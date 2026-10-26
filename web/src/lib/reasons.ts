/**
 * Rating log reason text (specs/frontend.md, "Rating log reason text"). ratings.json stores a
 * reason_code and values, never text; these templates turn them into English or Spanish.
 * Draft wording (owner checks it). Spanish follows Mexican football media (ESPN Deportes, TUDN,
 * Fox Sports México): atajar, fuera de lugar, penal, pelota, disparo, portería, portero (decision Oct 26).
 * A missing optional value drops its clause instead of failing.
 */
import type { Lang } from "../types";

export type ReasonValues = Record<string, string | number | boolean | undefined>;
/** Turns a player id into "#6 J. Pereira"; returns "" for unknown ids. */
export type NameOf = (id: string) => string;

type Template = (v: ReasonValues, name: (key: string) => string, num: (key: string, digits: number) => string) => string;

/** Picks `withValue` when every listed value is present, otherwise `bare`. */
const opt = (present: boolean, withValue: string, bare: string) => (present ? withValue : bare);

const EN: Record<string, Template> = {
  goal: (_v, _n, x) => opt(!!x("xg", 2), `Scored (xG ${x("xg", 2)})`, "Scored"),
  assist: (_v, n) => opt(!!n("scorer"), `Assisted ${n("scorer")}`, "Assist"),
  key_pass: (_v, n) => opt(!!n("receiver"), `Key pass to ${n("receiver")}`, "Key pass"),
  shot_on_target: (_v, _n, x) => opt(!!x("xg", 2), `Shot on target (xG ${x("xg", 2)})`, "Shot on target"),
  big_chance_missed: (_v, _n, x) => opt(!!x("xg", 2), `Missed a big chance (xG ${x("xg", 2)})`, "Missed a big chance"),
  tackle: (_v, n) => opt(!!n("opponent"), `Won the ball from ${n("opponent")}`, "Won the ball"),
  dispossessed: (_v, n) => opt(!!n("opponent"), `Dispossessed by ${n("opponent")}`, "Dispossessed"),
  interception: (_v, n) => opt(!!n("passer"), `Intercepted ${n("passer")}'s pass`, "Intercepted a pass"),
  block: (_v, n) => opt(!!n("shooter"), `Blocked ${n("shooter")}'s shot`, "Blocked a shot"),
  clearance: () => "Cleared the danger",
  aerial_duel_won: (_v, n) => opt(!!n("opponent"), `Won a header against ${n("opponent")}`, "Won a header"),
  dribble: (_v, n) => opt(!!n("opponent"), `Beat ${n("opponent")}`, "Beat his man"),
  beaten_by_dribble: (_v, n) => opt(!!n("opponent"), `Beaten by ${n("opponent")}`, "Beaten by a dribble"),
  foul_won: (_v, n) => opt(!!n("opponent"), `Fouled by ${n("opponent")}`, "Won a foul"),
  foul_committed: (_v, n) => opt(!!n("opponent"), `Fouled ${n("opponent")}`, "Committed a foul"),
  handball: () => "Handball",
  offside: () => "Caught offside",
  card_yellow: () => "Yellow card",
  card_red: () => "Sent off",
  error_leading_to_goal: () => "Error leading to a goal",
  error_leading_to_goal_earlier: () => "Mistake in the move that led to a goal",
  gk_save: (_v, n, x) =>
    `${opt(!!n("shooter"), `Saved from ${n("shooter")}`, "Made a save")}${opt(!!x("xg", 2), ` (xG ${x("xg", 2)})`, "")}`,
  gk_goal_conceded: (_v, n, x) =>
    `${opt(!!n("scorer"), `Beaten by ${n("scorer")}`, "Conceded a goal")}${opt(!!x("xg", 2), ` (xG ${x("xg", 2)})`, "")}`,
  gk_claim: () => "Claimed the cross",
  gk_sweep: () => "Swept up behind the defence",
  counterpress: (_v, n) =>
    opt(!!n("opponent"), `Pressed ${n("opponent")} straight after losing the ball`, "Pressed straight after losing the ball"),
  pressure_regain: (_v, n) =>
    opt(!!n("opponent"), `Pressed ${n("opponent")} and the team won the ball back`, "Pressed and the team won the ball back"),
  recovery_run: (_v, _n, x) =>
    opt(!!x("distance_m", 0), `Sprinted ${x("distance_m", 0)} m back to defend`, "Sprinted back to defend"),
  marking_denial: (_v, n) => opt(!!n("opponent"), `Marked ${n("opponent")} out of the game`, "Marked his man out of the game"),
  decoy_run: (_v, n) =>
    n("opponent") && n("teammate")
      ? `Run dragged ${n("opponent")} away, freeing ${n("teammate")}`
      : "Decoy run opened space",
  shape_kept: () => "Held position in the team shape",
  shape_out_of_position: (_v, _n, x) =>
    opt(!!x("deviation_m", 0), `Out of position (${x("deviation_m", 0)} m from shape)`, "Out of position"),
  shape_walking: () => "Walking while out of position",
  shape_no_change: () => "",
};

