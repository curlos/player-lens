/**
 * Screen-reader announcements for the match's big moments (goals, cards, penalties). The pitch and
 * its banners are visual, so this polite live region says the same thing in words.
 */
import { useMatchTime } from "../hooks/useClock";
import { lastIndexAtOrBefore, minuteSpoken } from "../lib/format";
import { shownAt, type MatchData } from "../lib/match";

/** How long after the moment it is still worth announcing (match seconds). */
const ANNOUNCE_S = 6;

export function LiveAnnouncer({ match }: { match: MatchData }) {
  const t = useMatchTime(10);
  // a goal is announced when the ball lands (shownAt), like the banner; cards and penalties at once
  let i = lastIndexAtOrBefore(match.highlights, t);
  if (i >= 0 && shownAt(match, match.highlights[i].t) > t) i--;
  const h = i >= 0 && t - shownAt(match, match.highlights[i].t) <= ANNOUNCE_S ? match.highlights[i] : null;

  let text = "";
  if (h) {
    const p = match.players.get(h.player);
    const who = p ? `#${p.number} ${p.name}` : "";
    const team = match.teams[h.team].name;
    const { azc, rdm } = h.event.score;
    if (h.kind === "goal") {
      text = `Goal, ${minuteSpoken(h.t)}: ${who}, ${team}. ${match.teams.azc.name} ${azc}, ${match.teams.rdm.name} ${rdm}.`;
    } else if (h.kind === "penalty") {
      text = `Penalty to ${team}, ${minuteSpoken(h.t)}.`;
    } else {
      text = `${h.kind === "red" ? "Red" : "Yellow"} card, ${minuteSpoken(h.t)}: ${who}, ${team}.`;
    }
  }

  return (
    <div className="sr-only" aria-live="polite" aria-atomic="true">
      {text}
    </div>
  );
}
