/** Selected player's card: silhouette, name, number and position, OVR, live rating, chart, stat badges. */
import { useMatchTime } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { KEEPER_COLORS } from "../lib/config";
import { distanceKmAt, goalsAndAssistsAt, ratingAt, xgAt, type MatchData } from "../lib/match";
import { AvatarIcon, BallIcon, BootIcon } from "./icons";
import { RatingChart } from "./RatingChart";
import { RatingPill } from "./RatingPill";

export function PlayerCard({ match, player, final }: { match: MatchData; player: string; final?: boolean }) {
  const t = useMatchTime(4);
  const { mode } = useSettings();
  const p = match.players.get(player);
  if (!p) return null;
  const { goals, assists } = goalsAndAssistsAt(match, player, t);
  const sentOff = match.sentOff.get(player);
  const team = match.teams[p.team];

  return (
    <section className="shrink-0 rounded-xl border border-white/5 bg-zinc-900/80 p-3">
      {/* top-aligned, so the Analyst stat line under the name doesn't push the avatar down */}
      <div className="flex items-start gap-3">
        <AvatarIcon className="mt-0.5 h-11 w-11 shrink-0" />
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold leading-tight text-zinc-50">{p.name}</h2>
          <div className="mt-0.5 flex items-center gap-1.5 text-sm text-zinc-400">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.isKeeper ? KEEPER_COLORS[p.team] : team.color }} />
            <span>
              #{p.number} · {p.slot}
            </span>
            <span className="rounded bg-zinc-700/80 px-1.5 py-px text-xs font-semibold text-zinc-300">OVR {p.ovr}</span>
            {sentOff && t >= sentOff.cardT && <span className="rounded bg-red-500/20 px-1.5 py-px text-xs font-semibold text-red-300">Sent off</span>}
          </div>
          {mode === "analyst" && (
            <p
              className="mt-0.5 text-xs tabular-nums text-zinc-400"
              title="Expected goals (xG): the combined chance of all this player's shots so far; 1.00 would be one goal's worth of chances. Distance covered: how far this player has run so far."
            >
              Expected goals (xG) {xgAt(match, player, t).toFixed(2)} · Distance covered {distanceKmAt(match, player, t).toFixed(1)} km
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-sm text-zinc-300">{final ? "Match rating" : "Live rating"}</span>
        <RatingPill rating={ratingAt(match, player, t)} className="px-2.5 py-0.5 text-lg" />
      </div>
      <div className="mt-1">
        <RatingChart match={match} player={player} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-white/5 pt-2 text-sm text-zinc-300">
        <span
          className="flex cursor-help items-center gap-1.5 rounded-full bg-zinc-800 px-2.5 py-0.5"
          title="Goals: times this player has scored in the match so far"
        >
          <BallIcon className="h-4 w-4" />
          <span className="tabular-nums">{goals}</span>
          <span className="text-zinc-400">{goals === 1 ? "goal" : "goals"}</span>
        </span>
        <span
          className="flex cursor-help items-center gap-1.5 rounded-full bg-zinc-800 px-2.5 py-0.5"
          title="Assists: the last pass before a teammate's goal (the boot is the assist icon)"
        >
          <BootIcon className="h-4 w-4 text-zinc-300" />
          <span className="tabular-nums">{assists}</span>
          <span className="text-zinc-400">{assists === 1 ? "assist" : "assists"}</span>
        </span>
      </div>
    </section>
  );
}
