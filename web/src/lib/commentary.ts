/**
 * Commentary source for the selected player.
 *
 * Phase 2 placeholder: template lines built by code from the player's events and rating log,
 * shaped exactly like CommentaryLine in agents/models.py (fact_check "template", audio_url null).
 * Phase 3 replaces the bodies of getCommentaryChunk and getTrace with GET /commentary and
 * GET /agents/trace; the callers don't change.
 *
 * Cadence follows ARCHITECTURE "Commentary cadence": at least LINE_MIN_GAP_S between lines (big
 * moments may interrupt), a filler line when nothing fired for LINE_MAX_SILENCE_S, and a short
 * reaction about 8 s after a goal.
 */
import type { CommentaryChunk, CommentaryLine, Lang, MatchEvent, Mode, RatingEntry, Trace } from "../types";
import { CHUNK_S, LINE_MAX_SILENCE_S, LINE_MIN_GAP_S, MAX_CHUNK, SPOTLIGHT_MIN_IMPORTANCE } from "./config";
import { activityAt, distanceKmAt, playerLabel, ratingAt, scoreAt, type MatchData } from "./match";
import { reasonText } from "./reasons";
import { deltaLabel, minuteLabel, ratingLabel } from "./format";

interface Candidate {
  t: number;
  type: string;
  importance: number;
  text: string;
  events: string[];
}

/** Built lines per (match, player, mode, lang); chunks are slices of this. */
const lineCache = new Map<string, CommentaryLine[]>();
/** Source events per line id, for the trace. */
const lineEvents = new Map<string, { line: CommentaryLine; events: string[] }>();

/**
 * One 1-minute commentary chunk for the selected player (chunk = floor(t / 60), 0 to 89).
 * Async on purpose: the Phase 3 version is a network call and may answer "preparing".
 */
export async function getCommentaryChunk(
  match: MatchData,
  player: string,
  mode: Mode,
  lang: Lang,
  chunk: number,
): Promise<CommentaryChunk> {
  const key = `${match.id}|${player}|${mode}|${lang}`;
  let lines = lineCache.get(key);
  if (!lines) {
    lines = buildLines(match, player, mode, lang);
    lineCache.set(key, lines);
  }
  const c = Math.min(Math.max(chunk, 0), MAX_CHUNK);
  const from = c * CHUNK_S;
  const to = c === MAX_CHUNK ? Infinity : from + CHUNK_S;
  return { match: match.id, player, mode, lang, chunk: c, status: "ready", lines: lines.filter((l) => l.t >= from && l.t < to) };
}

/** "How this was made" for one line. Template lines have a single Template step. */
export async function getTrace(lineId: string): Promise<Trace | null> {
  const entry = lineEvents.get(lineId);
  if (!entry) return null;
  return {
    line_id: lineId,
    steps: [
      {
        agent: "Template",
        summary: "Written by code from the event and rating log, no AI call",
        text: entry.line.text,
        fact_check: "template",
      },
    ],
    events: entry.events,
  };
}

/** Words to seconds of speech, clamped to the 2 to 5 s line length (guess: ~2.7 words per second). */
function speechSeconds(text: string): number {
  return Math.min(5, Math.max(2, text.split(/\s+/).length / 2.7));
}

function surname(match: MatchData, id: string): string {
  const name = match.players.get(id)?.name ?? id;
  return name.replace(/^[A-Z]\.\s*/, "");
}

const ACTIVITY_PHRASE: Record<Lang, Record<string, string>> = {
  en: {
    stand: "standing his ground", walk: "walking back into shape", jog: "jogging into position", run: "on the move",
    sprint: "sprinting", carry: "driving forward with the ball", press: "pressing the ball carrier",
    track_back: "tracking back", mark: "staying tight to his man", make_run: "making a run in behind",
    hold_shape: "holding the team shape", talk_ref: "having a word with the referee", huddle: "in the huddle",
    celebrate: "celebrating", down: "down on the turf", wall: "lining up in the wall",
    set_piece_wait: "waiting for the set piece", take_set_piece: "standing over the set piece",
    sent_off: "making the long walk off",
  },
  es: {
    stand: "quieto en su zona", walk: "volviendo a su posición", jog: "trotando hacia su sitio", run: "en movimiento",
    sprint: "esprintando", carry: "conduciendo la pelota", press: "presionando al rival con la pelota",
    track_back: "replegando", mark: "pegado a su marca", make_run: "atacando el espacio a la espalda",
    hold_shape: "manteniendo el orden del equipo", talk_ref: "hablando con el árbitro", huddle: "reunido con sus compañeros",
    celebrate: "celebrando", down: "tendido en el césped", wall: "colocado en la barrera",
    set_piece_wait: "esperando el cobro", take_set_piece: "listo para cobrar",
    sent_off: "camino al vestidor",
  },
};

