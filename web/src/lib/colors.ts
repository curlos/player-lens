/** Rating colors (specs/frontend.md, "Selection and visual rules"). */

const DEFAULT = ["#E5484D", "#F97316", "#EAB308", "#84CC16", "#16A34A"]; // red, orange, yellow, light green, green
const COLORBLIND = ["#1D4ED8", "#60A5FA", "#CBD5E1", "#FDBA74", "#EA580C"]; // blue to orange

/** Band index: <5.0, 5.0-5.9, 6.0-6.9, 7.0-7.9, 8.0+ (on the displayed one-decimal value). */
export function ratingBand(r: number): number {
  const v = Math.round(r * 10) / 10;
  if (v < 5) return 0;
  if (v < 6) return 1;
  if (v < 7) return 2;
  if (v < 8) return 3;
  return 4;
}

/**
 * Colour of a rating change (log, full-time moments, pitch pops): green for a gain and red for a
 * loss, or blue and orange with Colorblind colors on. The sign is always shown too. `light` gives
 * the paler shades used on the dark pitch.
 */
export function deltaColor(delta: number, colorblind: boolean, light = false): string {
  if (colorblind) return delta > 0 ? (light ? "#93C5FD" : "#60A5FA") : light ? "#FDBA74" : "#FB923C";
  return delta > 0 ? (light ? "#86EFAC" : "#4ADE80") : light ? "#FCA5A5" : "#F87171";
}

export function ratingColor(r: number, colorblind: boolean): string {
  return (colorblind ? COLORBLIND : DEFAULT)[ratingBand(r)];
}

/** Text color that stays readable on the pill color. */
export function ratingTextColor(r: number, colorblind: boolean): string {
  const band = ratingBand(r);
  if (colorblind) return band === 0 || band === 4 ? "#fff" : "#111";
  return band === 0 ? "#fff" : "#111";
}
