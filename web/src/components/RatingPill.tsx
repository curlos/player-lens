import { useSettings } from "../hooks/useSettings";
import { ratingColor, ratingTextColor } from "../lib/colors";
import { ratingLabel } from "../lib/format";

/** Colored rating pill; the number is always visible (specs/frontend.md, rating colors). */
export function RatingPill({ rating, className = "" }: { rating: number; className?: string }) {
  const { colorblind } = useSettings();
  return (
    <span
      className={`inline-flex items-center justify-center rounded-md font-bold tabular-nums ${className}`}
      style={{ background: ratingColor(rating, colorblind), color: ratingTextColor(rating, colorblind) }}
    >
      {ratingLabel(rating)}
    </span>
  );
}
