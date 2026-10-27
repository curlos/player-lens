/**
 * Commentary for the selected player (specs/frontend.md, "Commentary, trace and audio").
 * Fetches the 1-minute chunk at the playhead plus the next one, caches them by
 * (match, player, mode, lang, chunk), and shows the line whose start time has been reached.
 * Above 1x nothing is fetched and the panel says commentary is paused.
 */
import { useEffect, useRef, useState } from "react";
import { useClock, useClockState, useMatchTime } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { playClip, stopClip } from "../lib/audio";
import { getCommentaryChunk, getTrace } from "../lib/commentary";
import { CHUNK_S, LATE_LINE_DROP_S, MAX_CHUNK } from "../lib/config";
import { minuteLabel } from "../lib/format";
import type { MatchData } from "../lib/match";
import type { CommentaryChunk, CommentaryLine, Lang, Mode, Trace } from "../types";

const chunkKey = (match: string, player: string, mode: Mode, lang: Lang, chunk: number) => `${match}|${player}|${mode}|${lang}|${chunk}`;

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-md bg-zinc-800 p-0.5 text-sm">
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          aria-pressed={v === value}
          onClick={() => onChange(v)}
          className={`rounded px-2 py-0.5 ${v === value ? "bg-zinc-600 text-white" : "text-zinc-400 hover:text-zinc-200"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function AgentTrace({ match, line }: { match: MatchData; line: CommentaryLine }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  useEffect(() => {
    let live = true;
    getTrace(line.id).then((tr) => live && setTrace(tr));
    return () => {
      live = false;
    };
  }, [line.id]);
  if (!trace) return <p className="mt-2 text-sm text-zinc-500">Loading trace…</p>;
  return (
    <ol className="mt-2 space-y-1.5 border-l border-zinc-700 pl-3 text-sm">
      {trace.steps.map((s, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[15px] top-1 h-1.5 w-1.5 rounded-full bg-zinc-400" />
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-zinc-200">{s.agent}</span>
            {s.fact_check && <span className="rounded bg-zinc-700 px-1.5 py-px text-xs text-zinc-300">{s.fact_check}</span>}
          </div>
          {s.summary && <p className="text-zinc-400">{s.summary}</p>}
        </li>
      ))}
      {trace.events.length > 0 && (
        <li className="text-zinc-500">
          Source events:{" "}
          {trace.events
            .map((id) => match.eventById.get(id))
            .filter((e) => e != null)
            .map((e) => `${e.type.replace(/_/g, " ")} ${minuteLabel(e.t)}`)
            .join(", ")}
        </li>
      )}
    </ol>
  );
}

export function CommentaryPanel({ match, player, started }: { match: MatchData; player: string; started: boolean }) {
  const t = useMatchTime(10);
  const clock = useClock();
  const { rate, seekCount } = useClockState();
  const atOneX = rate === 1;
  // A seek, a player switch or a return to 1x starts fresh: lines older than the late limit are
  // dropped. Adjusted during render (not in an effect) so the first render after the change, and
  // the clip it plays, already use the new anchor.
  const anchorKey = `${seekCount}|${player}|${atOneX}`;
  const [anchor, setAnchor] = useState({ key: anchorKey, t: clock.t });
  if (anchor.key !== anchorKey) setAnchor({ key: anchorKey, t: clock.t });
  const { mode, setMode, lang, setLang, muted } = useSettings();
  const cache = useRef(new Map<string, CommentaryChunk>());
  const pending = useRef(new Set<string>());
  const [, setVersion] = useState(0);
  const [retry, setRetry] = useState(0);
  const [traceOpen, setTraceOpen] = useState<string | null>(null);
  const lastPlayed = useRef<string | null>(null);

  const chunk = Math.min(Math.floor(t / CHUNK_S), MAX_CHUNK);

  // Changing speed stops any clip that is playing.
  useEffect(() => {
    stopClip();
  }, [rate]);

  useEffect(() => {
    if (!atOneX || !started) return; // no commentary requests above 1x
    // the playhead chunk and the next; also the previous one, whose last line may still be
    // playing just after a minute boundary
    for (const c of [chunk, chunk + 1, chunk - 1]) {
      if (c < 0 || c > MAX_CHUNK) continue;
      const key = chunkKey(match.id, player, mode, lang, c);
      if (cache.current.has(key) || pending.current.has(key)) continue;
      pending.current.add(key);
      getCommentaryChunk(match, player, mode, lang, c)
        .then((res) => {
          cache.current.set(key, res);
          setVersion((v) => v + 1);
        })
        // a failed chunk is retried a few seconds later; the clock never waits for it
        .catch(() => window.setTimeout(() => setRetry((r) => r + 1), 3000))
        .finally(() => pending.current.delete(key));
    }
  }, [match, player, mode, lang, chunk, atOneX, started, retry]);

  const current = cache.current.get(chunkKey(match.id, player, mode, lang, chunk));
  const previous = chunk > 0 ? cache.current.get(chunkKey(match.id, player, mode, lang, chunk - 1)) : undefined;
  let line: CommentaryLine | null = null;
  if (current) {
    const lines = [...(previous?.lines ?? []), ...current.lines];
    for (let i = lines.length - 1; i >= 0; i--) {
      if (lines[i].t <= t) {
        if (lines[i].t >= anchor.t || t - lines[i].t <= LATE_LINE_DROP_S) line = lines[i];
        break;
      }
    }
  }

  // After a seek or a player switch a line may play again (declared before the clip effect so it
  // runs first in the same commit).
  useEffect(() => {
    lastPlayed.current = null;
  }, [anchorKey]);

  useEffect(() => {
    if (!line || !atOneX || line.id === lastPlayed.current) return;
    lastPlayed.current = line.id;
    if (!muted) playClip(line.audio_url ?? null);
  }, [line, atOneX, muted]);

  const name = match.players.get(player)?.name ?? "";
  let body;
  if (!started) body = <p className="text-sm text-zinc-400">Waiting for kickoff</p>;
  else if (t >= match.duration) body = <p className="text-sm text-zinc-400">Full time</p>;
  else if (!atOneX) body = <p className="text-sm text-zinc-400">Commentary pauses at {rate}x speed</p>;
  else if (!current) body = <p className="animate-pulse text-sm text-zinc-400">Preparing commentary</p>;
  else if (!line) body = <p className="text-sm text-zinc-500">Following {name}…</p>;
  else {
    const big = line.importance >= 0.8;
    body = (
      <div>
        <p className={big ? "text-2xl font-bold leading-tight text-zinc-50" : "text-[15px] leading-snug text-zinc-100"}>{line.text}</p>
        <button
          type="button"
          onClick={() => setTraceOpen(traceOpen === line.id ? null : line.id)}
          className="mt-3 text-sm text-zinc-400 underline decoration-zinc-600 underline-offset-2 hover:text-zinc-200"
        >
          How this was made
        </button>
        {traceOpen === line.id && <AgentTrace match={match} line={line} />}
      </div>
    );
  }

  return (
    <section className="flex min-h-[11rem] shrink-0 flex-col rounded-xl border border-white/5 bg-zinc-900/80 p-3">
      <div className="mb-3 flex items-center justify-between">
        <Segmented<Mode> value={mode} onChange={setMode} options={[["casual", "Casual"], ["analyst", "Analyst"]]} />
        <div className="flex items-center gap-2">
          <Segmented<Lang> value={lang} onChange={setLang} options={[["en", "EN"], ["es", "ES"]]} />
        </div>
      </div>
      <div aria-live="polite" lang={lang}>
        {body}
      </div>
    </section>
  );
}
