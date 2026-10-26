/** The three library matches with matchday and result; the current one is highlighted. */
import type { MatchSummary } from "../types";

interface Props {
  matches: MatchSummary[];
  current: string;
  onPick: (id: string) => void;
  compact?: boolean;
}

export function MatchPicker({ matches, current, onPick, compact }: Props) {
  if (compact) {
    const others = matches.filter((m) => m.match_id !== current);
    if (!others.length) return null;
    return (
      <p className="text-sm text-zinc-400">
        Other matches:{" "}
        {others.map((m, i) => (
          <span key={m.match_id}>
            {i > 0 && " · "}
            <button type="button" className="underline decoration-zinc-600 underline-offset-2 hover:text-zinc-200" onClick={() => onPick(m.match_id)}>
              {m.label} ({m.home} {m.score.azc}-{m.score.rdm} {m.away})
            </button>
          </span>
        ))}
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {matches.map((m) => (
        <li key={m.match_id}>
          <button
            type="button"
            onClick={() => onPick(m.match_id)}
            className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${m.match_id === current ? "bg-zinc-700 text-white" : "text-zinc-300 hover:bg-zinc-800"}`}
          >
            <span>
              {m.label}
              {m.blurb && <span className="text-zinc-400"> · {m.blurb}</span>}
            </span>
            <span className="tabular-nums">
              {m.home} {m.score.azc}-{m.score.rdm} {m.away}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