const ES: Record<string, Template> = {
  goal: (_v, _n, x) => opt(!!x("xg", 2), `Gol (xG ${x("xg", 2)})`, "Gol"),
  assist: (_v, n) => opt(!!n("scorer"), `Asistencia a ${n("scorer")}`, "Asistencia"),
  key_pass: (_v, n) => opt(!!n("receiver"), `Pase clave a ${n("receiver")}`, "Pase clave"),
  shot_on_target: (_v, _n, x) => opt(!!x("xg", 2), `Disparo a portería (xG ${x("xg", 2)})`, "Disparo a portería"),
  big_chance_missed: (_v, _n, x) => opt(!!x("xg", 2), `Falló una ocasión clara (xG ${x("xg", 2)})`, "Falló una ocasión clara"),
  tackle: (_v, n) => opt(!!n("opponent"), `Le robó la pelota a ${n("opponent")}`, "Robó la pelota"),
  dispossessed: (_v, n) => opt(!!n("opponent"), `Perdió la pelota ante ${n("opponent")}`, "Perdió la pelota"),
  interception: (_v, n) => opt(!!n("passer"), `Interceptó el pase de ${n("passer")}`, "Interceptó un pase"),
  block: (_v, n) => opt(!!n("shooter"), `Bloqueó el disparo de ${n("shooter")}`, "Bloqueó un disparo"),
  clearance: () => "Despejó el peligro",
  aerial_duel_won: (_v, n) => opt(!!n("opponent"), `Le ganó el duelo aéreo a ${n("opponent")}`, "Ganó un duelo aéreo"),
  dribble: (_v, n) => opt(!!n("opponent"), `Regateó a ${n("opponent")}`, "Ganó el uno contra uno"),
  beaten_by_dribble: (_v, n) => opt(!!n("opponent"), `Lo regateó ${n("opponent")}`, "Perdió el uno contra uno"),
  foul_won: (_v, n) => opt(!!n("opponent"), `Recibió una falta de ${n("opponent")}`, "Recibió una falta"),
  foul_committed: (_v, n) => opt(!!n("opponent"), `Cometió falta sobre ${n("opponent")}`, "Cometió una falta"),
  handball: () => "Mano",
  offside: () => "Quedó en fuera de lugar",
  card_yellow: () => "Tarjeta amarilla",
  card_red: () => "Expulsado",
  error_leading_to_goal: () => "Error que acabó en gol",
  error_leading_to_goal_earlier: () => "Fallo en la jugada que acabó en gol",
  gk_save: (_v, n, x) =>
    `${opt(!!n("shooter"), `Le atajó el disparo a ${n("shooter")}`, "Hizo una atajada")}${opt(!!x("xg", 2), ` (xG ${x("xg", 2)})`, "")}`,
  gk_goal_conceded: (_v, n, x) =>
    `${opt(!!n("scorer"), `Lo batió ${n("scorer")}`, "Encajó un gol")}${opt(!!x("xg", 2), ` (xG ${x("xg", 2)})`, "")}`,
  gk_claim: () => "Atajó el centro",
  gk_sweep: () => "Salió de su área para cortar a la espalda de la defensa",
  counterpress: (_v, n) =>
    opt(!!n("opponent"), `Presión tras pérdida sobre ${n("opponent")}`, "Presión tras pérdida"),
  pressure_regain: (_v, n) =>
    opt(!!n("opponent"), `Presionó a ${n("opponent")} y el equipo recuperó la pelota`, "Presionó y el equipo recuperó la pelota"),
  recovery_run: (_v, _n, x) =>
    opt(!!x("distance_m", 0), `Sprint de ${x("distance_m", 0)} m para replegar`, "Replegó a toda velocidad"),
  marking_denial: (_v, n) => opt(!!n("opponent"), `Anuló a ${n("opponent")} con su marca`, "Anuló a su marca"),
  decoy_run: (_v, n) =>
    n("opponent") && n("teammate")
      ? `Su desmarque arrastró a ${n("opponent")} y liberó a ${n("teammate")}`
      : "Su desmarque abrió espacio",
  shape_kept: () => "Mantuvo su posición en el bloque",
  shape_out_of_position: (_v, _n, x) =>
    opt(!!x("deviation_m", 0), `Descolocado (a ${x("deviation_m", 0)} m de su posición)`, "Descolocado"),
  shape_walking: () => "Caminaba estando descolocado",
  shape_no_change: () => "",
};

/** Every reason code the frontend knows (34, specs/frontend.md). */
export const REASON_CODES = Object.keys(EN);

/** Localized reason text for one rating entry. Unknown codes fall back to the code itself. */
export function reasonText(code: string, values: ReasonValues | undefined, lang: Lang, nameOf: NameOf): string {
  const v = values ?? {};
  const table = lang === "es" ? ES : EN;
  // own keys only, so a code like "constructor" can't pick up an Object.prototype member
  const template = Object.hasOwn(table, code) ? table[code] : undefined;
  if (!template) return code.replace(/_/g, " ");
  const name = (key: string) => (typeof v[key] === "string" ? nameOf(v[key] as string) : "");
  const num = (key: string, digits: number) => (typeof v[key] === "number" ? (v[key] as number).toFixed(digits) : "");
  return template(v, name, num);
}
