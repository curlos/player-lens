/**
 * Audio module (specs/match-rules.md, "Crowd sound" and "Spoken commentary").
 * The crowd plays through Web Audio: a looped murmur plus reaction clips (and the referee's
 * whistle) chosen by `crowd.ts`, all real CC0 recordings. The Start click creates the
 * AudioContext (browsers only allow audio after a user gesture); the clips load in the
 * background after that, so playback never waits on them.
 *
 * Commentary voice (Phase 3): `playClip` decodes the line's MP3 and plays it through the same
 * AudioContext and master gain as the crowd, so the one Mute button silences both. While a clip
 * plays the crowd bus ducks (`CROWD.duck`, or `CROWD.duckGoal` while a goal roar sounds) and
 * comes back after the line (`duckAttackS` down, `duckReleaseS` back). `stopClip` ends the voice
 * at once (mute, seek, speed change, player or match switch). The text always shows: audio is
 * never the only source of information.
 */
import { CROWD, CROWD_CLIPS, type CrowdClip } from "./config";
import type { CrowdCue } from "./crowd";

const CLIP_BASE = "/audio/crowd/";

interface Voice {
  src: AudioBufferSourceNode;
  gain: GainNode;
}

const state = {
  unlocked: false,
  muted: false,
  playing: false,
  ctx: null as AudioContext | null,
  master: null as GainNode | null,
  /** Everything the crowd plays goes through this bus, so the voice can duck it in one place. */
  crowd: null as GainNode | null,
  murmurGain: null as GainNode | null,
  buffers: new Map<CrowdClip, AudioBuffer>(),
  voices: new Set<Voice>(),
  /** The commentary clip that is playing (null when none) and a token that voids a clip still decoding after a stop. */
  clip: null as { src: AudioBufferSourceNode | null; gain: GainNode | null; big: boolean } | null,
  /** The newest line that arrived while another was speaking; it plays when that one ends. */
  pending: null as { url: string; importance: number; since: number } | null,
  /** How close the ball is to a goal right now (0..1, from `dangerLevel`); the voice rises with it. */
  danger: 0,
  clipToken: 0,
  /** Context time until which a goal roar sounds (the crowd ducks less under it). */
  roarUntil: 0,
  /** Last cues played, newest last (read by the dev-only `__playerLens.audio`). */
  recent: [] as CrowdCue[],
};

/** Called from the Start click (a user gesture), which is what browsers require to allow audio. */
export function unlockAudio(): void {
  if (state.unlocked) return;
  state.unlocked = true;
  const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return; // no Web Audio: the match simply plays silent
  const ctx = new Ctx();
  const master = ctx.createGain();
  master.gain.value = state.muted ? 0 : CROWD.master;
  master.connect(ctx.destination);
  const crowd = ctx.createGain();
  crowd.gain.value = CROWD.crowdLevel;
  crowd.connect(master);
  const murmurGain = ctx.createGain();
  murmurGain.gain.value = 0;
  murmurGain.connect(crowd);
  Object.assign(state, { ctx, master, crowd, murmurGain });
  for (const name of Object.keys(CROWD_CLIPS) as CrowdClip[]) void loadClip(ctx, name);
}

async function loadClip(ctx: AudioContext, name: CrowdClip): Promise<void> {
  try {
    const res = await fetch(CLIP_BASE + CROWD_CLIPS[name].file);
    if (!res.ok) return;
    const buf = await ctx.decodeAudioData(await res.arrayBuffer());
    state.buffers.set(name, buf);
    if (name === "murmur") startMurmur(buf);
  } catch {
    // a missing or undecodable clip only means that reaction stays silent
  }
}

function startMurmur(buf: AudioBuffer) {
  const { ctx, murmurGain } = state;
  if (!ctx || !murmurGain) return;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.loop = true;
  src.connect(murmurGain);
  src.start();
}

export function setMuted(muted: boolean): void {
  state.muted = muted;
  if (muted) stopClip();
  const { ctx, master } = state;
  if (!ctx || !master) return;
  const target = muted ? 0 : CROWD.master;
  // a suspended context's clock is frozen, so a ramp would only run (audibly) on resume
  if (ctx.state === "running") master.gain.setTargetAtTime(target, ctx.currentTime, 0.05);
  else {
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.value = target;
  }
}

export function isMuted(): boolean {
  return state.muted;
}

let suspendTimer = 0;

/**
 * Follows the clock: paused means silence (the context is suspended), playing resumes it. At full
 * time (`linger`) the final whistle and the fading murmur ring out before the suspend.
 */
export function setAudioPlaying(playing: boolean, linger = false): void {
  state.playing = playing;
  const { ctx } = state;
  if (!ctx) return;
  window.clearTimeout(suspendTimer);
  if (playing) void ctx.resume();
  else if (linger) suspendTimer = window.setTimeout(() => void ctx.suspend(), 2500);
  else void ctx.suspend();
}

