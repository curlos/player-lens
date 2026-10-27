/** Small inline SVG icons (no icon font, no brand marks). */
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = { "aria-hidden": true, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const PlayIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" />
  </svg>
);
export const PauseIcon = (p: P) => (
  <svg {...base} {...p}>
    <rect x="6" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" />
    <rect x="14" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" />
  </svg>
);
export const GearIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);
export const SpeakerIcon = ({ off, ...p }: P & { off?: boolean }) => (
  <svg {...base} {...p}>
    <path d="M11 5 6 9H2v6h4l5 4z" fill="currentColor" />
    {off ? <path d="m23 9-6 6M17 9l6 6" /> : <path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" />}
  </svg>
);
/** Four corner brackets: pointing out to enter fullscreen, pointing in (`exit`) to leave it. */
export const FullscreenIcon = ({ exit, ...p }: P & { exit?: boolean }) => (
  <svg {...base} {...p}>
    <path d={exit ? "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" : "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"} />
  </svg>
);
export const BallIcon = (p: P) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" {...p}>
    <circle cx="12" cy="12" r="10" fill="#fff" stroke="#18181b" strokeWidth="1.5" />
    <path d="m12 7 4 3-1.5 4.5h-5L8 10z" fill="#18181b" />
    <path d="M12 7V2.5M16 10l4.5-1.5M14.5 14.5l3 3.5M9.5 14.5l-3 3.5M8 10 3.5 8.5" stroke="#18181b" strokeWidth="1.2" />
  </svg>
);
/** Penalty area with the spot: the box a penalty is given in, so it reads differently from the goal ball. */
export const PenaltyIcon = (p: P) => (
  <svg {...base} strokeWidth={1.8} {...p}>
    <path d="M3 5h18v14H3zM8 5v6h8V5" />
    <circle cx="12" cy="15" r="1.6" fill="currentColor" stroke="none" />
  </svg>
);
export const BootIcon = (p: P) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor" {...p}>
    <path d="M3 15.5c0-1 .6-1.6 1.5-1.8l4-.9c.8-.2 1.5-.8 1.8-1.6L12 7h4.5l.6 3.2c.2.9 1 1.5 1.9 1.6l1.6.2c.8.1 1.4.8 1.4 1.6V17a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
    <path d="M5 19h1.5M9 19h1.5M13 19h1.5M17 19h1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);
export const ReplayIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);
export const AvatarIcon = (p: P) => (
  <svg aria-hidden="true" viewBox="0 0 48 48" {...p}>
    <circle cx="24" cy="24" r="24" fill="#3f3f46" />
    <circle cx="24" cy="19" r="8.5" fill="#18181b" />
    <path d="M8 42c2.5-8 9-12 16-12s13.5 4 16 12a23.8 23.8 0 0 1-32 0z" fill="#18181b" />
  </svg>
);
