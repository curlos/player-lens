import { createContext, useContext, useEffect, useState, useSyncExternalStore } from "react";
import type { Clock, ClockState } from "../lib/clock";

export const ClockContext = createContext<Clock | null>(null);

export function useClock(): Clock {
  const clock = useContext(ClockContext);
  if (!clock) throw new Error("useClock outside ClockContext");
  return clock;
}

/** Play state, rate and seek count; re-renders only when they change. */
export function useClockState(): ClockState {
  const clock = useClock();
  return useSyncExternalStore(clock.subscribeState, clock.getState);
}

/**
 * Match time for panels, re-rendering at most `hz` times per second (and at once after a seek),
 * so React trees never re-render every frame (specs/frontend.md, "Performance").
 */
export function useMatchTime(hz = 10): number {
  const clock = useClock();
  const [t, setT] = useState(clock.t);
  useEffect(() => {
    let lastEmit = 0;
    let lastSeek = clock.getState().seekCount;
    return clock.subscribeFrame((now) => {
      const wall = performance.now();
      const seek = clock.getState().seekCount;
      if (seek !== lastSeek || wall - lastEmit >= 1000 / hz || clock.ended) {
        lastSeek = seek;
        lastEmit = wall;
        setT(now);
      }
    });
  }, [clock, hz]);
  return t;
}

/** Match time rounded down to whole seconds; re-renders once per match second at most. */
export function useMatchSecond(): number {
  const clock = useClock();
  const [s, setS] = useState(Math.floor(clock.t));
  useEffect(() => clock.subscribeFrame((now) => setS(Math.floor(now))), [clock]);
  return s;
}
