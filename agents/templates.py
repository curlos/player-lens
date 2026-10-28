"""Template fallback lines (specs/agents-backend.md, "Template fallback").

Used whenever an LLM step fails twice, a spend cap is hit, or Foundry is unreachable. Written by code from a
moment's facts, in Casual or Analyst and English or Mexican Spanish (atajar, fuera de lugar, penal, pelota,
disparo, portería, portero, regate). Every candidate is run through Fact Guard before it is returned, so a
template can never state something the facts don't; the last resort is a bland line that always passes.
"""

from __future__ import annotations

import re
import string
from typing import Any

from agents import config as C
from agents.fact_guard import check_line
from agents.inputs import MatchBundle
from agents.models import Fact, Moment

# What the selected player does, for filler lines (activity codes from meta.activities).
ACTIVITY = {
    "en": {
        "stand": "standing firm", "walk": "walking back into shape", "jog": "jogging into position", "run": "on the move",
        "sprint": "sprinting", "carry": "driving forward with the ball", "press": "pressing the ball carrier",
        "track_back": "tracking back", "mark": "staying tight to the marker", "make_run": "making a run in behind",
        "hold_shape": "holding the team shape", "talk_ref": "having a word with the referee", "huddle": "in the huddle",
        "celebrate": "celebrating", "down": "down on the turf", "wall": "lining up in the wall",
        "set_piece_wait": "waiting for the set piece", "take_set_piece": "standing over the set piece", "sent_off": "walking off",
    },
    "es": {
        "stand": "firme en su zona", "walk": "volviendo a su posición", "jog": "trotando hacia su posición", "run": "en movimiento",
        "sprint": "esprintando", "carry": "conduciendo la pelota", "press": "presionando al rival", "track_back": "replegando",
        "mark": "pegado a su marca", "make_run": "atacando el espacio a la espalda", "hold_shape": "manteniendo el orden del equipo",
        "talk_ref": "hablando con el árbitro", "huddle": "reunido con sus compañeros", "celebrate": "celebrando",
        "down": "tendido en el césped", "wall": "colocado en la barrera", "set_piece_wait": "esperando el cobro",
        "take_set_piece": "listo para el cobro", "sent_off": "camino al vestidor",
    },
}
DEFAULT_ACTIVITY = {"en": "working across the pitch", "es": "moviéndose por todo el campo"}

