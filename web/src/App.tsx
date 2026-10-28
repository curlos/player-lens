/**
 * App: loads the match library and the selected match, owns the playback clock, the selection
 * and the viewer settings. MatchView lays out the pitch, highlights row and sidebar.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Banners } from "./components/Banners";
import { FullTimeCard } from "./components/FullTimeCard";
import { HighlightsRow } from "./components/HighlightsRow";
import { LiveAnnouncer } from "./components/LiveAnnouncer";
import { Pitch } from "./components/Pitch";
import { PlaybackBar } from "./components/PlaybackBar";
import { ScoreBar } from "./components/ScoreBar";
import { Sidebar, type SidebarTab } from "./components/Sidebar";
import { StartOverlay } from "./components/StartOverlay";
import { ClockContext, useClock, useClockState } from "./hooks/useClock";
import { SettingsContext, useSettings, type Settings } from "./hooks/useSettings";
import { audioDebug, playCue, setAudioPlaying, setMurmurLevel, setMuted as setAudioMuted, setVoiceDanger, stopClip, stopReactions, unlockAudio } from "./lib/audio";
import { crowdCues, dangerLevel, murmurLevel } from "./lib/crowd";
import { Clock } from "./lib/clock";
import { ARROW_SEEK_S, CONTROLS_HIDE_MS } from "./lib/config";
import { fetchMatchList, loadMatch, type MatchData } from "./lib/match";
import { loadFlag, saveFlag } from "./lib/storage";
import type { Lang, MatchSummary, Mode } from "./types";

const HERO_FALLBACK = "md38_title_decider";
/** Pitch box including the grass around the lines, in meters: 4 m at the sides and bottom, 7 m on top for the score bar. */
const BOX_W = 113;
const BOX_H = 79;
/** Widest pitch box that still leaves room for the highlights row (up to two rows, about 5.5rem) below it. */
const BOX_WIDTH_CSS = `min(100cqw, calc((100cqh - 5.5rem) * ${BOX_W} / ${BOX_H}))`;
/** Fullscreen: the largest box that fits the screen at the same aspect ratio (the rest is black bars). */
const BOX_WIDTH_FULLSCREEN_CSS = `min(100vw, calc(100vh * ${BOX_W} / ${BOX_H}))`;

function usePersistentFlag(key: string, fallback: boolean): [boolean, (v: boolean) => void] {
  const [v, setV] = useState(() => loadFlag(key, fallback));
  const set = useCallback(
    (next: boolean) => {
      setV(next);
      saveFlag(key, next);
    },
    [key],
  );
  return [v, set];
}

