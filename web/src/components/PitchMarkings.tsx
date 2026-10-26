/** Pitch surface and Laws-of-the-Game markings in meters (ARCHITECTURE section 2). Static. */
import { memo } from "react";
import { COLORS } from "../lib/config";

const W = 105;
const H = 68;
const LINE = { stroke: "rgba(255,255,255,0.6)", strokeWidth: 0.15, fill: "none" } as const;

function Box({ left, depth, width }: { left: boolean; depth: number; width: number }) {
  const x = left ? 0 : W - depth;
  return <rect x={x} y={(H - width) / 2} width={depth} height={width} {...LINE} />;
}

function Arc({ left }: { left: boolean }) {
  // the "D": the part of the 9.15 m circle around the penalty spot that lies outside the area
  const spotX = left ? 11 : W - 11;
  const edge = left ? 16.5 : W - 16.5;
  const dy = Math.sqrt(9.15 ** 2 - (edge - spotX) ** 2);
  return <path d={`M ${edge} ${H / 2 - dy} A 9.15 9.15 0 0 ${left ? 1 : 0} ${edge} ${H / 2 + dy}`} {...LINE} />;
}

export const PitchMarkings = memo(function PitchMarkings() {
  const stripes = Array.from({ length: 14 }, (_, i) => i);
  return (
    <g pointerEvents="none" aria-hidden="true">
      <rect x={-4} y={-4} width={W + 8} height={H + 8} fill={COLORS.pitch} />
      {stripes.map((i) => (
        <rect key={i} x={i * 7.5} y={0} width={7.5} height={H} fill={i % 2 ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.04)"} />
      ))}
      <rect x={0} y={0} width={W} height={H} {...LINE} />
      <line x1={W / 2} y1={0} x2={W / 2} y2={H} {...LINE} />
      <circle cx={W / 2} cy={H / 2} r={9.15} {...LINE} />
      <circle cx={W / 2} cy={H / 2} r={0.3} fill="rgba(255,255,255,0.6)" />
      {[true, false].map((left) => (
        <g key={String(left)}>
          <Box left={left} depth={16.5} width={40.32} />
          <Box left={left} depth={5.5} width={18.32} />
          <circle cx={left ? 11 : W - 11} cy={H / 2} r={0.3} fill="rgba(255,255,255,0.6)" />
          <Arc left={left} />
          <rect x={left ? -1.6 : W} y={(H - 7.32) / 2} width={1.6} height={7.32} {...LINE} />
        </g>
      ))}
      {[
        [0, 0, 0],
        [W, 0, 90],
        [W, H, 180],
        [0, H, 270],
      ].map(([x, y, rot]) => (
        <path key={`${x}-${y}`} d="M 1 0 A 1 1 0 0 1 0 1" transform={`translate(${x} ${y}) rotate(${rot})`} {...LINE} />
      ))}
    </g>
  );
});
