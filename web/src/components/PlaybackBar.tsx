/**
 * Auto-hiding control bar along the bottom of the pitch: play/pause, mute (all match sound), the
 * clock, a timeline with goal and card markers, the five speeds, the gear for the View popover
 * (which holds Activity labels) and full screen.
 */
import { useRef } from "react";
import { useClock, useClockState, useMatchTime } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { SPEEDS } from "../lib/config";
import { clockLabel, minuteLabel } from "../lib/format";
import type { MatchData } from "../lib/match";
import type { MatchSummary } from "../types";
import { BallIcon, FullscreenIcon, GearIcon, PauseIcon, PlayIcon, SpeakerIcon } from "./icons";
import { ViewPopover } from "./ViewPopover";

interface Props {
  match: MatchData;
  matches: MatchSummary[];
  onPickMatch: (id: string) => void;
  visible: boolean;
  disabled: boolean;
  popoverOpen: boolean;
  setPopoverOpen: (v: boolean) => void;
  fullscreen: boolean;
  onToggleFullscreen: () => void;
}

export function PlaybackBar({ match, matches, onPickMatch, visible, disabled, popoverOpen, setPopoverOpen, fullscreen, onToggleFullscreen }: Props) {
  const clock = useClock();
  const { playing, rate } = useClockState();
  const t = useMatchTime(10);
  const { muted, setMuted } = useSettings();
  const track = useRef<HTMLDivElement>(null);
  const gear = useRef<HTMLButtonElement>(null);

  const seekFromPointer = (clientX: number) => {
    const el = track.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    clock.seek(((clientX - box.left) / box.width) * match.duration);
  };

  const pct = (x: number) => `${(x / match.duration) * 100}%`;

  return (
    <div
      // hidden bars still show while a control inside has keyboard focus (focus-visible, so a button
      // clicked with the mouse, which keeps focus, doesn't pin the bar open); before Start the bar is inert
      className={`@container absolute inset-x-0 bottom-0 z-20 transition-opacity duration-300 ${visible ? "opacity-100" : "pointer-events-none opacity-0 has-[:focus-visible]:pointer-events-auto has-[:focus-visible]:opacity-100"} ${disabled ? "pointer-events-none opacity-40 grayscale" : ""}`}
      inert={disabled}
      onClick={(e) => e.stopPropagation()}
      // a button or the timeline clicked with the mouse gives its focus back, or a later arrow-key
      // seek would make it :focus-visible and pin the bar open (Tab still focuses and shows it)
      onPointerUp={() => {
        const el = document.activeElement;
        if (el instanceof HTMLElement && el.matches("button, [role='slider']") && el.closest("[data-playback-bar]")) {
          window.setTimeout(() => el.blur(), 0);
        }
      }}
      data-playback-bar
      onKeyDown={(e) => {
        if (e.key === "Escape" && popoverOpen) {
          setPopoverOpen(false);
          gear.current?.focus();
        }
      }}
    >
      {/* narrow pitch (timeline on its own row): more room above the timeline and between it and the buttons */}
      <div className="mx-2 mb-2 flex flex-wrap items-center gap-x-2 gap-y-3 rounded-lg bg-zinc-950/85 px-2 pt-3.5 pb-2.5 @2xl:gap-x-3 @2xl:gap-y-1.5 @2xl:px-3 @2xl:py-2 text-zinc-200 backdrop-blur">
        <button type="button" aria-label={playing ? "Pause" : "Play"} onClick={() => clock.toggle()} className="rounded p-1 hover:bg-white/10">
          {playing ? <PauseIcon className="h-5 w-5" /> : <PlayIcon className="h-5 w-5" />}
        </button>
        {/* where a video player keeps it: mutes the crowd now and the commentary voice from Phase 3 */}
        <button type="button" aria-label={muted ? "Unmute" : "Mute"} aria-pressed={muted} onClick={() => setMuted(!muted)} className="rounded p-1 hover:bg-white/10">
          <SpeakerIcon off={muted} className={`h-5 w-5 ${muted ? "text-zinc-500" : ""}`} />
        </button>
        {/* on a narrow pitch the score bar already shows the clock */}
        <span className="hidden w-11 text-sm tabular-nums text-zinc-400 @md:inline">{clockLabel(t)}</span>

        <div
          ref={track}
          // a narrow pitch (phone, or phone landscape): the timeline gets its own row above the buttons.
          // A container query, because the pitch can be narrow on a wide screen.
          className="relative order-first h-6 min-w-0 flex-1 basis-full cursor-pointer @2xl:order-none @2xl:basis-0"
          role="slider"
          tabIndex={0}
          aria-label="Match time"
          aria-valuemin={0}
          aria-valuemax={match.duration}
          aria-valuenow={Math.floor(t)}
          aria-valuetext={clockLabel(t)}
          // left and right arrows are handled globally (5 s); Home and End jump to the ends
          onKeyDown={(e) => {
            if (e.key === "Home" || e.key === "End") {
              e.preventDefault();
              clock.seek(e.key === "Home" ? 0 : match.duration);
            }
          }}
          onPointerDown={(e) => {
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
            seekFromPointer(e.clientX);
          }}
          onPointerMove={(e) => {
            if (e.buttons === 1) seekFromPointer(e.clientX);
          }}
        >
          <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-zinc-700" />
          <div className="absolute left-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-lime-400" style={{ width: pct(t) }} />
          <div className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow" style={{ left: pct(t) }} />
          {match.highlights.map((h) => (
            <div
              key={h.id}
              aria-hidden="true"
              title={`${minuteLabel(h.t)} ${h.kind}`}
              className="pointer-events-none absolute -top-1.5 -translate-x-1/2"
              style={{ left: pct(h.t) }}
            >
              {h.kind === "goal" ? (
                <BallIcon className="h-3 w-3 rounded-full ring-1 ring-zinc-950" />
              ) : h.kind === "penalty" ? (
                <span className="block rounded-sm bg-orange-300 px-[2px] text-[8px] font-bold leading-3 text-zinc-900 ring-1 ring-zinc-950">P</span>
              ) : (
                <span className={`block h-3 w-2 rounded-[1px] ring-1 ring-zinc-950 ${h.kind === "red" ? "bg-red-500" : "bg-yellow-400"}`} />
              )}
            </div>
          ))}
        </div>

        {/* ml-auto: on a narrow pitch (timeline on its own row) play, mute and time stay left and the
            speeds, gear and full screen go right, as in a phone video player; mr-1 sets the speeds apart */}
        <div className="ml-auto mr-1 flex items-center gap-0.5">
          {SPEEDS.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === rate}
              aria-label={`Speed ${r}x`}
              onClick={() => clock.setRate(r)}
              className={`rounded px-1.5 py-0.5 text-sm font-semibold tabular-nums ${r === rate ? "bg-lime-400 text-zinc-900" : "text-zinc-300 hover:bg-white/10"}`}
            >
              {r}x
            </button>
          ))}
        </div>

        <div className="relative">
          <button
            ref={gear}
            type="button"
            aria-label="View options"
            aria-haspopup="dialog"
            aria-expanded={popoverOpen}
            onClick={() => setPopoverOpen(!popoverOpen)}
            className="rounded p-1 hover:bg-white/10"
          >
            <GearIcon className="h-5 w-5" />
          </button>
          {popoverOpen && <ViewPopover match={match} matches={matches} onPickMatch={onPickMatch} />}
        </div>
        {/* last, where video players keep it; hidden where the browser has no fullscreen (iPhone) */}
        {document.fullscreenEnabled && (
          <button
            type="button"
            aria-label={fullscreen ? "Exit full screen" : "Full screen"}
            aria-pressed={fullscreen}
            onClick={onToggleFullscreen}
            className="rounded p-1 hover:bg-white/10"
          >
            <FullscreenIcon exit={fullscreen} className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