function scoreText(match: MatchData, t: number): string {
  const s = scoreAt(match, t);
  return `${match.teams.azc.abbr} ${s.azc}-${s.rdm} ${match.teams.rdm.abbr}`;
}

/** Text for a match-wide moment (goal, card, penalty) from the selected player's point of view. */
function momentText(match: MatchData, e: MatchEvent, player: string, mode: Mode, lang: Lang): string {
  const who = surname(match, e.player);
  const team = match.teams[e.team].name;
  const mine = e.player === player;
  const score = scoreText(match, e.t);
  const xg = e.xg != null ? e.xg.toFixed(2) : "";
  const es = lang === "es";
  switch (e.type) {
    case "goal":
      if (mine) {
        if (mode === "analyst") {
          if (!xg) return es ? `Gol de ${who}. ${score}.` : `${who} scores. ${score}.`;
          return es ? `Gol de ${who}, xG ${xg}. ${score}.` : `${who} scores from an xG ${xg} chance. ${score}.`;
        }
        return es ? `¡GOL! ¡${who} la mete! ${score}.` : `GOAL! ${who} buries it! ${score}.`;
      }
      if (e.other === player) {
        return es ? `¡Asistencia de ${surname(match, player)} y gol de ${who}! ${score}.` : `${surname(match, player)} sets it up and ${who} scores! ${score}.`;
      }
      return es ? `Gol de ${team}: marca ${who}. ${score}.` : `Goal for ${team}, ${who} scores. ${score}.`;
    case "card_yellow":
      return mine
        ? es ? `Amarilla para ${who}. Tendrá que medir cada entrada.` : `Yellow card for ${who}. He has to be careful now.`
        : es ? `Amarilla para ${who} (${team}).` : `${who} of ${team} is booked.`;
    case "card_red":
      return mine
        ? es ? `¡Roja para ${who}! Se va expulsado.` : `Red card! ${who} is sent off.`
        : es ? `¡Expulsado ${who}! ${team} se queda con diez.` : `${who} is sent off. ${team} are down to ten.`;
    case "penalty":
      return es ? `¡Penal para ${team}! Momento enorme.` : `Penalty to ${team}! A massive moment.`;
    default:
      return "";
  }
}

/** Text for one of the player's own rating changes, built on the reason template. */
function ratingLineText(match: MatchData, r: RatingEntry, mode: Mode, lang: Lang): string {
  const reason = reasonText(r.reason_code, r.values, lang, (id) => playerLabel(match, id));
  if (!reason) return "";
  const who = surname(match, r.player);
  if (mode === "analyst") {
    const rating = ratingLabel(r.rating_after);
    return lang === "es"
      ? `${reason}. Nota ${rating} (${deltaLabel(r.delta)}).`
      : `${reason}. Rating ${rating} (${deltaLabel(r.delta)}).`;
  }
  const lower = reason.charAt(0).toLowerCase() + reason.slice(1);
  if (r.off_ball) return lang === "es" ? `Trabajo sin pelota de ${who}: ${lower}.` : `Off the ball, ${who}: ${lower}.`;
  return `${who}: ${lower}.`;
}

function fillerText(match: MatchData, player: string, t: number, mode: Mode, lang: Lang, n: number): string {
  const who = surname(match, player);
  const es = lang === "es";
  if (mode === "analyst" || n % 3 === 2) {
    const km = distanceKmAt(match, player, t).toFixed(1);
    const rating = ratingLabel(ratingAt(match, player, t));
    return es ? `${who}: ${km} km recorridos, nota ${rating}.` : `${who} has covered ${km} km, rating ${rating}.`;
  }
  const act = activityAt(match, player, t) ?? "hold_shape";
  const phrase = ACTIVITY_PHRASE[lang][act] ?? act.replace(/_/g, " ");
  if (n % 3 === 1) return `${minuteLabel(t)}: ${who}, ${phrase}.`;
  return es ? `${who} sigue ${phrase}.` : `${who} is ${phrase}.`;
}

