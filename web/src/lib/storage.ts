/** Per-viewer conveniences in localStorage. Never needed for correctness, so every access is guarded. */

export function loadFlag(key: string, fallback: boolean): boolean {
  try {
    const v = window.localStorage.getItem(`player-lens:${key}`);
    return v === null ? fallback : v === "1";
  } catch {
    return fallback;
  }
}

export function saveFlag(key: string, value: boolean): void {
  try {
    window.localStorage.setItem(`player-lens:${key}`, value ? "1" : "0");
  } catch {
    // storage blocked (private window, previews): the setting just isn't remembered
  }
}
