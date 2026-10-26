/** Small pure formatters shared by the panels. */

/** Football minute for labels: an event at 87:12 is the 88th minute. */
export function minuteLabel(t: number): string {
  return `${Math.floor(t / 60) + 1}'`;
}

/** The same football minute in words, for screen readers ("39'" would be read as "39 apostrophe"). */
export function minuteSpoken(t: number): string {
  return `minute ${Math.floor(t / 60) + 1}`;
}

/** Match clock "mm:ss" (no stoppage time, so 90:00 is the last value). */
export function clockLabel(t: number): string {
  const s = Math.max(0, Math.floor(t));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Ratings show one decimal inside the 3.1 to 9.9 display range (PRODUCT, "Rating model"). */
export function ratingLabel(r: number): string {
  return Math.min(9.9, Math.max(3.1, r)).toFixed(1);
}

/** Signed delta, two decimals: "+0.12", "-0.05". */
export function deltaLabel(d: number): string {
  return `${d > 0 ? "+" : d < 0 ? "-" : ""}${Math.abs(d).toFixed(2)}`;
}

/** Index of the last item whose `t` is at or before `t` (-1 when none); items sorted by t. */
export function lastIndexAtOrBefore(items: ArrayLike<{ t: number }>, t: number): number {
  let lo = 0;
  let hi = items.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid].t <= t) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}
