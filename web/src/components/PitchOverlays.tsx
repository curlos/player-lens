/**
 * Brief fading action visuals on the pitch (specs/frontend.md, "Selection and visual rules"):
 * pass line, shot line with speed pop, tackle flash, pressure pulse, card caption, xG chip at a
 * penalty, rating pops. Re-rendered at ~20 Hz from the clock; every element is derived from
 * events in a short window before t, so seeking is always correct. One component draws both
 * layers around the dots (passed as children), so there is one clock subscription and one window
 * scan per tick; the children element is unchanged between ticks, so React skips it.
 */
import { useMemo, type ReactNode } from "react";
import { useMatchTime } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { deltaColor } from "../lib/colors";
import { DOT_R, POP_MIN_DELTA_OTHERS, VISUAL_S } from "../lib/config";
import { deltaLabel, lastIndexAtOrBefore } from "../lib/format";
import { eventsInWindow, goalRevealT, positionAt, shownAt, type MatchData } from "../lib/match";
import type { MatchEvent } from "../types";

interface Props {
  match: MatchData;
  /** The dots layer: drawn between the "under" visuals (lines, flashes) and the "over" ones (chips, pops). */
  children: ReactNode;
}

// +1: a goal's visuals start up to a second after its time (ball in flight)
const WINDOW = Math.max(...Object.values(VISUAL_S)) + 1;
const FLASH_TYPES = new Set(["tackle", "interception", "block", "clearance", "save", "gk_claim", "gk_sweep", "aerial_duel"]);
const PULSE_TYPES = new Set(["pressure", "counterpress", "pressure_regain"]);

/** 1 at the event, fading to 0 after `span` seconds. */
const fade = (t: number, at: number, span: number) => Math.max(0, 1 - (t - at) / span);

function Chip({ x, y, text, fill, color, size = 1.2, opacity = 1 }: { x: number; y: number; text: string; fill: string; color: string; size?: number; opacity?: number }) {
  const w = text.length * size * 0.58 + 1.4;
  return (
    <g transform={`translate(${x} ${y})`} opacity={opacity}>
      <rect x={-w / 2} y={-size} width={w} height={size * 2} rx={size * 0.4} fill={fill} stroke="rgba(0,0,0,0.25)" strokeWidth={0.08} />
      <text textAnchor="middle" dominantBaseline="central" fontSize={size} fontWeight={700} fill={color}>
        {text}
      </text>
    </g>
  );
}

