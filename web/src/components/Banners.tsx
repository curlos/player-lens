/** GOAL and PENALTY banners across the top of the pitch, shown briefly after the event. */
import { useMatchTime } from "../hooks/useClock";
import { VISUAL_S } from "../lib/config";
import { minuteLabel } from "../lib/format";
import { eventsInWindow, goalRevealT, type MatchData } from "../lib/match";

export function Banners({ match }: { match: MatchData }) {
  const t = useMatchTime(10);
  const recent = eventsInWindow(match, t, Math.max(VISUAL_S.goalBanner + 1, VISUAL_S.penaltyBanner)); // +1: a goal shows up to a second after its time (ball in flight)
  const goal = [...recent].reverse().find((e) => e.type === "goal" && t >= goalRevealT(match, e) && t - goalRevealT(match, e) <= VISUAL_S.goalBanner);
  const penalty = [...recent].reverse().find((e) => e.type === "penalty" && t - e.t <= VISUAL_S.penaltyBanner);

  if (goal) {
    const scorer = match.players.get(goal.player);
    const color = match.teams[goal.team].color;
    return (
      <div className="pointer-events-none absolute inset-x-[8%] top-[max(11%,3rem)] flex justify-center">
        <div
          className="w-full motion-safe:animate-[bannerIn_300ms_ease-out] rounded-sm py-1.5 text-center text-2xl font-extrabold tracking-wide text-white [text-shadow:0_1px_3px_rgba(0,0,0,0.45)] sm:text-3xl"
          style={{ background: `linear-gradient(90deg, transparent, ${color} 14%, ${color} 86%, transparent)` }}
        >
          GOAL - {scorer ? `#${scorer.number} ${scorer.name} ` : ""}
          {minuteLabel(goal.t)}
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