# "{who} <phrase>": the player's own rating-log moments. The first phrase needs the named value, the second does not.
PHRASES: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        "shot_on_target": ("puts a shot on target", "puts a shot on target"),
        "big_chance_missed": ("misses a big chance", "misses a big chance"),
        "key_pass": ("plays a key pass to {receiver}", "plays a key pass"),
        "assist": ("sets up {scorer}", "sets up a teammate"),
        "tackle": ("wins the ball from {opponent}", "wins the ball back"),
        "interception": ("intercepts {passer}'s pass", "intercepts a pass"),
        "block": ("blocks {shooter}'s shot", "blocks a shot"),
        "clearance": ("clears the danger", "clears the danger"),
        "aerial_duel_won": ("wins a header against {opponent}", "wins a header"),
        "dribble": ("dribbles past {opponent}", "dribbles past a defender"),
        "beaten_by_dribble": ("is beaten by {opponent}'s dribble", "is beaten by a dribble"),
        "dispossessed": ("is dispossessed by {opponent}", "is dispossessed"),
        "foul_won": ("is fouled by {opponent}", "wins a foul"),
        "foul_committed": ("fouls {opponent}", "commits a foul"),
        "handball": ("is penalised for handball", "is penalised for handball"),
        "offside": ("is caught offside", "is caught offside"),
        "counterpress": ("presses {opponent} right after losing the ball", "presses right after losing the ball"),
        "pressure_regain": ("presses {opponent} and the team wins the ball back", "presses and the team wins the ball back"),
        "recovery_run": ("sprints {distance_m} m back to defend", "sprints back to defend"),
        "marking_denial": ("marks {opponent} out of the game", "marks the opponent out of the game"),
        "decoy_run": ("drags {opponent} away, freeing {teammate}", "makes a decoy run that opens space"),
        "error_leading_to_goal": ("makes an error that leads to a goal", "makes an error that leads to a goal"),
        "error_leading_to_goal_earlier": ("makes a mistake earlier in the move for a goal", "makes a mistake earlier in the move for a goal"),
        "gk_save": ("saves from {shooter}", "makes a save"),
        "gk_goal_conceded": ("is beaten by {scorer}", "is beaten"),
        "gk_claim": ("claims the ball in the air", "claims the ball in the air"),
        "gk_sweep": ("sweeps up behind the defence", "sweeps up behind the defence"),
        "card_yellow": ("is shown a yellow card", "is shown a yellow card"),
        "card_red": ("is sent off", "is sent off"),
        "shape_kept": ("holds his place in the team shape", "holds his place in the team shape"),
        "shape_out_of_position": ("drifts {deviation_m} m out of position", "drifts out of position"),
        "shape_walking": ("walks while out of position", "walks while out of position"),
    },
    "es": {
        "shot_on_target": ("manda un disparo a portería", "manda un disparo a portería"),
        "big_chance_missed": ("falla una ocasión clara", "falla una ocasión clara"),
        "key_pass": ("da un pase clave a {receiver}", "da un pase clave"),
        "assist": ("asiste a {scorer}", "asiste a un compañero"),
        "tackle": ("le roba la pelota a {opponent}", "roba la pelota"),
        "interception": ("intercepta el pase de {passer}", "intercepta un pase"),
        "block": ("bloquea el disparo de {shooter}", "bloquea un disparo"),
        "clearance": ("despeja el peligro", "despeja el peligro"),
        "aerial_duel_won": ("gana un duelo aéreo a {opponent}", "gana un duelo aéreo"),
        "dribble": ("regatea a {opponent}", "regatea a un defensa"),
        "beaten_by_dribble": ("pierde el uno contra uno ante {opponent}", "pierde el uno contra uno"),
        "dispossessed": ("pierde la pelota ante {opponent}", "pierde la pelota"),
        "foul_won": ("recibe una falta de {opponent}", "recibe una falta"),
        "foul_committed": ("comete falta sobre {opponent}", "comete una falta"),
        "handball": ("comete mano", "comete mano"),
        "offside": ("queda en fuera de lugar", "queda en fuera de lugar"),
        "counterpress": ("presiona a {opponent} tras perder la pelota", "presiona tras perder la pelota"),
        "pressure_regain": ("presiona a {opponent} y su equipo gana la pelota", "presiona y su equipo gana la pelota"),
        "recovery_run": ("corre {distance_m} m para replegar", "corre para replegar"),
        "marking_denial": ("anula a {opponent} con su marca", "anula a su marca"),
        "decoy_run": ("arrastra a {opponent} y libera a {teammate}", "hace un desmarque que abre espacio"),
        "error_leading_to_goal": ("comete un error que acaba en gol", "comete un error que acaba en gol"),
        "error_leading_to_goal_earlier": ("falla en la jugada que acaba en gol", "falla en la jugada que acaba en gol"),
        "gk_save": ("ataja el disparo de {shooter}", "hace una atajada"),
        "gk_goal_conceded": ("queda batido por {scorer}", "queda batido"),
        "gk_claim": ("atrapa el centro", "atrapa el centro"),
        "gk_sweep": ("sale a despejar detrás de la defensa", "sale a despejar detrás de la defensa"),
        "card_yellow": ("ve la tarjeta amarilla", "ve la tarjeta amarilla"),
        "card_red": ("es expulsado", "es expulsado"),
        "shape_kept": ("mantiene su posición en el bloque", "mantiene su posición en el bloque"),
        "shape_out_of_position": ("queda descolocado a {deviation_m} metros de su posición", "queda descolocado"),
        "shape_walking": ("camina estando descolocado", "camina estando descolocado"),
    },
}

