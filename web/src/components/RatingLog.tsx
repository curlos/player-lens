/**
 * The rating reason log for the selected player, newest first. Text comes from the EN/ES
 * templates in lib/reasons.ts; silent entries (delta 0) are never shown. Clicking a row replays
 * it: the clock seeks a few seconds before the change and keeps playing or paused.
 */
import { useClock, useMatchSecond } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { deltaColor } from "../lib/colors";
import { RATING_LOG_LEAD_S } from "../lib/config";
import { deltaLabel, lastIndexAtOrBefore, minuteLabel, minuteSpoken } from "../lib/format";
import { playerLabel, type MatchData } from "../lib/match";
import { reasonText } from "../lib/reasons";

const MAX_ROWS = 60;

export function RatingLog({ match, player }: { match: MatchData; player: string }) {
  const clock = useClock();
  const s = useMatchSecond();
  const { lang, colorblind } = useSettings();
  const log = match.ratingLog.get(player) ?? [];
  const end = lastIndexAtOrBefore(log, s);
  const rows = [];
  for (let i = end; i >= 0 && rows.length < MAX_ROWS; i--) rows.push(log[i]);

  return (
    <section className="flex min-h-[10rem] flex-1 flex-col rounded-xl border border-white/5 bg-zinc-900/80 p-3">
      <h3 className="text-sm font-medium text-zinc-200">Rating log</h3>
      <div className="mt-1.5 grid grid-cols-[3.25rem_3.25rem_1fr] border-b border-white/10 pb-1 text-xs text-zinc-500">
        <span>Minute</span>
        <span>+/-</span>
        <span>Reason</span>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto" aria-label="Rating changes, newest first" lang={lang}>
        {rows.length === 0 && <li className="py-2 text-sm text-zinc-500">No rating changes yet.</li>}
        {rows.map((r) => {
          const reason = reasonText(r.reason_code, r.values, lang, (id) => playerLabel(match, id));
          return (
            <li key={r.id} className="border-b border-white/5">
              {/* the whole row replays the moment; the player stays selected */}
              <button
                type="button"
                onClick={() => clock.seek(Math.max(0, r.t - RATING_LOG_LEAD_S))}
                title={`Replay from ${RATING_LOG_LEAD_S} seconds before`}
                // the label replaces the row's text for screen readers, so it carries the off-ball tag too
                aria-label={`${minuteSpoken(r.t)}, ${deltaLabel(r.delta)}, ${reason}${r.off_ball ? ", off-ball" : ""}. Replay from ${RATING_LOG_LEAD_S} seconds before.`}
                className="grid w-full grid-cols-[3.25rem_3.25rem_1fr] items-start rounded py-1 text-left text-sm hover:bg-white/5"
              >
                <span className="tabular-nums text-zinc-400">{minuteLabel(r.t)}</span>
                <span className="font-semibold tabular-nums" style={{ color: deltaColor(r.delta, colorblind) }}>
                  {deltaLabel(r.delta)}
                </span>
                <span className="text-zinc-200">
                  {reason}
                  {r.off_ball && <span className="ml-1.5 rounded bg-lime-400/15 px-1 py-px text-xs font-medium text-lime-300">off-ball</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
