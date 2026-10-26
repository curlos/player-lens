/** Gear popover: Mute, Show ratings, Colorblind colors, Match info (with the match picker) and Settings. */
import { useEffect, useRef, useState } from "react";
import { useSettings } from "../hooks/useSettings";
import type { MatchData } from "../lib/match";
import type { MatchSummary } from "../types";
import { MatchPicker } from "./MatchPicker";
import { Toggle } from "./Toggle";

interface Props {
  match: MatchData;
  matches: MatchSummary[];
  onPickMatch: (id: string) => void;
}

const SHORTCUTS: [string, string][] = [
  ["Space", "Play or pause (starts the match from the intro)"],
  ["Enter", "Start the match from the intro"],
  ["← / →", "Back or forward 5 seconds"],
];

export function ViewPopover({ match, matches, onPickMatch }: Props) {
  const s = useSettings();
  const [page, setPage] = useState<"main" | "info" | "settings">("main");
  const panel = useRef<HTMLDivElement>(null);
  // move keyboard focus into the popover when it opens or changes page (Escape closes it)
  useEffect(() => {
    panel.current?.querySelector<HTMLElement>("button")?.focus();
  }, [page]);
  const meta = match.meta;

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label="View options"
      className="absolute bottom-full right-0 mb-2 w-64 rounded-lg border border-zinc-700/70 bg-zinc-900/95 p-2 text-sm text-zinc-200 shadow-2xl backdrop-blur"
      onClick={(e) => e.stopPropagation()}
    >
      {page === "main" && (
        <div className="space-y-0.5">
          {[
            ["Mute", s.muted, s.setMuted],
            ["Show ratings", s.showRatings, s.setShowRatings],
            ["Activity labels", s.activityLabels, s.setActivityLabels],
            ["Colorblind colors", s.colorblind, s.setColorblind],
            ["All movement arrows", s.allArrows, s.setAllArrows],
          ].map(([label, on, set]) => (
            <div key={label as string} className="flex items-center justify-between rounded px-2 py-1.5">
              <span>{label as string}</span>
              <Toggle on={on as boolean} onChange={set as (v: boolean) => void} label={label as string} />
            </div>
          ))}
          <div className="my-1 border-t border-zinc-700/70" />
          <button type="button" className="block w-full rounded px-2 py-1.5 text-left hover:bg-zinc-800" onClick={() => setPage("info")}>
            Match info
          </button>
          <button type="button" className="block w-full rounded px-2 py-1.5 text-left hover:bg-zinc-800" onClick={() => setPage("settings")}>
            Settings
          </button>
        </div>
      )}
      {page === "info" && (
        <div className="space-y-2 p-1">
          <button type="button" className="text-sm text-zinc-400 hover:text-zinc-200" onClick={() => setPage("main")}>
            ‹ Back
          </button>
          <div>
            <p className="font-semibold">Atlas League · {meta.label}</p>
            {meta.blurb && <p className="text-sm text-zinc-400">{meta.blurb}</p>}
            <p className="mt-1 text-sm text-zinc-400">
              {match.teams.azc.name} ({match.teams.azc.formation}) vs {match.teams.rdm.name} ({match.teams.rdm.formation})
            </p>
            <p className="text-sm text-zinc-500">All players, clubs and matches are fictional. Seed {meta.seed}.</p>
          </div>
          <MatchPicker matches={matches} current={match.id} onPick={onPickMatch} />
        </div>
      )}
      {page === "settings" && (
        <div className="space-y-2 p-1">
          <button type="button" className="text-sm text-zinc-400 hover:text-zinc-200" onClick={() => setPage("main")}>
            ‹ Back
          </button>
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Keyboard</p>
          <ul className="space-y-1 text-sm">
            {SHORTCUTS.map(([k, v]) => (
              <li key={k} className="flex gap-2">
                <kbd className="min-w-12 rounded bg-zinc-800 px-1.5 py-0.5 text-center font-mono text-xs">{k}</kbd>
                <span className="text-zinc-300">{v}</span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-zinc-500">Commentary plays at 1x only. Settings are remembered in this browser when storage is available.</p>
        </div>
      )}
    </div>
  );
}
