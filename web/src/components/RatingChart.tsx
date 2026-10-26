/**
 * Rating line chart for the selected player, from kickoff (6.0) to now. Hover (or touch) shows
 * the minute and the rating at that point, using the same minute format as the rating log.
 *
 * The SVG stretches to the card's width (preserveAspectRatio "none"), which would distort text and
 * circles, so only lines and the area are SVG; the end dot and the tooltip are HTML placed by
 * percentage. The 6.0 label sits in its own column left of the plot, so the line never touches it.
 */
import { useState, type PointerEvent } from "react";
import { useMatchTime } from "../hooks/useClock";
import { COLORS } from "../lib/config";
import { lastIndexAtOrBefore, minuteLabel, ratingLabel } from "../lib/format";
import { ratingAt, type MatchData } from "../lib/match";

const W = 200;
const H = 54;
const Y_MIN = 4;
const Y_MAX = 10;

export function RatingChart({ match, player }: { match: MatchData; player: string }) {
  const t = useMatchTime(4);
  const [hoverFrac, setHoverFrac] = useState<number | null>(null);
  const log = match.ratingLog.get(player) ?? [];
  const end = lastIndexAtOrBefore(log, t);
  const span = Math.max(t, 60);
  const x = (s: number) => (s / span) * W;
  const y = (r: number) => H - ((Math.min(Y_MAX, Math.max(Y_MIN, r)) - Y_MIN) / (Y_MAX - Y_MIN)) * H;
  const pctX = (s: number) => `${(x(s) / W) * 100}%`;
  const pctY = (r: number) => `${(y(r) / H) * 100}%`;

  let prev = match.ratingStart;
  const pts: string[] = [`0,${y(prev).toFixed(1)}`];
  for (let i = 0; i <= end; i++) {
    const e = log[i];
    pts.push(`${x(e.t).toFixed(1)},${y(prev).toFixed(1)}`, `${x(e.t).toFixed(1)},${y(e.rating_after).toFixed(1)}`);
    prev = e.rating_after;
  }
  const now = ratingAt(match, player, t);
  pts.push(`${x(t).toFixed(1)},${y(now).toFixed(1)}`);
  const base = y(match.ratingStart);

  // the hovered point, clamped to the part of the match already played
  const hoverT = hoverFrac == null ? null : Math.min(hoverFrac * span, t);
  const hoverR = hoverT == null ? null : ratingAt(match, player, hoverT);

  const track = (e: PointerEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    setHoverFrac(Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)));
  };

  return (
    <div className="flex h-14 w-full gap-1.5">
      <div className="relative w-6 shrink-0" aria-hidden="true">
        <span className="absolute right-0 -translate-y-1/2 text-xs leading-none tabular-nums text-zinc-400" style={{ top: pctY(match.ratingStart) }}>
          {ratingLabel(match.ratingStart)}
        </span>
      </div>
      <div
        className="relative h-full min-w-0 flex-1 touch-none select-none"
        onPointerMove={track}
        onPointerDown={track}
        onPointerLeave={() => setHoverFrac(null)}
        role="img"
        aria-label={`Rating over time: ${ratingLabel(match.ratingStart)} at kickoff, ${ratingLabel(now)} now`}
      >
        <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full overflow-visible" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="rating-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={COLORS.lime} stopOpacity="0.25" />
              <stop offset="1" stopColor={COLORS.lime} stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1={0} x2={W} y1={base} y2={base} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
          <polygon points={`0,${H} ${pts.join(" ")} ${x(t).toFixed(1)},${H}`} fill="url(#rating-fill)" />
          <polyline points={pts.join(" ")} fill="none" stroke={COLORS.lime} strokeWidth={1.6} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          {hoverT != null && (
            <line x1={x(hoverT)} x2={x(hoverT)} y1={0} y2={H} stroke="rgba(255,255,255,0.35)" vectorEffect="non-scaling-stroke" />
          )}
        </svg>

        <span
          className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: pctX(t), top: pctY(now), background: COLORS.lime }}
          aria-hidden="true"
        />

        {hoverT != null && hoverR != null && (
          <>
            <span
              className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-zinc-900 bg-white"
              style={{ left: pctX(hoverT), top: pctY(hoverR) }}
              aria-hidden="true"
            />
            <span
              className="pointer-events-none absolute -top-1 z-10 whitespace-nowrap rounded bg-zinc-800 px-1.5 py-0.5 text-xs tabular-nums text-zinc-100 shadow"
              style={{
                left: pctX(hoverT),
                // keep the tooltip inside the card at both ends
                transform: `translate(${hoverT / span < 0.15 ? "0" : hoverT / span > 0.85 ? "-100%" : "-50%"}, -100%)`,
              }}
            >
              {minuteLabel(hoverT)} · {ratingLabel(hoverR)}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
