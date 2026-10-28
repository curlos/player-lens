"""Fake model and fake Speech for tests: same interfaces as FoundryLLM and SpeechClient, never touching Azure."""

from __future__ import annotations

from typing import Any

from agents.llm import LLMError
from agents.speech import Clip, clip_hash, duration_of


class FakeLLM:
    """Answers each agent from its payload, like a well-behaved model. ``bad_line`` makes the Commentator say something unsupported
    once, so Fact Guard has to fix it. ``fail`` lists agents that always raise LLMError."""

    def __init__(self, bad_line: str | None = None, fail: tuple[str, ...] = (), fix_text: str | None = None, delay: float = 0.0,
                 explode: bool = False, flaky: tuple[str, ...] = ()):
        self.calls: list[str] = []
        self.bad_line = bad_line
        self.fail = fail
        self.fix_text = fix_text
        self.payloads: dict[str, dict[str, Any]] = {}
        self.delay = delay  # seconds each call takes (to test in-flight dedupe)
        self.explode = explode  # raise an unexpected error, as a bug would
        self.flaky = set(flaky)  # agents whose first call fails and second succeeds

    async def complete(self, agent: str, payload: dict[str, Any], *, key: str) -> dict[str, Any]:
        import asyncio

        self.calls.append(agent)
        self.payloads[agent] = payload
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.explode:
            raise RuntimeError("unexpected bug")
        if agent in self.flaky:
            self.flaky.discard(agent)
            raise LLMError(f"{agent} hiccup")
        if agent in self.fail:
            raise LLMError(f"{agent} is down")
        if agent == "interpreter":
            return {"labels": {f["fact_id"]: "a neutral description of the fact" for f in payload["facts"]}}
        if agent == "moments":
            return {"moments": [{"moment_id": m["moment_id"], "tone": "excited" if m["importance"] >= 0.8 else "calm", "why": "It matters to the player."}
                                for m in payload["moments"]]}
        if agent == "commentator":
            lines = []
            for m in payload["moments"]:
                values = m["facts"][0]["values"]
                text = f"{values.get('scorer', 'Lima')} keeps playing well in this minute of the match."
                if m["trigger"] == "goal" and self.bad_line:
                    text = self.bad_line
                lines.append({"moment_id": m["moment_id"], "text": text, "fact_ids_used": [f["fact_id"] for f in m["facts"]]})
            return {"lines": lines}
        if agent == "fact_guard":
            fixed = self.fix_text or "Lima fires it home, and it is {score}!"
            return {"fixes": [{"moment_id": x["moment_id"], "text": fixed.format(score=x["facts"][0]["values"].get("score", "1-0"))} for x in payload["lines"]]}
        if agent == "personalizer":
            return {"variants": [{"moment_id": x["moment_id"], "text": x["text"]} for x in payload["lines"]]}
        if agent == "voice_director":
            return {"directions": [{"moment_id": x["moment_id"], "pauses": [], "emphasis": [], "rate": "fast" if x["tone"] == "excited" else "normal",
                                    "style": "default"} for x in payload["lines"]]}
        if agent == "recap":
            if payload.get("lang") == "es":  # 40 to 90 words, like a real recap, or Fact Guard sends it to the template
                return {"text": "Lima termina con 8.9 tras un gran triunfo de Azure City. Anotó 2 goles, recorrió 11.2 km y trabajó sin descanso para su "
                                "equipo de principio a fin, presionando sin parar y con mucho esfuerzo sin la pelota durante todo el partido, siempre "
                                "atento a cada jugada."}
            return {"text": "Lima finishes on 8.9 after a big win for Azure City. He scored 2 goals, covered 11.2 km and kept working hard for his "
                            "team from the first minute to the last, pressing high and giving the defence a difficult afternoon all match long."}
        raise AssertionError(agent)


class FakeSpeech:
    """Returns a clip for any line without a network call; remembers what it was asked to say."""

    def __init__(self):
        self.said: list[tuple[str, str, str]] = []

    async def synth(self, text: str, voice: str, ssml: str, *, key: str) -> Clip:
        self.said.append((text, voice, ssml))
        h = clip_hash(text, voice, ssml)
        return Clip(h, duration_of(b"x" * 24000), f"/audio/{h}.mp3")
