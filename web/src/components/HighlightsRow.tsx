/**
 * Highlights row below the pitch: every goal, card and penalty as a chip in the team's color,
 * for example "88' GOAL #10 J. Ribeiro". A click seeks 8 s before the event and keeps play state.
 */
import { useClock, useClockState, useMatchTime } from "../hooks/useClock";
import { HIGHLIGHT_LEAD_S } from "../lib/config";
import { minuteLabel, minuteSpoken } from "../lib/format";
import { shownAt, type HighlightKind, type MatchData } from "../lib/match";
import { BallIcon, PenaltyIcon } from "./icons";

const KIND_LABEL: Record<HighlightKind, string> = { goal: "GOAL", yellow: "YEL", red: "RED", penalty: "PEN" };
const KIND_SPOKEN: Record<HighlightKind, string> = { goal: "goal", yellow: "yellow card", red: "red card", penalty: "penalty" };

export function HighlightsRow({ match }: { match: MatchData }) {
  const clock = useClock();
  const { started } = useClockState();
  const t = useMatchTime(10);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {match.highlights.map((h) => {
        const p = match.players.get(h.player);
        const color = match.teams[h.team].color;
        const past = shownAt(match, h.t) <= t; // a goal chip lights up when the ball lands
        return (
          <button
            key={h.id}
            type="button"
            // before Start the match must begin at kickoff, as with the keyboard and the timeline
            disabled={!started}
            onClick={() => clock.seek(Math.max(0, h.t - HIGHLIGHT_LEAD_S))}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm font-medium text-zinc-100 transition hover:brightness-125 disabled:cursor-default disabled:hover:brightness-100 ${past ? "" : "opacity-60"}`}
            style={{ borderColor: `${color}aa`, background: `${color}26` }}
            title="Jump to 8 seconds before"
            aria-label={`${minuteSpoken(h.t)}, ${KIND_SPOKEN[h.kind]}, #${p?.number} ${p?.name}. Jump to 8 seconds before.`}
          >
            <span className="tabular-nums text-zinc-400">{minuteLabel(h.t)}</span>
            {h.kind === "yellow" && <span className="inline-block h-3 w-2 rounded-[1px] bg-yellow-400" />}
            {h.kind === "red" && <span className="inline-block h-3 w-2 rounded-[1px] bg-red-500" />}
            {h.kind === "goal" && <BallIcon className="h-3.5 w-3.5 shrink-0" />}
            {h.kind === "penalty" && <PenaltyIcon className="h-3.5 w-3.5 shrink-0" />}
            <span className="font-bold" style={{ color: h.kind === "goal" ? "#fff" : undefined }}>
              {KIND_LABEL[h.kind]}
            </span>
            <span>
              #{p?.number} {p?.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