# Frames: key -> (lang, mode) -> candidate templates, tried in rotation.
T: dict[str, dict[tuple[str, str], list[str]]] = {
    "goal_self": {
        ("en", "casual"): ["GOAL! {who} fires it home, and it is {score}!", "{who} scores! A big moment, and it is {score}.", "What a finish from {who}! It is {score}!"],
        ("en", "analyst"): ["{who} scores from an xG {xg} chance. It is {score}.", "{who} finishes an xG {xg} chance, and it is {score}."],
        ("es", "casual"): ["¡GOL! {who} la manda al fondo y es {score}!", "¡{who} anota! Un momento enorme, {score}.", "¡Qué definición de {who}! Es {score}!"],
        ("es", "analyst"): ["{who} define una ocasión de xG {xg}. Es {score}.", "{who} anota con un xG de {xg}, y es {score}."],
    },
    "goal_assist": {
        ("en", "casual"): ["{who} sets it up and {scorer} scores! It is {score}!", "{who} lays it on for {scorer}, who scores. {score}!"],
        ("en", "analyst"): ["{who} assists {scorer}'s goal, an xG {xg} chance. It is {score}."],
        ("es", "casual"): ["¡{who} asiste y {scorer} anota! Es {score}!", "{who} se la deja a {scorer} y es gol. {score}!"],
        ("es", "analyst"): ["{who} asiste a {scorer} en una ocasión de xG {xg}. Es {score}."],
    },
    "goal_other": {
        ("en", "casual"): ["{scorer} scores for {team}, and it is {score}.", "Goal for {team}! {scorer} scores, and it is {score}."],
        ("en", "analyst"): ["{scorer} scores for {team} from an xG {xg} chance. It is {score}."],
        ("es", "casual"): ["{scorer} anota para {team}, y es {score}.", "¡Gol de {team}! Anota {scorer}, {score}."],
        ("es", "analyst"): ["{scorer} anota para {team} con un xG de {xg}. Es {score}."],
    },
    "react_self": {
        ("en", "casual"): ["{who} wheels away to celebrate. What a moment."], ("en", "analyst"): ["{who} wheels away to celebrate. What a moment."],
        ("es", "casual"): ["{who} lo celebra con los suyos. Qué momento."], ("es", "analyst"): ["{who} lo celebra con los suyos. Qué momento."],
    },
    "react_team": {
        ("en", "casual"): ["{team} celebrate. Now to keep a cool head."], ("en", "analyst"): ["{team} celebrate. Now to keep a cool head."],
        ("es", "casual"): ["{team} lo celebra. Ahora toca mantener la cabeza fría."], ("es", "analyst"): ["{team} lo celebra. Ahora toca mantener la cabeza fría."],
    },
    "react_against": {
        ("en", "casual"): ["A blow for {selected_team}. Time to respond."], ("en", "analyst"): ["A blow for {selected_team}. Time to respond."],
        ("es", "casual"): ["Un golpe para {selected_team}. Toca reaccionar ya."], ("es", "analyst"): ["Un golpe para {selected_team}. Toca reaccionar ya."],
    },
    "yellow_self": {
        ("en", "casual"): ["Yellow card for {who}. Time to be careful now."], ("en", "analyst"): ["Yellow card for {who}. Time to be careful now."],
        ("es", "casual"): ["Tarjeta amarilla para {who}. Ahora hay que medir cada entrada."], ("es", "analyst"): ["Tarjeta amarilla para {who}. Ahora hay que medir cada entrada."],
    },
    "yellow_other": {
        ("en", "casual"): ["{player} of {team} goes into the referee's book."], ("en", "analyst"): ["{player} of {team} goes into the referee's book."],
        ("es", "casual"): ["{player} de {team} ve la tarjeta amarilla."], ("es", "analyst"): ["{player} de {team} ve la tarjeta amarilla."],
    },
    "red_self": {
        ("en", "casual"): ["Red card! {who} is sent off. What a blow."], ("en", "analyst"): ["Red card! {who} is sent off. What a blow."],
        ("es", "casual"): ["¡Tarjeta roja! {who} es expulsado. Qué golpe."], ("es", "analyst"): ["¡Tarjeta roja! {who} es expulsado. Qué golpe."],
    },
    "red_other": {
        ("en", "casual"): ["Red card! {player} of {team} is sent off."], ("en", "analyst"): ["Red card! {player} of {team} is sent off."],
        ("es", "casual"): ["¡Tarjeta roja! {player} de {team} es expulsado."], ("es", "analyst"): ["¡Tarjeta roja! {player} de {team} es expulsado."],
    },
    "penalty": {
        ("en", "casual"): ["Penalty to {team}! A huge moment in this match."], ("en", "analyst"): ["Penalty to {team}! A huge moment in this match."],
        ("es", "casual"): ["¡Penal para {team}! Un momento enorme del partido."], ("es", "analyst"): ["¡Penal para {team}! Un momento enorme del partido."],
    },
    "event": {
        ("en", "casual"): ["{who} {phrase}.", "Nice bit of work: {who} {phrase}.", "{who} {phrase}, and the team benefits."],
        ("en", "analyst"): ["{who} {phrase}. Rating {rating_after}, {delta}.", "{who} {phrase}, taking the rating to {rating_after}."],
        ("es", "casual"): ["{who} {phrase}.", "Buen trabajo: {who} {phrase}.", "{who} {phrase}, y el equipo lo agradece."],
        ("es", "analyst"): ["{who} {phrase}. Nota {rating_after}, {delta}.", "{who} {phrase} y sube su nota a {rating_after}."],
    },
    # a rating change that went down: said plainly, never as praise
    "event_neg": {
        ("en", "casual"): ["{who} {phrase}.", "Unlucky: {who} {phrase}.", "{who} {phrase}, and that costs him."],
        ("en", "analyst"): ["{who} {phrase}. Rating {rating_after}, {delta}.", "{who} {phrase}, and the rating drops to {rating_after}."],
        ("es", "casual"): ["{who} {phrase}.", "Mala suerte: {who} {phrase}.", "{who} {phrase} y eso le cuesta."],
        ("es", "analyst"): ["{who} {phrase}. Nota {rating_after}, {delta}.", "{who} {phrase} y su nota baja a {rating_after}."],
    },
    "filler": {
        ("en", "casual"): ["{who} has covered {distance_km} km so far.", "{who} is up to {distance_km} km already!",
                           "{who} is rated {rating} right now.", "{who}'s rating stands at {rating} right now.",
                           "And here is {who}, {activity}.", "Look at {who} now, {activity}."],
        ("en", "analyst"): ["{who} has covered {distance_km} km in this match.", "{who} carries a rating of {rating} right now.",
                            "{who} is {activity} at the moment."],
        ("es", "casual"): ["{who} ya lleva {distance_km} km recorridos.", "¡{who} ya suma {distance_km} km en el partido!",
                           "{who} tiene una nota de {rating} ahora mismo.", "La nota de {who} está en {rating} ahora.",
                           "Ahí está {who}, que sigue {activity}.", "Atención a {who}, que sigue {activity}."],
        ("es", "analyst"): ["{who} lleva {distance_km} km recorridos en el partido.", "{who} tiene una nota de {rating} en este momento.",
                            "{who} sigue {activity} en este momento."],
    },
    "play": {
        ("en", "casual"): ["{play} {zone}.", "Now {play} {zone}."],
        ("en", "analyst"): ["{play} {zone}.", "{team} on the ball: {play} {zone}."],
        ("es", "casual"): ["{play} {zone_es}.", "Ahora {play} {zone_es}."],
        ("es", "analyst"): ["{play} {zone_es}.", "{team} con la pelota: {play} {zone_es}."],
    },
    "fallback": {
        ("en", "casual"): ["{who} keeps working across the pitch in minute {minute}."], ("en", "analyst"): ["{who} keeps working across the pitch in minute {minute}."],
        ("es", "casual"): ["{who} sigue trabajando por todo el campo en el minuto {minute}."], ("es", "analyst"): ["{who} sigue trabajando por todo el campo en el minuto {minute}."],
    },
}


