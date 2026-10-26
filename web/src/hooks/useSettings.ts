import { createContext, useContext } from "react";
import type { Lang, Mode } from "../types";

/** Viewer settings shared by the pitch, the panels and the View popover. */
export interface Settings {
  selected: string;
  select: (id: string) => void;
  mode: Mode;
  setMode: (m: Mode) => void;
  lang: Lang;
  setLang: (l: Lang) => void;
  showRatings: boolean;
  setShowRatings: (v: boolean) => void;
  colorblind: boolean;
  setColorblind: (v: boolean) => void;
  activityLabels: boolean;
  setActivityLabels: (v: boolean) => void;
  /** Movement arrows on every moving player, not just the followed player and those nearest them. */
  allArrows: boolean;
  setAllArrows: (v: boolean) => void;
  muted: boolean;
  setMuted: (v: boolean) => void;
}

export const SettingsContext = createContext<Settings | null>(null);

export function useSettings(): Settings {
  const s = useContext(SettingsContext);
  if (!s) throw new Error("useSettings outside SettingsContext");
  return s;
}