export function PitchOverlays({ match, children }: Props) {
  const t = useMatchTime(20);
  const { selected, colorblind } = useSettings();
  const recent = eventsInWindow(match, t, WINDOW);

  // Penalty kicks: the award and the kick that follows it, for the xG chip on the spot.
  const penalties = useMemo(() => {
    const out: { award: MatchEvent; kick: MatchEvent | undefined }[] = [];
    for (const e of match.events) {
      if (e.type !== "penalty") continue;
      const kick = match.events.find((k) => k.type === "shot" && k.t > e.t && k.team === e.team && k.t - e.t < 90);
      out.push({ award: e, kick });
    }
    return out;
  }, [match]);

  const at = (id: string): [number, number] | null => {
    const track = match.tracks.get(id);
    return track ? positionAt(track, t, match.seconds) : null;
  };

  const under = (
    <g pointerEvents="none" aria-hidden="true">
      {recent.map((e) => {
        if ((e.type === "pass" || e.type === "key_pass") && e.from && e.to) {
          const o = fade(t, e.t, VISUAL_S.pass);
          if (!o) return null;
          return (
            <line
              key={e.id}
              x1={e.from.x}
              y1={e.from.y}
              x2={e.to.x}
              y2={e.to.y}
              stroke="#fff"
              strokeWidth={0.22}
              strokeDasharray="0.7 0.6"
              opacity={0.75 * o}
            />
          );
        }
        if (e.type === "shot" && e.from && e.to) {
          const o = fade(t, e.t, VISUAL_S.shot);
          if (!o) return null;
          return <line key={e.id} x1={e.from.x} y1={e.from.y} x2={e.to.x} y2={e.to.y} stroke="#fff" strokeWidth={0.3} opacity={0.9 * o} />;
        }
        if (FLASH_TYPES.has(e.type) && e.from) {
          const o = fade(t, e.t, VISUAL_S.flash);
          if (!o) return null;
          return <circle key={e.id} cx={e.from.x} cy={e.from.y} r={1.2 + (1 - o) * 2.2} fill="rgba(255,255,255,0.25)" stroke="#fff" strokeWidth={0.15} opacity={o} />;
        }
        if (PULSE_TYPES.has(e.type)) {
          const o = fade(t, e.t, VISUAL_S.pulse);
          const p = at(e.player);
          if (!o || !p) return null;
          const color = match.teams[e.team].color;
          return <circle key={e.id} cx={p[0]} cy={p[1]} r={DOT_R + (1 - o) * 2.5} fill="none" stroke={color} strokeWidth={0.25} opacity={0.8 * o} />;
        }
        return null;
      })}
      {/* goal net flash on the goal that was scored */}
      {recent
        .filter((e) => e.type === "goal" && t >= goalRevealT(match, e) && t - goalRevealT(match, e) <= VISUAL_S.goalBanner)
        .map((e) => {
          const right = e.team === "azc";
          return (
            <rect
              key={`net-${e.id}`}
              x={right ? 105 : -1.6}
              y={(68 - 7.32) / 2}
              width={1.6}
              height={7.32}
              fill="rgba(255,255,255,0.35)"
              stroke="#fff"
              strokeWidth={0.15}
              opacity={fade(t, goalRevealT(match, e), VISUAL_S.goalBanner)}
            />
          );
        })}
    </g>
  );

  // "over" layer: captions, chips and pops
  const pops = (() => {
    const out = [];
    const end = lastIndexAtOrBefore(match.ratingChanges, t);
    // look one second further back: changes in a goal's second pop when the ball lands (shownAt)
    for (let i = end; i >= 0 && match.ratingChanges[i].t > t - VISUAL_S.ratingPop - 1; i--) {
      const r = match.ratingChanges[i];
      const shown = shownAt(match, r.t);
      if (shown > t || t - shown > VISUAL_S.ratingPop) continue;
      if (r.player === selected || Math.abs(r.delta) >= POP_MIN_DELTA_OTHERS) out.push({ ...r, t: shown });
    }
    return out;
  })();

  // Cards come from the highlights, where a second yellow is already merged into its red.
  const cards = match.highlights.filter(
    (h) => (h.kind === "yellow" || h.kind === "red") && h.t <= t && t - h.t <= VISUAL_S.cardCaption,
  );

  const over = (
    <g pointerEvents="none" aria-hidden="true">
      {recent.map((e) => {
        if (e.type === "shot" && e.from && e.to && e.speed_kmh != null) {
          const o = fade(t, e.t, VISUAL_S.shot);
          if (!o) return null;
          return (
            <Chip
              key={`spd-${e.id}`}
              x={(e.from.x + e.to.x) / 2}
              y={(e.from.y + e.to.y) / 2 - 1.6}
              text={`${Math.round(e.speed_kmh)} km/h`}
              fill="#f4f4f5"
              color="#18181b"
              opacity={Math.min(1, o * 2)}
            />
          );
        }
        return null;
      })}

      {cards.map((h) => {
        const p = at(h.player);
        const pl = match.players.get(h.player);
        if (!p || !pl) return null;
        const red = h.kind === "red";
        const o = Math.min(1, fade(t, h.t, VISUAL_S.cardCaption) * 3);
        const caption = `${red ? "Red" : "Yellow"} card - ${pl.abbr} #${pl.number}`;
        const w = caption.length * 0.62 + 1.6;
        return (
          <g key={`card-${h.id}`} opacity={o}>
            <rect x={p[0] + DOT_R + 0.6} y={p[1] - 2.6} width={1.4} height={2} rx={0.15} fill={red ? "#EF4444" : "#FACC15"} transform={`rotate(8 ${p[0] + DOT_R + 1.3} ${p[1] - 1.6})`} />
            <g transform={`translate(${p[0]} ${p[1] + DOT_R + 2.6})`}>
              <rect x={-w / 2} y={-1.1} width={w} height={2.2} rx={0.9} fill="rgba(24,24,27,0.9)" />
              <text textAnchor="middle" dominantBaseline="central" fontSize={1.1} fill="#f4f4f5">
                {red ? "Red" : "Yellow"} card -{" "}
                <tspan fill={red ? "#FCA5A5" : "#FDE047"} fontWeight={700}>
                  {pl.abbr} #{pl.number}
                </tspan>
              </text>
            </g>
          </g>
        );
      })}

      {penalties.map(({ award, kick }) => {
        const until = (kick?.t ?? award.t + 30) + 2;
        if (t < award.t || t > until || kick?.xg == null) return null;
        const spotX = award.team === "azc" ? 105 - 11 : 11;
        return <Chip key={`xg-${award.id}`} x={spotX} y={34 + 2.4} text={`xG ${kick.xg.toFixed(2)}`} fill="rgba(24,24,27,0.9)" color="#f4f4f5" size={1.05} />;
      })}

      {pops.map((r, i) => {
        const p = at(r.player);
        if (!p) return null;
        const o = fade(t, r.t, VISUAL_S.ratingPop);
        const rise = (1 - o) * 1.2;
        const big = r.delta >= 0.3;
        const isSel = r.player === selected;
        // several changes in the same second (shot on target + goal) stack instead of overlapping
        const stack = pops.slice(0, i).filter((q) => q.player === r.player).length;
        const y = p[1] - DOT_R - (isSel ? 6.2 : 1.6) - rise - stack * 2.4;
        if (big) return <Chip key={r.id} x={p[0]} y={y} text={`★ ${deltaLabel(r.delta)}`} fill="#EAB308" color="#18181b" size={1.3} opacity={Math.min(1, o * 2)} />;
        return (
          <text
            key={r.id}
            x={p[0] + (isSel ? 0 : DOT_R)}
            y={y}
            textAnchor="middle"
            fontSize={isSel ? 1.25 : 1}
            fontWeight={700}
            fill={deltaColor(r.delta, colorblind, true)}
            stroke="rgba(0,0,0,0.6)"
            strokeWidth={0.2}
            paintOrder="stroke"
            opacity={Math.min(1, o * 2)}
          >
            {deltaLabel(r.delta)}
          </text>
        );
      })}
    </g>
  );

  return (
    <>
      {under}
      {children}
      {over}
    </>
  );
}