# What the player on the ball does, for play lines (one per Fact Guard action category; the words must match it).
PLAY_PHRASES = {
    "en": {"pass": "{actor} moves it on for {team}", "dribble": "{actor} takes on his man", "tackle": "{actor} wins it with a tackle",
           "interception": "{actor} intercepts for {team}", "header": "{actor} goes up for the header", "clearance": "{actor} clears it",
           "block": "{actor} blocks it", "shot": "{actor} shoots for {team}", "save": "{actor} makes the save",
           "press": "{actor} presses for {team}", "foul": "{actor} gives away a foul", "offside": "{actor} is flagged offside",
           "restart": "{team} restart play"},
    "es": {"pass": "{actor} mueve la pelota para {team}", "dribble": "{actor} encara con un regate", "tackle": "{actor} gana con una entrada",
           "interception": "{actor} intercepta para {team}", "header": "{actor} va de cabeza", "clearance": "{actor} despeja",
           "block": "{actor} bloquea", "shot": "{actor} dispara para {team}", "save": "{actor} ataja",
           "press": "{actor} presiona para {team}", "foul": "{actor} comete falta", "offside": "{actor} queda en fuera de lugar",
           "restart": "{team} reanuda el juego"},
}


def _surname(name: str) -> str:
    return name.split(". ", 1)[-1]


