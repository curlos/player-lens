/**
 * Audio module (specs/match-rules.md, "Crowd sound" and "Spoken commentary").
 * Phase 2 ships the hooks only: no audio files exist yet, so every call is a no-op that records state.
 * Phase 3 fills in Web Audio crowd loops and the commentary clip player behind the same functions.
 */
import type { TeamId } from "../types";

const state = { unlocked: false, muted: false };

/** Called from the Start click (a user gesture), which is what browsers require to allow audio. */
export function unlockAudio(): void {
  state.unlocked = true;
}

export function setMuted(muted: boolean): void {
  state.muted = muted;
}

export function isMuted(): boolean {
  return state.muted;
}

/** Crowd reaction to an event: clip and volume follow importance; Azure City is the home side. */
export function crowdReact(_importance: number, _team: TeamId): void {}

/** Play one commentary clip (no-op until Phase 3 provides audio URLs). */
export function playClip(_url: string | null): void {}

/** Stop the current commentary clip (speed changes, seeks, player switches). */
export function stopClip(): void {}