export default function App() {
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [matchId, setMatchId] = useState(HERO_FALLBACK);
  const [match, setMatch] = useState<MatchData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState("azc_09");
  const [mode, setMode] = useState<Mode>("casual");
  const [langEs, setLangEs] = usePersistentFlag("lang-es", false);
  const [showRatings, setShowRatings] = useState(false);
  const [colorblind, setColorblind] = usePersistentFlag("colorblind", false);
  const [activityLabels, setActivityLabels] = usePersistentFlag("activity-labels", false);
  const [allArrows, setAllArrows] = usePersistentFlag("all-movement-arrows", false);
  const [muted, setMutedState] = useState(false);
  const [tab, setTab] = useState<SidebarTab>("player");

  const clock = useMemo(() => new Clock(match?.duration ?? 5400), [match]);
  useEffect(() => () => clock.dispose(), [clock]);

  // Dev only (removed from production builds): lets a browser session put the match in a given
  // state for visual checks, e.g. __playerLens.clock.seek(2330).
  useEffect(() => {
    if (import.meta.env.DEV) Object.assign(window, { __playerLens: { clock, select: setSelected, audio: audioDebug } });
  }, [clock]);

  // Crowd: each frame plays the cues crossed since the last one (never across a seek) and sets the
  // murmur; pausing suspends the audio. Audio only listens to the clock, it never holds it up.
  useEffect(() => {
    if (!match) return;
    let prevT = clock.t;
    let seeks = clock.getState().seekCount;
    const offFrame = clock.subscribeFrame((t) => {
      const { playing, rate, seekCount } = clock.getState();
      if (seekCount !== seeks) {
        seeks = seekCount;
        stopReactions();
      } else if (playing) {
        for (const cue of crowdCues(match, prevT, t, rate)) playCue(cue);
      }
      prevT = t;
      setMurmurLevel(murmurLevel(match, t));
      setVoiceDanger(dangerLevel(match, t));
    });
    const offState = clock.subscribeState(() => setAudioPlaying(clock.getState().playing, clock.ended));
    return () => {
      offFrame();
      offState();
      // a new match gets a new clock that starts paused and never reports it, so silence the old one here
      stopReactions();
      setAudioPlaying(false);
    };
  }, [clock, match]);

  useEffect(() => {
    fetchMatchList()
      .then((list) => {
        setMatches(list);
        const hero = list.find((m) => m.hero);
        if (hero) setMatchId((id) => (id === HERO_FALLBACK ? hero.match_id : id));
      })
      .catch(() => setMatches([]));
  }, []);

  useEffect(() => {
    let live = true;
    setMatch(null);
    setError(null);
    loadMatch(matchId)
      .then((m) => {
        if (!live) return;
        setSelected(m.meta.default_player);
        setMatch(m);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [matchId]);

  const settings: Settings = useMemo(
    () => ({
      selected,
      select: setSelected,
      mode,
      setMode,
      lang: langEs ? "es" : "en",
      setLang: (l: Lang) => setLangEs(l === "es"),
      showRatings,
      setShowRatings,
      colorblind,
      setColorblind,
      activityLabels,
      setActivityLabels,
      allArrows,
      setAllArrows,
      muted,
      setMuted: (m: boolean) => {
        setMutedState(m);
        setAudioMuted(m);
      },
    }),
    [selected, mode, langEs, setLangEs, showRatings, colorblind, setColorblind, activityLabels, setActivityLabels, allArrows, setAllArrows, muted],
  );

  const pickMatch = useCallback((id: string) => {
    stopClip();
    setTab("player");
    setMatchId(id);
  }, []);

  return (
    <ClockContext.Provider value={clock}>
      <SettingsContext.Provider value={settings}>
        <MatchView match={match} matchId={matchId} matches={matches} error={error} onPickMatch={pickMatch} tab={tab} setTab={setTab} />
      </SettingsContext.Provider>
    </ClockContext.Provider>
  );
}

interface MatchViewProps {
  match: MatchData | null;
  matchId: string;
  matches: MatchSummary[];
  error: string | null;
  onPickMatch: (id: string) => void;
  tab: SidebarTab;
  setTab: (t: SidebarTab) => void;
}

function MatchView({ match, matchId, matches, error, onPickMatch, tab, setTab }: MatchViewProps) {
  const clock = useClock();
  const state = useClockState();
  const { selected } = useSettings();
  const [recentMove, setRecentMove] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [ftDismissed, setFtDismissed] = useState(false);
  const moveTimer = useRef(0);
  const stage = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  // follows the browser, so Esc (or the browser's own exit) updates the button too
  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement != null && document.fullscreenElement === stage.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void stage.current?.requestFullscreen().catch(() => {}); // refused (iframe, iPhone): stay inline
  }, []);
  const started = state.started;
  const ended = !!match && started && clock.t >= match.duration;

  // A seek (or a new match) brings the full-time card back the next time the match ends.
  useEffect(() => setFtDismissed(false), [state.seekCount, match]);

  const start = useCallback(() => {
    if (!match) return;
    unlockAudio();
    clock.play();
  }, [clock, match]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target instanceof Element ? e.target : null; // can be window or document
      // Space and Enter on a focused control (button, checkbox, field) stay with the browser.
      const onControl = target?.closest("button, input, select, textarea, a, [role='switch'], [role='button'], [role='tab'], [contenteditable='true']") != null;
      if ((e.code === "Space" || e.code === "Enter") && onControl) return;
      if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
      const begun = clock.getState().started;
      if (e.code === "Space") {
        e.preventDefault();
        if (e.repeat) return; // holding Space must not toggle play over and over
        if (begun) clock.toggle();
        else start();
      } else if (e.code === "Enter" && !begun) {
        e.preventDefault();
        start();
      } else if (begun && (e.code === "ArrowLeft" || e.code === "ArrowRight")) {
        e.preventDefault();
        clock.seek(clock.t + (e.code === "ArrowLeft" ? -ARROW_SEEK_S : ARROW_SEEK_S));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clock, start]);

  const onMouseMove = () => {
    setRecentMove(true);
    window.clearTimeout(moveTimer.current);
    moveTimer.current = window.setTimeout(() => setRecentMove(false), CONTROLS_HIDE_MS);
  };

  // Hidden by default; appears on mouse move over the pitch or on pause (and stays while the View popover is open).
  const barVisible = !started || !state.playing || recentMove || popoverOpen;
  const boxW = fullscreen ? BOX_WIDTH_FULLSCREEN_CSS : BOX_WIDTH_CSS;

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 font-sans text-zinc-100 lg:h-screen lg:flex-row">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-2 p-3 lg:p-4">
        <div
          // Below lg the page is one column with no definite height, so the container measures its width
          // only (cqh then falls back to the viewport); from lg up it fills the row and measures both.
          className="relative flex flex-col items-center [container-type:inline-size] lg:min-h-[300px] lg:flex-1 lg:[container-type:size]"
          onClick={() => setPopoverOpen(false)}>
          {/* the fullscreen target: in fullscreen it fills the screen in black and centers the pitch box */}
          <div
            ref={stage}
            // the cursor hides with the control bar, as in a video player
            className={`${fullscreen ? "flex items-center justify-center bg-black" : "shrink-0"} ${started && !barVisible ? "cursor-none" : ""}`}
            // only the pitch wakes the control bar (not the highlights row below it); in fullscreen the
            // black bars count as pitch too
            onMouseMove={onMouseMove}
          >
          <div
            className="relative shrink-0"
            style={{
              width: boxW,
              height: `calc(${boxW} * ${BOX_H} / ${BOX_W})`,
              background: "#2E5A30",
              // in box units, not %: percentage padding would resolve against the parent's width
              padding: `calc(${boxW} * ${7 / BOX_W}) calc(${boxW} * ${4 / BOX_W}) calc(${boxW} * ${4 / BOX_W})`,
            }}
          >
            {match && <Pitch match={match} dimmed={ended} />}
            {match && (
              <div className="absolute left-1/2 top-[1.6%] z-10 -translate-x-1/2">
                <ScoreBar match={match} />
              </div>
            )}
            {match && <Banners match={match} />}
            {match && started && <LiveAnnouncer match={match} />}
            {match && (
              <PlaybackBar
                match={match}
                matches={matches}
                onPickMatch={onPickMatch}
                visible={barVisible}
                disabled={!started}
                popoverOpen={popoverOpen}
                setPopoverOpen={setPopoverOpen}
                fullscreen={fullscreen}
                onToggleFullscreen={toggleFullscreen}
              />
            )}
            {!started && <StartOverlay match={match} matchId={matchId} matches={matches} error={error} onStart={start} onPickMatch={onPickMatch} />}
            {match && ended && !ftDismissed && (
              <FullTimeCard
                match={match}
                player={selected}
                onReplay={() => {
                  clock.seek(0);
                  clock.play();
                }}
                onPickAnother={() => {
                  setFtDismissed(true);
                  setTab("all");
                }}
              />
            )}
          </div>
          </div>
          {match && (
            <div className="mt-2 w-full pb-4" style={{ maxWidth: BOX_WIDTH_CSS }}>
              <HighlightsRow match={match} />
            </div>
          )}
        </div>
      </main>
      <Sidebar match={match} tab={tab} setTab={setTab} started={started} ended={ended} />
    </div>
  );
}
