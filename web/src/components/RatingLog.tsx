/**
 * The rating reason log for the selected player, newest first. Text comes from the EN/ES
 * templates in lib/reasons.ts; silent entries (delta 0) are never shown.
 */
import { useMatchSecond } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { deltaColor } from "../lib/colors";
import { deltaLabel, lastIndexAtOrBefore, minuteLabel } from "../lib/format";
import { playerLabel, type MatchData } from "../lib/match";
import { reasonText } from "../lib/reasons";

const MAX_ROWS = 60;

export function RatingLog({ match, player }: { match: MatchData; player: string }) {
  const s = useMatchSecond();
  const { lang, colorblind } = useSettings();
  const log = match.ratingLog.get(player) ?? [];
  const end = lastIndexAtOrBefore(log, s);
  const rows = [];
  for (let i = end; i >= 0 && rows.length < MAX_ROWS; i--) rows.push(log[i]);

  return (
    <section className="flex min-h-[7rem] flex-1 flex-col rounded-xl border border-white/5 bg-zinc-900/80 p-3">
      <h3 className="text-sm font-medium text-zinc-200">Rating log</h3>
      <div className="mt-1.5 grid grid-cols-[3.25rem_3.25rem_1fr] border-b border-white/10 pb-1 text-xs text-zinc-500">
        <span>Minute</span>
        <span>+/-</span>
        <span>Reason</span>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto" aria-label="Rating changes, newest first" lang={lang}>
        {rows.length === 0 && <li className="py-2 text-sm text-zinc-500">No rating changes yet.</li>}
        {rows.map((r) => (
          <li key={r.id} className="grid grid-cols-[3.25rem_3.25rem_1fr] items-start border-b border-white/5 py-1 text-sm">
            <span className="tabular-nums text-zinc-400">{minuteLabel(r.t)}</span>
            <span className="font-semibold tabular-nums" style={{ color: deltaColor(r.delta, colorblind) }}>
              {deltaLabel(r.delta)}
            </span>
            <span className="text-zinc-200">
              {reasonText(r.reason_code, r.values, lang, (id) => playerLabel(match, id))}
              {r.off_ball && <span className="ml-1.5 rounded bg-lime-400/15 px-1 py-px text-xs font-medium text-lime-300">off-ball</span>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