/** Below this change the murmur is not rescheduled (called every frame; each call adds an automation event). */
const MURMUR_STEP = 0.01;
let murmurTarget = -1;

/** Murmur volume, eased so ball movement doesn't make it flutter. */
export function setMurmurLevel(level: number): void {
  const { ctx, murmurGain } = state;
  if (!ctx || !murmurGain || Math.abs(level - murmurTarget) < MURMUR_STEP) return;
  murmurTarget = level;
  murmurGain.gain.setTargetAtTime(level * CROWD_CLIPS.murmur.norm, ctx.currentTime, 0.8);
}

/** Plays one crowd cue now; skipped silently if its clip hasn't loaded yet. */
export function playCue(cue: CrowdCue): void {
  const { ctx, crowd } = state;
  if (!ctx || !crowd) return;
  state.recent = [...state.recent.slice(-19), cue];
  const name: CrowdClip = cue.sound === "whistleLong" ? "whistle" : cue.sound;
  const buf = state.buffers.get(name);
  if (!buf) return;
  const clip = CROWD_CLIPS[name];
  const blasts = cue.sound === "whistleLong" ? [0, CROWD.finalWhistleGap, 2 * CROWD.finalWhistleGap] : [0];
  const play = Math.min(cue.play ?? clip.play, buf.duration - clip.offset);
  for (const at of blasts) playBuffer(ctx, crowd, buf, clip.offset, play, cue.gain * clip.norm, at);
  if (name === "roar") {
    state.roarUntil = ctx.currentTime + play;
    if (state.clip) applyDuck(); // a roar starting under the voice: the crowd may come up to the goal level
  }
}

function playBuffer(ctx: AudioContext, out: AudioNode, buf: AudioBuffer, offset: number, play: number, level: number, delay: number) {
  const now = ctx.currentTime + delay;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const gain = ctx.createGain();
  // a short clip (the whistle) keeps its own attack and tail; longer ones fade in and out
  const fade = Math.min(CROWD.fadeS, play / 4);
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(level, now + Math.min(0.08, fade));
  gain.gain.setValueAtTime(level, now + play - fade);
  gain.gain.linearRampToValueAtTime(0, now + play);
  src.connect(gain).connect(out);
  const voice = { src, gain };
  state.voices.add(voice);
  src.onended = () => state.voices.delete(voice);
  src.start(now, offset, play + 0.05);
}

/** After a seek: fade out every reaction still sounding (the murmur keeps going). */
export function stopReactions(): void {
  const { ctx } = state;
  if (!ctx) return;
  const now = ctx.currentTime;
  for (const v of state.voices) {
    v.gain.gain.cancelScheduledValues(now);
    v.gain.gain.setTargetAtTime(0, now, CROWD.fadeS / 3);
    v.src.stop(now + CROWD.fadeS);
  }
  state.voices.clear();
}

/** Dev checks only: what the crowd engine is doing. */
export function audioDebug() {
  return {
    context: state.ctx?.state ?? "none",
    muted: state.muted,
    master: state.master?.gain.value ?? null,
    murmur: state.murmurGain?.gain.value ?? null,
    loaded: [...state.buffers.keys()],
    voices: state.voices.size,
    clip: state.clip ? "playing" : null,
    crowdBus: state.crowd?.gain.value ?? null,
    recent: state.recent,
  };
}

/** Decoded commentary clips by URL (a promise, so a preload and a play share one fetch). Small: a minute holds about five clips. */
const clipCache = new Map<string, Promise<AudioBuffer | null>>();
const CLIP_CACHE_MAX = 40;

function decodeClip(url: string): Promise<AudioBuffer | null> {
  const ctx = state.ctx;
  if (!ctx) return Promise.resolve(null);
  let hit = clipCache.get(url);
  if (!hit) {
    const load: Promise<AudioBuffer | null> = fetch(url)
      .then((res) => (res.ok ? res.arrayBuffer() : Promise.reject(new Error("clip not found"))))
      .then((data) => ctx.decodeAudioData(data))
      .catch(() => {
        if (clipCache.get(url) === load) clipCache.delete(url); // forget the failure, so a later preload or play tries again
        return null; // this time the line is read, not heard
      });
    hit = load;
    clipCache.set(url, hit);
    if (clipCache.size > CLIP_CACHE_MAX) clipCache.delete(clipCache.keys().next().value as string);
  }
  return hit;
}

/** Fetch and decode a line's clip ahead of its start so it plays without delay (the panel calls this when a chunk arrives). */
export function preloadClip(url: string | null | undefined): void {
  if (url && state.ctx) void decodeClip(url);
}

