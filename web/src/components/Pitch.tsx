/**
 * The SVG pitch (viewBox 0 0 105 68, meters). React renders the structure once per match and
 * selection; a frame listener then moves dots and tags by writing SVG attributes on refs, so
 * nothing re-renders per frame (specs/frontend.md, "Performance and robustness").
 *
 * Layer order: markings, trail, selected name tag (under all dots), action visuals, dots,
 * ball, referee, activity labels and rating pills, pops and captions, hover tag (above all).
 *
 * Keyboard: the pitch is one tab stop, a listbox of players. Arrow keys move a keyboard focus to
 * the nearest player in that direction (aria-activedescendant, so screen readers announce them);
 * Enter or Space follows that player; Home goes back to the player being followed.
 */
import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useClock } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { ratingColor, ratingTextColor } from "../lib/colors";
import {
  BALL_R,
  COLORS,
  DOT_R,
  KEEPER_COLORS,
  REF_HALF,
  SENT_OFF_FADE_S,
  SPOTLIGHT_DIM,
  SPOTLIGHT_MIN_IMPORTANCE,
  SPOTLIGHT_FADE_MS,
  SPOTLIGHT_MOMENT_FADE_S,
  SPOTLIGHT_MOMENT_S,
  SPOTLIGHT_ON_SELECT_MS,
  TRAIL_S,
  ARROW_NEAREST,
  ARROW_NEAR_MAX_DIST,
  MOTION_MIN_SPEED,
} from "../lib/config";
import { ratingLabel } from "../lib/format";
import { footballPatches } from "../lib/football";
import { activityAt, nearestInDirection, positionAt, ratingAt, type MatchData, type Track } from "../lib/match";
import { PitchMarkings } from "./PitchMarkings";
import { PitchOverlays } from "./PitchOverlays";

interface Props {
  match: MatchData;
  /** Full time: the pitch dims under the full-time card. */
  dimmed: boolean;
}

interface DotRefs {
  g: SVGGElement | null;
  label: SVGTextElement | null;
  pill: SVGGElement | null;
  pillRect: SVGRectElement | null;
  pillText: SVGTextElement | null;
  /** Movement arc: a path on the dot's front edge, rotated to the direction of travel. */
  motion: SVGPathElement | null;
  lastLabel: string;
  lastPill: string;
}

const TAG_FONT = 1.45;

/**
 * A movement arrow for a player at (x, y): a small, sharp, filled triangle growing out of a circle
 * of radius `r` (the dot's outline, or the lime ring), pointing where the player is heading over
 * their last second of movement. Its two base corners sit on that circle, so it reads as part of
 * the outline. Returns null below MOTION_MIN_SPEED. Drawn facing +x; callers rotate it by `angle`.
 */
function movementArrow(track: Track, x: number, y: number, t: number, seconds: number, r = DOT_R) {
  const [px, py] = positionAt(track, Math.max(0, t - 1), seconds);
  const vx = x - px;
  const vy = y - py;
  if (Math.hypot(vx, vy) < MOTION_MIN_SPEED) return null; // m/s
  const half = 0.42; // half the base width, m
  const base = Math.sqrt(r * r - half * half); // base corners on the circle
  const tip = r + 0.62;
  return {
    angle: ((Math.atan2(vy, vx) * 180) / Math.PI).toFixed(1),
    d: `M ${base.toFixed(3)} -${half} L ${tip.toFixed(3)} 0 L ${base.toFixed(3)} ${half} Z`,
  };
}

/** Rough text width in meters for the tag font (measured once in the browser would be nicer; good enough). */
const textWidth = (s: string, font = TAG_FONT) => s.length * font * 0.56;