/** Builds every line of the match for one player, mode and language. */
export function buildLines(match: MatchData, player: string, mode: Mode, lang: Lang): CommentaryLine[] {
  const candidates: Candidate[] = [];
  const momentSeconds = new Set<number>();

  // goals, cards and penalties, with a second yellow already merged into its red (buildHighlights)
  for (const { event: e } of match.highlights) {
    const text = momentText(match, e, player, mode, lang);
    if (!text) continue;
    const involved = e.player === player || e.other === player;
    candidates.push({ t: e.t, type: e.type, importance: involved ? 1 : e.importance, text, events: [e.id, ...(e.related ?? [])] });
    if (involved) momentSeconds.add(e.t);
    if (e.type === "goal") {
      const reaction =
        e.player === player
          ? lang === "es" ? "Lo celebra con los suyos. Qué momento." : "He wheels away to celebrate. What a moment."
          : e.team === match.players.get(player)?.team
            ? lang === "es" ? "Su equipo lo celebra; ahora a mantener la cabeza fría." : "His side celebrate. Now to keep a cool head."
            : lang === "es" ? "Toca reaccionar. Hay que volver a empezar." : "A blow for his side. Time to respond.";
      candidates.push({ t: Math.min(e.t + 8, match.duration), type: "reaction", importance: 0.6, text: reaction, events: [e.id] });
    }
  }

  for (const r of match.ratingLog.get(player) ?? []) {
    if (momentSeconds.has(r.t)) continue; // the goal or card line already covers this second
    const text = ratingLineText(match, r, mode, lang);
    if (!text) continue;
    const ev = match.eventById.get(r.event_id);
    candidates.push({
      t: r.t,
      type: r.off_ball ? "off_ball" : "rating",
      // rating changes of 0.10 or more outrank small ones (ARCHITECTURE trigger order)
      importance: Math.max(ev?.importance ?? 0.1, Math.abs(r.delta) >= 0.1 ? 0.4 : 0),
      text,
      events: [r.event_id],
    });
  }

  candidates.sort((a, b) => a.t - b.t || b.importance - a.importance);

  // Pick lines: keep the gap rule, big moments may interrupt; a lower-importance overlap is dropped.
  const picked: Candidate[] = [];
  let prevEnd = -Infinity;
  for (const c of candidates) {
    const big = c.importance >= SPOTLIGHT_MIN_IMPORTANCE;
    // the goal reaction is part of the goal moment: it skips the minimum gap but never overlaps
    const minGap = c.type === "reaction" ? 0 : LINE_MIN_GAP_S;
    if (!big && c.t < prevEnd + minGap) continue;
    if (big && picked.length && picked[picked.length - 1].t === c.t) continue;
    picked.push(c);
    prevEnd = c.t + speechSeconds(c.text);
  }

  // Fill silences longer than the limit with filler lines from code-computed facts.
  const withFiller: Candidate[] = [];
  let lastEnd = 0;
  let fillers = 0;
  const pushFillersUntil = (until: number) => {
    while (until - lastEnd > LINE_MAX_SILENCE_S) {
      // 10 s after the last line, but never so late that the next line loses its minimum gap
      // (5 s is the longest a line can take, so both gaps stay at least LINE_MIN_GAP_S).
      const t = Math.round(lastEnd + Math.min(10, (until - lastEnd - 5) / 2));
      if (t >= match.duration) break;
      const text = fillerText(match, player, t, mode, lang, fillers++);
      withFiller.push({ t, type: "filler", importance: 0.1, text, events: [] });
      lastEnd = t + speechSeconds(text);
    }
  };
  for (const c of picked) {
    pushFillersUntil(c.t);
    withFiller.push(c);
    lastEnd = c.t + speechSeconds(c.text);
  }
  pushFillersUntil(match.duration);

  return withFiller.map((c, i) => {
    const line: CommentaryLine = {
      id: `tpl_${match.id}_${player}_${mode}_${lang}_${String(i).padStart(4, "0")}`,
      t: c.t,
      duration: Math.round(speechSeconds(c.text) * 10) / 10,
      player,
      type: c.type,
      importance: c.importance,
      text: c.text,
      audio_url: null,
      fact_check: "template",
    };
    lineEvents.set(line.id, { line, events: c.events });
    return line;
  });
}