/** Crowd bus level: `crowdLevel`, times the duck factor while a clip plays (both duck factors are 1 now: no ducking). */
function applyDuck(): void {
  const { ctx, crowd } = state;
  if (!ctx || !crowd) return;
  crowd.gain.cancelScheduledValues(ctx.currentTime);
  if (state.clip) {
    const level = ctx.currentTime < state.roarUntil ? CROWD.duckGoal : CROWD.duck;
    crowd.gain.setTargetAtTime(CROWD.crowdLevel * level, ctx.currentTime, CROWD.duckAttackS / 3);
  } else {
    crowd.gain.setTargetAtTime(CROWD.crowdLevel, ctx.currentTime, CROWD.duckReleaseS / 3);
  }
}

/** Voice level for a clip: louder as the ball nears a goal, and louder again for a big line. */
function voiceLevel(big: boolean): number {
  return CROWD.voiceGain * (1 + CROWD.voiceDangerBoost * state.danger) * (big ? CROWD.voiceBigBoost : 1);
}

/** Below this change the voice level is not rescheduled (called every frame). */
const DANGER_STEP = 0.02;

/** Called every frame with `dangerLevel(match, t)`: a clip that is playing follows the ball, like the crowd murmur. */
export function setVoiceDanger(danger: number): void {
  if (Math.abs(danger - state.danger) < DANGER_STEP) return;
  state.danger = danger;
  const { ctx, clip } = state;
  if (ctx && clip?.gain) clip.gain.gain.setTargetAtTime(voiceLevel(clip.big), ctx.currentTime, 0.3);
}

/**
 * Play one commentary line's clip (`audio_url`); null or a failed load plays nothing.
 * A line that arrives while another is still speaking waits for it to finish instead of cutting it off (owner: the goal
 * line was interrupted by its own celebration line). Only the newest waiting line is kept, and it is dropped if it has
 * waited longer than `CROWD.voiceQueueMaxS`. A big line (`importance` >= 0.8: goals, cards) still cuts off an ordinary
 * one. `resume` wakes a suspended context and always plays now (a click on the recap's Listen button).
 */
export function playClip(url: string | null, resume = false, importance = 0): void {
  const { ctx } = state;
  const big = importance >= 0.8;
  if (ctx && !resume && state.clip && !(big && !state.clip.big)) {
    if (url) state.pending = { url, importance, since: ctx.currentTime }; // a line with no clip leaves the waiting one alone
    return;
  }
  stopClip();
  startClip(url, resume, importance);
}

function startClip(url: string | null, resume: boolean, importance: number): void {
  const { ctx, master } = state;
  if (!url || !ctx || !master || state.muted) return;
  if (resume && ctx.state === "suspended") void ctx.resume(); // the full-time recap button: the clock is stopped, the click is the gesture
  const token = ++state.clipToken;
  const big = importance >= 0.8;
  // Holds the place while the clip decodes, so a line arriving meanwhile waits instead of starting over it.
  state.clip = { src: null, gain: null, big };
  void decodeClip(url).then((buf) => {
    if (token !== state.clipToken) return; // stopped (or replaced) while it was loading
    if (!buf) {
      state.clip = null;
      playPending();
      return;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const gain = ctx.createGain();
    gain.gain.value = voiceLevel(big);
    // A limiter after the boost, so a loud line near goal never distorts; the same master as the crowd, so Mute silences both.
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -3;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.1;
    src.connect(gain).connect(limiter).connect(master);
    const clip = { src, gain, big };
    state.clip = clip;
    src.onended = () => {
      if (state.clip === clip) {
        state.clip = null;
        applyDuck();
        playPending();
      }
    };
    src.start();
    applyDuck();
  });
}

/** Plays the line that waited for the last one to finish, unless it has gone stale. */
function playPending(): void {
  const { ctx, pending } = state;
  state.pending = null;
  if (!ctx || !pending || ctx.currentTime - pending.since > CROWD.voiceQueueMaxS) return;
  startClip(pending.url, false, pending.importance);
}

/** Stop the commentary clip (mute, speed changes, seeks, player and match switches) and bring the crowd back. */
export function stopClip(): void {
  state.clipToken++; // voids a clip that is still loading
  state.pending = null; // a waiting line is dropped too (seek, mute, speed, player or match change)
  const { ctx, clip } = state;
  if (!ctx || !clip) return;
  state.clip = null;
  if (!clip.src || !clip.gain) return; // it was still decoding
  const now = ctx.currentTime;
  clip.gain.gain.cancelScheduledValues(now);
  clip.gain.gain.setTargetAtTime(0, now, 0.015);
  clip.src.onended = null;
  clip.src.stop(now + 0.08);
  applyDuck();
}
