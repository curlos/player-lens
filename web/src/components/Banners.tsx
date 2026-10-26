/** GOAL and PENALTY banners across the top of the pitch, shown briefly after the event. */
import { useMatchTime } from "../hooks/useClock";
import { VISUAL_S } from "../lib/config";
import { minuteLabel } from "../lib/format";
import { eventsInWindow, type MatchData } from "../lib/match";

export function Banners({ match }: { match: MatchData }) {
  const t = useMatchTime(10);
  const recent = eventsInWindow(match, t, Math.max(VISUAL_S.goalBanner, VISUAL_S.penaltyBanner));
  const goal = [...recent].reverse().find((e) => e.type === "goal" && t - e.t <= VISUAL_S.goalBanner);
  const penalty = [...recent].reverse().find((e) => e.type === "penalty" && t - e.t <= VISUAL_S.penaltyBanner);

  if (goal) {
    const scorer = match.players.get(goal.player);
    const color = match.teams[goal.team].color;
    return (
      <div className="pointer-events-none absolute inset-x-[8%] top-[max(11%,3rem)] flex justify-center">
        <div
          className="w-full motion-safe:animate-[bannerIn_300ms_ease-out] rounded-sm py-1.5 text-center text-2xl font-extrabold tracking-wide text-zinc-900 shadow-lg sm:text-3xl"
          style={{ background: `linear-gradient(90deg, transparent, ${color}55 8%, #e2f5d8 30%, #e2f5d8 70%, ${color}55 92%, transparent)` }}
        >
          GOAL - {scorer?.name} {minuteLabel(goal.t)}
        </div>
      </div>
    );
  }
  if (penalty) {
    return (
      <div className="pointer-events-none absolute left-1/2 top-[max(11%,3rem)] -translate-x-1/2">
        <div className="motion-safe:animate-[bannerIn_300ms_ease-out] rounded-md border-2 border-orange-300/80 bg-zinc-900/90 px-5 py-1 text-2xl font-extrabold tracking-wider text-orange-200 shadow-lg sm:text-3xl">
          PENALTY
        </div>
      </div>
    );
  }
  return null;
}
