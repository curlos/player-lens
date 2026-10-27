/**
 * Audio module (specs/match-rules.md, "Crowd sound" and "Spoken commentary").
 * The crowd plays through Web Audio: a looped murmur plus reaction clips (and the referee's
 * whistle) chosen by `crowd.ts`, all real CC0 recordings. The Start click creates the
 * AudioContext (browsers only allow audio after a user gesture); the clips load in the
 * background after that, so playback never waits on them. Commentary clips are Phase 3:
 * `playClip` and `stopClip` stay no-ops until the backend provides audio URLs.
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
  murmurGain: null as GainNode | null,
  buffers: new Map<CrowdClip, AudioBuffer>(),
  voices: new Set<Voice>(),
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
  const murmurGain = ctx.createGain();
  murmurGain.gain.value = 0;
  murmurGain.connect(master);
  Object.assign(state, { ctx, master, murmurGain });
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
  const { ctx, master } = state;
  if (!ctx || !master) return;
  state.recent = [...state.recent.slice(-19), cue];
  const name: CrowdClip = cue.sound === "whistleLong" ? "whistle" : cue.sound;
  const buf = state.buffers.get(name);
  if (!buf) return;
  const clip = CROWD_CLIPS[name];
  const blasts = cue.sound === "whistleLong" ? [0, CROWD.finalWhistleGap, 2 * CROWD.finalWhistleGap] : [0];
  for (const at of blasts) playBuffer(ctx, master, buf, clip.offset, Math.min(cue.play ?? clip.play, buf.duration - clip.offset), cue.gain * clip.norm, at);
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
    recent: state.recent,
  };
}

/** Play one commentary clip (no-op until Phase 3 provides audio URLs). */
export function playClip(_url: string | null): void {}

/** Stop the current commentary clip (speed changes, seeks, player switches). */
export function stopClip(): void {}
