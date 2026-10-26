/**
 * Full-time card: final score, the champions line for a title decider, the selected player's
 * match rating, their top three rating moments and a recap paragraph.
 * Recap: Phase 2 builds it from code facts; Phase 3 swaps in GET /recap (pre-generated text).
 */
import { useSettings } from "../hooks/useSettings";
import { deltaColor } from "../lib/colors";
import { deltaLabel, minuteLabel, ratingLabel } from "../lib/format";
import { STANDINGS } from "../lib/config";
import { distanceKmAt, goalsAndAssistsAt, playerLabel, ratingAt, titleWinner, type MatchData } from "../lib/match";
import { reasonText } from "../lib/reasons";
import { AvatarIcon, BallIcon, ReplayIcon } from "./icons";
import { RatingPill } from "./RatingPill";

interface Props {
  match: MatchData;
  player: string;
  onReplay: () => void;
  onPickAnother: () => void;
}

function recapText(match: MatchData, player: string, lang: "en" | "es"): string {
  const p = match.players.get(player)!;
  const end = match.duration;
  const { goals, assists } = goalsAndAssistsAt(match, player, end);
  const rating = ratingLabel(ratingAt(match, player, end));
  const km = distanceKmAt(match, player, end).toFixed(1);
  const offBall = (match.ratingLog.get(player) ?? []).filter((r) => r.off_ball && r.delta > 0).length;
  if (lang === "es") {
    return `${p.name} termina con un ${rating}: ${goals} gol${goals === 1 ? "" : "es"}, ${assists} asistencia${assists === 1 ? "" : "s"}, ${km} km recorridos y ${offBall} acciones sin pelota premiadas.`;
  }
  return `${p.name} finishes on ${rating}: ${goals} goal${goals === 1 ? "" : "s"}, ${assists} assist${assists === 1 ? "" : "s"}, ${km} km covered and ${offBall} rewarded off-ball actions.`;
}

export function FullTimeCard({ match, player, onReplay, onPickAnother }: Props) {
  const { lang, colorblind } = useSettings();
  const p = match.players.get(player);
  const { azc, rdm } = match.meta.score;
  const champion = match.teams[titleWinner(STANDINGS, match.meta.score)];
  const top = [...(match.ratingLog.get(player) ?? [])].filter((r) => r.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, 3);
  const maxDelta = top[0]?.delta ?? 1;
  const { goals } = goalsAndAssistsAt(match, player, match.duration);

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center p-4">
      <div
        className="w-full max-w-sm rounded-2xl border border-white/10 bg-zinc-900/95 p-5 text-center text-zinc-200 shadow-2xl"
        role="dialog"
        aria-labelledby="full-time-title"
      >
        <h2 id="full-time-title" className="text-3xl font-bold text-white">
          Full time
        </h2>
        <p className="mt-1 text-lg text-zinc-300">
          {match.teams.azc.name} <span className="font-bold text-white">{azc} - {rdm}</span> {match.teams.rdm.name}
        </p>
        {match.meta.title_decider && <p className="mt-0.5 text-lg text-amber-300">{champion.name}: Atlas League champions</p>}

        {p && (
          <div className="mt-4 rounded-xl border border-white/10 bg-zinc-800/60 p-3 text-left">
            <div className="flex items-center gap-3">
              <AvatarIcon className="h-11 w-11 shrink-0" />
              <div>
                <p className="text-lg font-semibold text-white">{p.name}</p>
                <p className="flex items-center gap-2 text-sm text-zinc-400">
                  match rating <RatingPill rating={ratingAt(match, player, match.duration)} className="px-1.5 text-sm" />
                  {goals > 0 && (
                    <span className="flex items-center gap-0.5">
                      {goals} goal{goals === 1 ? "" : "s"} {Array.from({ length: goals }, (_, i) => <BallIcon key={i} className="h-3 w-3" />)}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <p className="mt-3 text-sm text-zinc-400">Top 3 rating moments</p>
            <ul className="mt-1 space-y-1">
              {top.map((r) => (
                <li key={r.id} className="grid grid-cols-[1fr_3rem_5rem] items-center gap-2 text-sm">
                  <span className="min-w-0 break-words text-zinc-200">
                    {minuteLabel(r.t)} {reasonText(r.reason_code, r.values, lang, (id) => playerLabel(match, id))}
                  </span>
                  <span className="text-right font-semibold tabular-nums" style={{ color: deltaColor(r.delta, colorblind) }}>
                    {deltaLabel(r.delta)}
                  </span>
                  <span className="h-2 rounded-full" style={{ width: `${Math.max(8, (r.delta / maxDelta) * 100)}%`, background: deltaColor(r.delta, colorblind) }} />
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm leading-relaxed text-zinc-300">{recapText(match, player, lang)}</p>
          </div>
        )}

        <button
          type="button"
          autoFocus
          onClick={onReplay}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-700 py-2.5 font-medium text-white hover:bg-zinc-600"
        >
          <ReplayIcon className="h-4 w-4" /> Replay match
        </button>
        <button type="button" onClick={onPickAnother} className="mt-2 text-sm text-zinc-400 underline decoration-zinc-600 underline-offset-2 hover:text-zinc-200">
          Pick another player
        </button>
      </div>
    </div>
  );
}
