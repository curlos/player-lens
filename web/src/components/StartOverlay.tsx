/**
 * Start match overlay (PRODUCT, "Intro copy"). No homepage: the site opens on the match with the
 * star selected. Start (or Enter / Space) begins playback and unlocks audio.
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { STANDINGS } from "../lib/config";
import type { MatchData } from "../lib/match";
import type { MatchSummary } from "../types";
import { MatchPicker } from "./MatchPicker";

interface Props {
  match: MatchData | null;
  matchId: string;
  matches: MatchSummary[];
  error: string | null;
  onStart: () => void;
  onPickMatch: (id: string) => void;
}

/** Tailwind's `lg`: from here the pitch is tall enough to hold the card. */
const WIDE = "(min-width: 1024px)";

function useWide(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  useEffect(() => {
    const mq = window.matchMedia(WIDE);
    const onChange = () => setWide(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return wide;
}

export function StartOverlay({ match, matchId, matches, error, onStart, onPickMatch }: Props) {
  const wide = useWide();
  const meta = match?.meta;
  const titleDecider = meta?.title_decider ?? true;
  const startButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (match) startButton.current?.focus();
  }, [match]);
  const overlay = (
    // Over the pitch from lg up; below lg the pitch is far shorter than the card, so it covers the
    // whole screen like a mobile modal. Either way it scrolls rather than spilling past the top.
    <div className={`inset-0 z-30 overflow-y-auto backdrop-blur-[1px] ${wide ? "absolute bg-zinc-950/55" : "fixed bg-zinc-950/80"}`}>
      <div className="flex min-h-full items-center justify-center p-4">
      <div
        className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900/95 p-6 text-zinc-200 shadow-2xl"
        role="dialog"
        aria-labelledby="start-title"
      >
        <h1 id="start-title" className="flex items-center gap-2.5 text-2xl font-bold text-white">
          <img src="/favicon.svg" alt="" width={32} height={32} className="h-8 w-8 shrink-0" />
          Player Lens
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-zinc-300">
          {titleDecider ? (
            <>
              Atlas League, matchday {meta?.matchday ?? 38}. Redmond United lead Azure City by a single point, so Azure must win to take
              the title.
            </>
          ) : (
            <>
              Atlas League, matchday {meta?.matchday}: Azure City vs Redmond United{meta?.blurb ? `, ${meta.blurb.toLowerCase()}` : ""}.
            </>
          )}
        </p>
        <p className="mt-3 text-sm leading-relaxed text-zinc-300">
          Pick any player and follow the match through their eyes. You get a personal commentator and a live rating that explains every
          change, including the off-ball work normal ratings ignore, like pressing, tracking back and decoy runs.
        </p>

        {titleDecider && (
          <div className="mt-4 border-t border-white/10 pt-3">
            <p className="text-sm text-zinc-400">Atlas League title decider · Matchday 38 of 38</p>
            <div className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-sm">
              <span>Redmond United ({STANDINGS.rdm.pos})</span>
              <span className="rounded bg-zinc-800 px-2 text-right tabular-nums">
                <span className="mr-2 font-semibold text-red-400">RDM</span>
                {STANDINGS.rdm.pts} pts
              </span>
              <span>Azure City ({STANDINGS.azc.pos})</span>
              <span className="rounded bg-zinc-800 px-2 text-right tabular-nums">
                <span className="mr-2 font-semibold text-blue-400">AZC</span>
                {STANDINGS.azc.pts} pts
              </span>
            </div>
          </div>
        )}

        {error ? (
          <p className="mt-5 rounded-lg bg-red-500/15 p-3 text-sm text-red-300">Could not load the match: {error}</p>
        ) : (
          <button
            ref={startButton}
            type="button"
            disabled={!match}
            onClick={onStart}
            className="mt-5 w-full rounded-lg bg-lime-400 py-2.5 text-base font-semibold text-zinc-900 transition hover:bg-lime-300 disabled:cursor-wait disabled:bg-zinc-700 disabled:text-zinc-400"
          >
            {match ? "Start match" : "Preparing match…"}
          </button>
        )}
        <p className="mt-2 text-center text-sm text-zinc-400">Click to start the match and enable commentary audio</p>
        <p className="mt-1 text-center text-sm text-zinc-500">All players, clubs and matches are fictional.</p>
        <div className="mt-3 text-center">
          <MatchPicker matches={matches} current={matchId} onPick={onPickMatch} compact />
        </div>
      </div>
      </div>
    </div>
  );
  // below lg, rendered into <body>: the pitch's container query would otherwise pin `fixed` to the pitch box
  return wide ? overlay : createPortal(overlay, document.body);
}
