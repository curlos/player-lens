/** Score bar centered at the top of the pitch: AZC, score, RDM, clock. Cards appear only once a team has one. */
import { useMatchTime } from "../hooks/useClock";
import { clockLabel } from "../lib/format";
import { scoreAt, teamCardsAt, type MatchData } from "../lib/match";
import type { TeamId } from "../types";

function Cards({ match, team, t }: { match: MatchData; team: TeamId; t: number }) {
  const { yellow, reds } = teamCardsAt(match, team, t);
  if (!yellow && !reds) return null;
  return (
    <div className="absolute left-1/2 top-full mt-1 flex -translate-x-1/2 items-center gap-1 whitespace-nowrap">
      {yellow && <span className="inline-block h-2.5 w-[7px] rounded-[1px] bg-yellow-400" aria-label="yellow card" />}
      {reds > 0 && <span className="inline-block h-2.5 w-[7px] rounded-[1px] bg-red-500" aria-label="red card" />}
      {reds > 0 && (
        <span className="rounded bg-zinc-900/90 px-1.5 py-px text-[10px] font-medium text-zinc-200">{11 - reds} men</span>
      )}
    </div>
  );
}

export function ScoreBar({ match }: { match: MatchData }) {
  const t = useMatchTime(10);
  const score = scoreAt(match, t);
  const { azc, rdm } = match.teams;
  return (
    <div className="flex items-stretch overflow-visible rounded-md text-[15px] font-semibold shadow-lg shadow-black/40 sm:text-lg">
      <div className="relative flex w-16 items-center justify-center rounded-l-md py-1 text-white sm:w-[4.5rem]" style={{ background: azc.color }}>
        {azc.abbr}
        <Cards match={match} team="azc" t={t} />
      </div>
      <div className="flex w-16 items-center justify-center bg-zinc-900 tabular-nums text-zinc-100 sm:w-[4.5rem]">
        {score.azc} - {score.rdm}
      </div>
      <div className="relative flex w-16 items-center justify-center py-1 text-white sm:w-[4.5rem]" style={{ background: rdm.color }}>
        {rdm.abbr}
        <Cards match={match} team="rdm" t={t} />
      </div>
      <div className="flex w-[4.5rem] items-center justify-center rounded-r-md bg-zinc-100 tabular-nums text-zinc-900 sm:w-20">
        {clockLabel(t)}
      </div>
    </div>
  );
}