def _fields(primary: Fact, facts: list[Fact], moment: Moment, bundle: MatchBundle, selected: str, lang: str) -> dict[str, str]:
    """String fields the templates may use, all taken from fact values (code-computed) and the roster."""
    me = bundle.players[selected]
    f: dict[str, str] = {
        "who": _surname(me.name), "selected_team": bundle.team_name[bundle.team_of[selected]], "minute": str(int(moment.t // 60) + 1),
    }
    for fact in facts:
        for key, val in fact.values.items():
            if isinstance(val, bool):
                continue
            if key in ("scorer", "assister", "opponent", "passer", "shooter", "receiver", "teammate", "player") and isinstance(val, str):
                f[key] = _surname(val) if key != "player" else val
            elif key == "delta" and isinstance(val, (int, float)):
                f[key] = f"{val:+.2f}"
            elif key in ("rating_after", "rating") and isinstance(val, (int, float)):
                f[key] = f"{val:.1f}"
            elif key == "distance_km" and isinstance(val, (int, float)):
                f[key] = f"{val:.1f}"
            elif key == "distance_m" and isinstance(val, (int, float)):
                f[key] = f"{val:.0f}"
            elif key == "xg":
                f[key] = f"{float(val):.2f}"
            elif isinstance(val, (str, int, float)):
                f.setdefault(key, str(val))
    if "assister" in f:
        f["assister"] = f["assister"]
    if primary.values.get("scorer"):
        f["scorer"] = _surname(str(primary.values["scorer"]))
    if "minute" in primary.values:  # a reaction line is a few seconds after the goal: use the fact's own minute
        f["minute"] = str(primary.values["minute"])
    act = str(primary.values.get("activity", ""))
    f["activity"] = ACTIVITY[lang].get(act, DEFAULT_ACTIVITY[lang])
    if primary.kind == "play":
        f["actor"] = _surname(str(primary.values.get("actor", "")))
        f["team"] = str(primary.values.get("team", ""))
        f["play"] = PLAY_PHRASES[lang].get(str(primary.values.get("action")), PLAY_PHRASES[lang]["restart"]).format_map(f)
    return f


def _key(primary: Fact, moment: Moment, selected: str, bundle: MatchBundle) -> str:
    me = bundle.players[selected]
    my_team = bundle.team_name[bundle.team_of[selected]]
    v = primary.values
    if moment.trigger == "reaction":
        if v.get("selected_scored"):
            return "react_self"
        return "react_team" if v.get("team") == my_team else "react_against"
    if primary.kind == "goal":
        return "goal_self" if v.get("selected_scored") else "goal_assist" if v.get("selected_assisted") else "goal_other"
    if primary.kind == "card":
        mine = v.get("player") == me.name
        return f"{v['card']}_{'self' if mine else 'other'}"
    if primary.kind == "foul" and v.get("action") == "penalty awarded":
        return "penalty"
    if primary.kind == "filler_stat":
        return "filler"
    if primary.kind == "play":
        return "play"
    return "event"


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def template_line(moment: Moment, facts: list[Fact], bundle: MatchBundle, selected: str, mode: str, lang: str) -> str:
    """A fact-checked template line for one moment, mode and language (never raises; always returns a line)."""
    primary = next((f for f in facts if f.fact_id == moment.fact_ids[0]), facts[0])
    fields = _fields(primary, facts, moment, bundle, selected, lang)
    key = _key(primary, moment, selected, bundle)
    negative = key == "event" and float(primary.values.get("delta", 0) or 0) < 0
    candidates = list(T["event_neg" if negative else key][(lang, mode)])
    if key == "event":
        code = str(primary.values.get("reason_code", ""))
        with_val, bare = PHRASES[lang].get(code, ("", ""))
        if not with_val:
            candidates = []  # no phrase for this reason: fall through to the fallback line
        else:
            phrase = with_val if _placeholders(with_val) <= fields.keys() else bare
            fields["phrase"] = phrase.format_map(fields)
    if key == "filler":  # only the frames for this stat line's topic, rotated so consecutive ones differ
        slot = {"distance": "{distance_km}", "rating": "{rating}", "activity": "{activity}"}.get(str(primary.values.get("topic")), "")
        candidates = [c for c in candidates if slot in c]
        if candidates:
            candidates = candidates[int(moment.t // 7) % len(candidates):] + candidates[: int(moment.t // 7) % len(candidates)]
    candidates += T["fallback"][(lang, mode)]
    for template in candidates:
        if not _placeholders(template) <= fields.keys():
            continue
        text = template.format_map(fields)
        if not check_line(text, facts=facts, bundle=bundle, selected=selected, t=moment.t, lang=lang):
            return text
    return T["fallback"][(lang, mode)][0].format_map(fields)  # facts-free, so it cannot be wrong
