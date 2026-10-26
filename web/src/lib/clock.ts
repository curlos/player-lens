/**
 * The single playback clock (specs/frontend.md, "Playback clock"): `{t, playing, rate}`.
 * A requestAnimationFrame loop advances t by real elapsed time x rate while playing. It never
 * waits on commentary, audio or the network. Frame listeners run every frame (the pitch);
 * state listeners run on play, pause, rate change and seek (panels, controls).
 */
import { SPEEDS, type Speed } from "./config";

export interface ClockState {
  playing: boolean;
  rate: Speed;
  /** Bumped on every seek so panels can re-anchor (for example the commentary late-line rule). */
  seekCount: number;
  started: boolean;
}

type FrameListener = (t: number) => void;

export class Clock {
  t = 0;
  private duration: number;
  private state: ClockState = { playing: false, rate: 1, seekCount: 0, started: false };
  private frameListeners = new Set<FrameListener>();
  private stateListeners = new Set<() => void>();
  private raf = 0;
  private last = 0;

  constructor(duration: number) {
    this.duration = duration;
  }

  getState = (): ClockState => this.state;

  subscribeState = (fn: () => void): (() => void) => {
    this.stateListeners.add(fn);
    return () => this.stateListeners.delete(fn);
  };

  /** Called every animation frame while playing and once after each seek. */
  subscribeFrame(fn: FrameListener): () => void {
    this.frameListeners.add(fn);
    fn(this.t);
    return () => this.frameListeners.delete(fn);
  }

  private setState(patch: Partial<ClockState>) {
    this.state = { ...this.state, ...patch };
    this.stateListeners.forEach((fn) => fn());
  }

  private emitFrame() {
    this.frameListeners.forEach((fn) => fn(this.t));
  }

  get ended(): boolean {
    return this.t >= this.duration;
  }

  play() {
    if (this.state.playing) return;
    if (this.ended) this.seek(0); // a restart is a seek: listeners re-anchor and the pitch redraws
    this.setState({ playing: true, started: true });
    this.last = performance.now();
    this.raf = requestAnimationFrame(this.tick);
  }

  pause() {
    if (!this.state.playing) return;
    cancelAnimationFrame(this.raf);
    this.setState({ playing: false });
  }

  toggle() {
    if (this.state.playing) this.pause();
    else this.play();
  }

  setRate(rate: Speed) {
    if (!SPEEDS.includes(rate) || rate === this.state.rate) return;
    this.setState({ rate });
  }

  /** Jumps to t (clamped to the match). Everything is local, so this is instant. */
  seek(t: number) {
    this.t = Math.min(Math.max(t, 0), this.duration);
    this.setState({ seekCount: this.state.seekCount + 1 });
    this.emitFrame();
    if (this.ended) this.pause();
  }

  private tick = (now: number) => {
    // 0 to 0.25 s: a background tab must not jump the match, and the first frame's timestamp can
    // predate the performance.now() taken in play(), which must not move the clock backward
    const dt = Math.min(Math.max((now - this.last) / 1000, 0), 0.25);
    this.last = now;
    this.t = Math.min(Math.max(this.t + dt * this.state.rate, 0), this.duration);
    this.emitFrame();
    if (this.ended) {
      this.setState({ playing: false });
      return;
    }
    this.raf = requestAnimationFrame(this.tick);
  };

  dispose() {
    cancelAnimationFrame(this.raf);
    this.frameListeners.clear();
    this.stateListeners.clear();
  }
}
