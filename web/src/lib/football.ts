/** The football drawn on the pitch (and in the site icon): pattern geometry only. */

/** A regular pentagon path (circumradius r, first vertex at `rotDeg`). */
function pentagon(cx: number, cy: number, r: number, rotDeg: number): string {
  const pts = Array.from({ length: 5 }, (_, k) => {
    const a = ((rotDeg + 72 * k) * Math.PI) / 180;
    return `${(cx + r * Math.cos(a)).toFixed(3)} ${(cy + r * Math.sin(a)).toFixed(3)}`;
  });
  return `M${pts.join(" L")} Z`;
}

/**
 * The classic football pattern for a ball of radius R centred on 0,0: a dark centre pentagon plus
 * five dark pentagons cut by the ball's edge (clip the result to the ball's circle). Same design
 * as the site icon.
 */
export function footballPatches(R: number): string[] {
  const outer = Array.from({ length: 5 }, (_, k) => {
    const a = -90 + 36 + 72 * k;
    const rad = (a * Math.PI) / 180;
    return pentagon(R * 0.98 * Math.cos(rad), R * 0.98 * Math.sin(rad), R * 0.36, a + 180);
  });
  return [pentagon(0, 0, R * 0.36, -90), ...outer];
}