export function Pitch({ match, dimmed }: Props) {
  const clock = useClock();
  const { selected, select, showRatings, colorblind, activityLabels, allArrows } = useSettings();
  const [hovered, setHovered] = useState<string | null>(null);
  // the player under keyboard focus (not yet followed); shows the same tag as a mouse hover
  const [kbFocus, setKbFocus] = useState<string | null>(null);
  const tagFor = hovered ?? kbFocus;

  const playerIds = useMemo(() => match.meta.entity_order.filter((id) => id !== "ball" && id !== "ref"), [match]);
  const dots = useRef(new Map<string, DotRefs>());
  // One stable set of ref callbacks per player. Inline callbacks re-run on every render (detach,
  // then attach), and React attaches a child's ref before its parent's, so each callback creates
  // the entry it needs instead of relying on the <g> ref having run first.
  const dotRefs = useMemo(() => {
    const entry = (id: string): DotRefs => {
      let d = dots.current.get(id);
      if (!d) {
        d = { g: null, label: null, pill: null, pillRect: null, pillText: null, motion: null, lastLabel: "", lastPill: "" };
        dots.current.set(id, d);
      }
      return d;
    };
    return new Map(
      playerIds.map((id) => [
        id,
        {
          g: (el: SVGGElement | null) => {
            entry(id).g = el;
          },
          label: (el: SVGTextElement | null) => {
            const d = entry(id);
            if (el) el.textContent = ""; // a fresh element starts empty, in step with the cache reset
            d.label = el;
            d.lastLabel = "";
          },
          pill: (el: SVGGElement | null) => {
            const d = entry(id);
            d.pill = el;
            d.lastPill = "";
          },
          pillRect: (el: SVGRectElement | null) => {
            entry(id).pillRect = el;
          },
          pillText: (el: SVGTextElement | null) => {
            entry(id).pillText = el;
          },
          motion: (el: SVGPathElement | null) => {
            entry(id).motion = el;
          },
        },
      ]),
    );
  }, [playerIds]);
  const ballRef = useRef<SVGGElement>(null);
  const ballPatches = useMemo(() => footballPatches(BALL_R), []);
  const refereeRef = useRef<SVGGElement>(null);
  const ringRef = useRef<SVGCircleElement>(null);
  const nameTagRef = useRef<SVGGElement>(null);
  const trailRefs = useRef<(SVGLineElement | null)[]>([]);
  const hoverRef = useRef<SVGGElement>(null);
  const kbRingRef = useRef<SVGCircleElement>(null);
  const selArrowRef = useRef<SVGPathElement>(null);
  const hoverRatingRect = useRef<SVGRectElement>(null);
  const hoverRatingText = useRef<SVGTextElement>(null);
  const tagRatingRect = useRef<SVGRectElement>(null);
  const tagRatingText = useRef<SVGTextElement>(null);
  const selectedAt = useRef(-Infinity);

  // Moments of the selected player that turn the spotlight on (goals, penalties, cards...).
  const bigMoments = useMemo(
    () =>
      match.events
        .filter((e) => e.importance >= SPOTLIGHT_MIN_IMPORTANCE && (e.player === selected || e.other === selected))
        .map((e) => e.t),
    [match, selected],
  );

  // A click on a player spotlights them briefly (not the default selection on load). A layout
  // effect declared before the drawing one, so the redraw for the new selection already sees the
  // spotlight (also while paused). The others then ease back to full color.
  // Compares with the previous selection rather than a "first run" flag: StrictMode runs mount
  // effects twice in dev, which defeated the flag and dimmed everyone on load.
  const lastSelected = useRef(selected);
  const redraw = useRef<(t: number) => void>(() => {});
  useLayoutEffect(() => {
    if (lastSelected.current === selected) return;
    lastSelected.current = selected;
    selectedAt.current = performance.now();
    // While paused nothing redraws, so animate the fade-back here until it has finished.
    const end = selectedAt.current + SPOTLIGHT_ON_SELECT_MS + SPOTLIGHT_FADE_MS + 50;
    let raf = 0;
    const tick = () => {
      if (!clock.getState().playing) redraw.current(clock.t);
      if (performance.now() < end) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [selected, clock]);

  useLayoutEffect(() => {
    const ballTrack = match.tracks.get("ball")!;
    const refTrack = match.tracks.get("ref")!;
    const selTrack = match.tracks.get(selected);
    let lastHoverRating = "";
    let lastTagRating = "";
    // pill colors are cached by label text; a palette or visibility change must repaint them all
    for (const d of dots.current.values()) d.lastPill = "";

    const draw = (t: number) => {
      // Spotlight strength, 1 = fully dimmed others, 0 = normal view. It switches on at once and
      // eases out: after a click over SPOTLIGHT_FADE_MS of real time, after a big moment over the
      // last SPOTLIGHT_MOMENT_FADE_S match seconds.
      const sinceClick = performance.now() - selectedAt.current;
      const clickStrength = Math.min(1, Math.max(0, 1 - (sinceClick - SPOTLIGHT_ON_SELECT_MS) / SPOTLIGHT_FADE_MS));
      let momentStrength = 0;
      for (const m of bigMoments) {
        if (t < m || t - m > SPOTLIGHT_MOMENT_S) continue;
        momentStrength = Math.max(momentStrength, Math.min(1, (SPOTLIGHT_MOMENT_S - (t - m)) / SPOTLIGHT_MOMENT_FADE_S));
      }
      const strength = Math.max(clickStrength, momentStrength);
      const dimmedOpacity = 1 - (1 - SPOTLIGHT_DIM) * strength;

      // the players nearest the followed one (within ARROW_NEAR_MAX_DIST) get movement arrows
      const near = new Set<string>();
      if (selTrack) {
        const [sx0, sy0] = positionAt(selTrack, t, match.seconds);
        playerIds
          .filter((id) => {
            const off = match.sentOff.get(id);
            return id !== selected && !(off && t > off.stopT + SENT_OFF_FADE_S);
          })
          .map((id) => {
            const [x, y] = positionAt(match.tracks.get(id)!, t, match.seconds);
            return { id, dist: Math.hypot(x - sx0, y - sy0) };
          })
          .filter((c) => c.dist <= ARROW_NEAR_MAX_DIST)
          .sort((a, b) => a.dist - b.dist)
          .slice(0, ARROW_NEAREST)
          .forEach((c) => near.add(c.id));
      }

      for (const id of playerIds) {
        const d = dots.current.get(id);
        const track = match.tracks.get(id);
        if (!d?.g || !track) continue;
        const [x, y] = positionAt(track, t, match.seconds);
        d.g.setAttribute("transform", `translate(${x.toFixed(2)} ${y.toFixed(2)})`);

        let opacity = id !== selected ? dimmedOpacity : 1;
        const off = match.sentOff.get(id);
        if (off && t > off.stopT) opacity *= Math.max(0, 1 - (t - off.stopT) / SENT_OFF_FADE_S);
        d.g.setAttribute("opacity", opacity.toFixed(2));
        d.g.style.pointerEvents = opacity === 0 ? "none" : "auto";

        if (d.motion) {
          // the followed player's arrow is drawn separately, in lime, above every dot
          const arrow = id !== selected && (allArrows || near.has(id)) && opacity > 0 ? movementArrow(track, x, y, t, match.seconds) : null;
          d.motion.setAttribute("display", arrow ? "inline" : "none");
          if (arrow) {
            d.motion.setAttribute("transform", `rotate(${arrow.angle})`);
            d.motion.setAttribute("d", arrow.d);
          }
        }

        if (d.label) {
          const act = activityAt(match, id, t);
          let text = "";
          if (act === "celebrate") text = "Celebrating";
          // activity text only with the Activity labels setting on (not even for the followed player)
          else if (act && activityLabels) text = act.replace(/_/g, " ");
          if (text !== d.lastLabel) {
            d.label.textContent = text;
            d.lastLabel = text;
          }
        }

        if (d.pill && d.pillRect && d.pillText) {
          // the selected player's rating sits in the name tag instead
          const show = showRatings && id !== selected;
          d.pill.setAttribute("visibility", show ? "visible" : "hidden");
          if (show) {
            const r = ratingAt(match, id, t);
            const label = ratingLabel(r);
            if (label !== d.lastPill) {
              d.pillText.textContent = label;
              d.pillRect.setAttribute("fill", ratingColor(r, colorblind));
              d.pillText.setAttribute("fill", ratingTextColor(r, colorblind));
              d.lastPill = label;
            }
          }
        }
      }

      // the ball at its true position (interpolated like every entity)
      const [bx, by] = positionAt(ballTrack, t, match.seconds);
      ballRef.current?.setAttribute("transform", `translate(${bx.toFixed(2)} ${by.toFixed(2)})`);

      const [rx, ry] = positionAt(refTrack, t, match.seconds);
      refereeRef.current?.setAttribute("transform", `translate(${rx.toFixed(2)} ${ry.toFixed(2)})`);
      refereeRef.current?.setAttribute("opacity", dimmedOpacity.toFixed(2));

      if (selTrack) {
        const [sx, sy] = positionAt(selTrack, t, match.seconds);
        const off = match.sentOff.get(selected);
        const gone = off && t > off.stopT + SENT_OFF_FADE_S;
        ringRef.current?.setAttribute("cx", sx.toFixed(2));
        ringRef.current?.setAttribute("cy", sy.toFixed(2));
        ringRef.current?.setAttribute("visibility", gone ? "hidden" : "visible");
        // grows out of the lime ring (r = DOT_R + 0.5)
        const selArrow = gone ? null : movementArrow(selTrack, sx, sy, t, match.seconds, DOT_R + 0.5);
        if (selArrowRef.current) {
          selArrowRef.current.setAttribute("display", selArrow ? "inline" : "none");
          if (selArrow) {
            selArrowRef.current.setAttribute("transform", `translate(${sx.toFixed(2)} ${sy.toFixed(2)}) rotate(${selArrow.angle})`);
            selArrowRef.current.setAttribute("d", selArrow.d);
          }
        }
        nameTagRef.current?.setAttribute("transform", `translate(${sx.toFixed(2)} ${sy.toFixed(2)})`);
        nameTagRef.current?.setAttribute("visibility", gone ? "hidden" : "visible");
        const r = ratingAt(match, selected, t);
        const label = ratingLabel(r);
        if (label !== lastTagRating && tagRatingText.current && tagRatingRect.current) {
          tagRatingText.current.textContent = label;
          tagRatingText.current.setAttribute("fill", ratingTextColor(r, colorblind));
          tagRatingRect.current.setAttribute("fill", ratingColor(r, colorblind));
          lastTagRating = label;
        }
        // one fading trail: segments from TRAIL_S seconds ago up to now
        let prev: [number, number] = [sx, sy];
        for (let k = 0; k < TRAIL_S; k++) {
          const seg = trailRefs.current[k];
          if (!seg) continue;
          const p = positionAt(selTrack, Math.max(0, Math.floor(t) - k), match.seconds);
          seg.setAttribute("x1", prev[0].toFixed(2));
          seg.setAttribute("y1", prev[1].toFixed(2));
          seg.setAttribute("x2", p[0].toFixed(2));
          seg.setAttribute("y2", p[1].toFixed(2));
          seg.setAttribute("visibility", gone ? "hidden" : "visible");
          prev = p;
        }
      }

      if (kbFocus && kbRingRef.current) {
        const track = match.tracks.get(kbFocus);
        if (track) {
          const [kx, ky] = positionAt(track, t, match.seconds);
          kbRingRef.current.setAttribute("cx", kx.toFixed(2));
          kbRingRef.current.setAttribute("cy", ky.toFixed(2));
        }
      }

      if (tagFor && hoverRef.current) {
        const track = match.tracks.get(tagFor);
        if (track) {
          const [hx, hy] = positionAt(track, t, match.seconds);
          hoverRef.current.setAttribute("transform", `translate(${hx.toFixed(2)} ${hy.toFixed(2)})`);
          const r = ratingAt(match, tagFor, t);
          const label = ratingLabel(r);
          if (label !== lastHoverRating && hoverRatingText.current && hoverRatingRect.current) {
            hoverRatingText.current.textContent = label;
            hoverRatingText.current.setAttribute("fill", ratingTextColor(r, colorblind));
            hoverRatingRect.current.setAttribute("fill", ratingColor(r, colorblind));
            lastHoverRating = label;
          }
        }
      }
    };
    redraw.current = draw;
    return clock.subscribeFrame(draw);
  }, [clock, match, playerIds, selected, bigMoments, showRatings, colorblind, activityLabels, allArrows, tagFor, kbFocus]);

  /** Players still on the pitch at the current time (a sent-off player who has faded out is skipped). */
  const visibleAt = (t: number) =>
    playerIds.filter((id) => {
      const off = match.sentOff.get(id);
      return !(off && t > off.stopT + SENT_OFF_FADE_S);
    });

  const onPitchKey = (e: KeyboardEvent<SVGSVGElement>) => {
    // A mouse click also focuses the pitch; then the keys keep their playback meaning (arrows seek,
    // Space pauses). Player navigation only runs when the pitch was reached with Tab, which is what
    // starts the keyboard focus (checking :focus-visible here is too late: any key press turns it on).
    if (!kbFocus) return;
    const dirs: Record<string, [number, number]> = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
    const from = kbFocus ?? selected;
    if (e.key in dirs) {
      e.preventDefault();
      e.stopPropagation(); // on the pitch, arrows move between players instead of seeking
      const next = nearestInDirection(match, from, visibleAt(clock.t), dirs[e.key], clock.t);
      if (next) setKbFocus(next);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation(); // Space follows the player here instead of pausing
      select(from);
    } else if (e.key === "Home") {
      e.preventDefault();
      e.stopPropagation();
      setKbFocus(selected);
    }
  };

  const sel = match.players.get(selected);
  const selName = sel?.name ?? "";
  const selNum = sel ? `#${sel.number}` : "";
  const nameW = textWidth(`${selName} ${selNum}`);
  const tagW = nameW + 5.6;

  const hov = tagFor ? match.players.get(tagFor) : undefined;
  const hovText = hov ? `#${hov.number} ${hov.name} · ${hov.slot} · OVR ${hov.ovr}` : "";
  const hovW = textWidth(hovText, 1.25) + 6.2;

  return (
    <svg
      viewBox="0 0 105 68"
      overflow="visible"
      className={`block h-full w-full select-none transition-opacity duration-700 ${dimmed ? "opacity-40" : ""}`}
      tabIndex={0}
      role="listbox"
      aria-label={`Pitch. Following ${selName} ${selNum}. Arrow keys move between nearby players, Enter follows the highlighted player, Home goes back.`}
      aria-activedescendant={kbFocus ? `pitch-dot-${kbFocus}` : undefined}
      onFocus={(e) => {
        // keyboard focus starts on the player being followed; a mouse click doesn't start it
        if (e.target === e.currentTarget && e.currentTarget.matches(":focus-visible")) setKbFocus(selected);
      }}
      onBlur={() => setKbFocus(null)}
      onKeyDown={onPitchKey}
      onPointerLeave={() => setHovered(null)}
    >
      <PitchMarkings />

      {/* trail */}
      <g pointerEvents="none" aria-hidden="true">
        {Array.from({ length: TRAIL_S }, (_, k) => (
          <line
            key={k}
            ref={(el) => {
              trailRefs.current[k] = el;
            }}
            stroke={COLORS.lime}
            strokeWidth={0.35 - k * 0.04}
            strokeLinecap="round"
            opacity={0.7 - k * 0.13}
          />
        ))}
      </g>

      {/* selected player's name tag: drawn under all dots */}
      <g ref={nameTagRef} pointerEvents="none" aria-hidden="true">
        <g transform={`translate(0 ${-DOT_R - 3.2})`}>
          <rect x={-tagW / 2} y={-1.4} width={tagW} height={2.8} rx={1.1} fill="rgba(24,24,27,0.82)" />
          <path d="M -0.7 1.4 L 0 2.2 L 0.7 1.4 Z" fill="rgba(24,24,27,0.82)" />
          <text x={-tagW / 2 + 1} dominantBaseline="central" fontSize={TAG_FONT} fill="#f4f4f5" fontWeight={500}>
            {selName} <tspan fill={COLORS.lime} fontWeight={700}>{selNum}</tspan>
          </text>
          <rect ref={tagRatingRect} x={tagW / 2 - 3.7} y={-0.9} width={3} height={1.8} rx={0.5} />
          <text ref={tagRatingText} x={tagW / 2 - 2.2} textAnchor="middle" dominantBaseline="central" fontSize={1.15} fontWeight={700} />
        </g>
      </g>

      {/* action visuals: drawn under and over the dots, ball and referee passed in as children */}
      <PitchOverlays match={match}>
        {/* players */}
        {playerIds.map((id) => {
          const p = match.players.get(id)!;
          const team = match.teams[p.team];
          const fill = p.isKeeper ? KEEPER_COLORS[p.team] : team.color;
          const refs = dotRefs.get(id)!;
          return (
            <g
              key={id}
              ref={refs.g}
              id={`pitch-dot-${id}`}
              role="option"
              aria-selected={id === selected}
              aria-label={`#${p.number} ${p.name}, ${team.name}, ${p.slot}, OVR ${p.ovr}, rating ${ratingLabel(ratingAt(match, id, clock.t))}`}
              className="cursor-pointer"
              onClick={() => select(id)}
              onPointerEnter={(e) => {
                if (e.pointerType !== "touch") setHovered(id);
              }}
              onPointerLeave={() => setHovered((h) => (h === id ? null : h))}
            >
              {/* movement arrow: a small white triangle growing out of the dot's white outline (drawn
                  before the dot, so the dot covers its base), rotated to the direction of travel */}
              <path ref={refs.motion} display="none" fill="#fff" pointerEvents="none" aria-hidden="true" />
              <circle r={DOT_R} fill={fill} stroke="#fff" strokeWidth={0.18} filter="url(#dot-shadow)" />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={1.55}
                fontWeight={700}
                fill={p.isKeeper ? "#18181b" : "#fff"}
                pointerEvents="none"
              >
                {p.number}
              </text>
              <text
                ref={refs.label}
                y={DOT_R + 1.3}
                textAnchor="middle"
                fontSize={1.05}
                fill="#fefce8"
                stroke="rgba(0,0,0,0.55)"
                strokeWidth={0.25}
                paintOrder="stroke"
                pointerEvents="none"
              />
              <g
                ref={refs.pill}
                transform={`translate(${DOT_R * 0.75} ${-DOT_R - 0.6})`}
                visibility="hidden"
                pointerEvents="none"
              >
                <rect
                  ref={refs.pillRect}
                  x={-1.25}
                  y={-0.7}
                  width={2.5}
                  height={1.4}
                  rx={0.4}
                />
                <text
                  ref={refs.pillText}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={1}
                  fontWeight={700}
                />
              </g>
            </g>
          );
        })}

        {/* selected ring: thin lime outline */}
        <circle ref={ringRef} r={DOT_R + 0.5} fill="none" stroke={COLORS.lime} strokeWidth={0.28} pointerEvents="none" aria-hidden="true" />
        {/* the followed player's movement arrow: a lime triangle growing out of the lime ring, above every dot */}
        <path ref={selArrowRef} display="none" fill={COLORS.lime} pointerEvents="none" aria-hidden="true" />
        {/* keyboard focus ring: dashed white, distinct from the lime selection ring */}
        {kbFocus && (
          <circle
            ref={kbRingRef}
            r={DOT_R + 1.1}
            fill="none"
            stroke="#fff"
            strokeWidth={0.3}
            strokeDasharray="0.9 0.6"
            pointerEvents="none"
            aria-hidden="true"
          />
        )}

        {/* the ball: a small football (same pattern as the site icon) with a soft shadow */}
        <g ref={ballRef} pointerEvents="none" aria-hidden="true">
          <circle r={BALL_R} fill="#fff" filter="url(#dot-shadow)" />
          <g clipPath="url(#ball-clip)" fill="#18181b">
            {ballPatches.map((d) => (
              <path key={d} d={d} />
            ))}
          </g>
          <circle r={BALL_R} fill="none" stroke="#18181b" strokeWidth={0.12} />
        </g>
        <g ref={refereeRef} pointerEvents="none" aria-hidden="true">
          <rect x={-REF_HALF} y={-REF_HALF} width={REF_HALF * 2} height={REF_HALF * 2} transform="rotate(45)" fill="#000" stroke="#fff" strokeWidth={0.15} />
        </g>
      </PitchOverlays>

      {/* hover tag: above everything, read-only */}
      {hov && (
        <g ref={hoverRef} pointerEvents="none" aria-hidden="true">
          <g transform={`translate(0 ${-DOT_R - 2.6})`}>
            <rect x={-hovW / 2} y={-1.25} width={hovW} height={2.5} rx={1} fill="rgba(24,24,27,0.92)" />
            <text x={-hovW / 2 + 0.9} dominantBaseline="central" fontSize={1.25} fill="#f4f4f5">
              {hovText}
            </text>
            <rect ref={hoverRatingRect} x={hovW / 2 - 3.6} y={-0.85} width={2.8} height={1.7} rx={0.45} />
            <text ref={hoverRatingText} x={hovW / 2 - 2.2} textAnchor="middle" dominantBaseline="central" fontSize={1.1} fontWeight={700} />
          </g>
        </g>
      )}

      <defs>
        <clipPath id="ball-clip">
          <circle r={BALL_R} />
        </clipPath>
        <filter id="dot-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="0.25" stdDeviation="0.3" floodColor="#000" floodOpacity="0.45" />
        </filter>
      </defs>
    </svg>
  );
}
