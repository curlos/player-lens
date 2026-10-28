"""Azure AI Speech: turns a finished line plus the Voice Director's instructions into an MP3 clip.

Plain code, not an agent (specs/agents-backend.md, step 7). The clip is cached by a hash of (text, voice, ssml), so
an identical line is synthesized once and shared. Clip length comes from the byte count: the output format is
constant bitrate (48 kbps), so seconds = bytes * 8 / 48000, with no audio tool needed.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import httpx

from agents import config as C
from agents.models import VoiceDirection
from app.budget import Budget
from app.settings import Settings


class SpeechError(Exception):
    """Synthesis failed or returned something that is not an MP3."""


@dataclass
class Clip:
    audio_hash: str
    duration_s: float
    audio_url: str


def clip_hash(text: str, voice: str, ssml: str) -> str:
    """Cache key: identical text, voice and markup share one clip."""
    return hashlib.sha256(f"{text}\0{voice}\0{ssml}".encode("utf-8")).hexdigest()[:32]


def duration_of(mp3: bytes) -> float:
    return round(len(mp3) * 8 / C.SPEECH_BITRATE, 1)


def looks_like_mp3(data: bytes) -> bool:
    return data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


# What the voice should say for written units; the on-screen text keeps "km". One word in, one word out, so pause and
# emphasis positions (word indexes) stay valid. A bare "m" is only a unit right after a number.
SPOKEN_UNITS = {
    "en": {"km": "kilometres", "km/h": "kilometres per hour", "kph": "kilometres per hour", "xg": "expected goals", "m": "metres"},
    "es": {"km": "kilómetros", "km/h": "kilómetros por hora", "kph": "kilómetros por hora", "xg": "goles esperados", "m": "metros"},
}


def spoken(word: str, previous: str, lang: str) -> str:
    """The word as the voice should say it: units spelled out (``km`` -> ``kilometres``), punctuation kept."""
    core = word.strip(".,!¡¿?;:")
    full = SPOKEN_UNITS[lang].get(core.lower())
    if full is None or (core.lower() == "m" and not previous.strip(".,").replace(".", "").isdigit()):
        return word
    return word.replace(core, full, 1)


def build_ssml(text: str, voice: str, lang: str, direction: VoiceDirection | None = None) -> str:
    """SSML for one line: the words, wrapped in the Voice Director's style (e.g. excited) when the language gets styles."""
    d = direction or VoiceDirection(moment_id="-", mode="casual", lang=lang)  # type: ignore[arg-type]
    words = text.split()
    emphasis = {w.lower().strip(".,!¡¿?") for w in d.emphasis}
    parts = []
    for i, word in enumerate(words):
        bare = word.lower().strip(".,!¡¿?")
        piece = escape(spoken(word, words[i - 1] if i else "", lang))
        if C.SSML_EMPHASIS and bare in emphasis:
            piece = f"<emphasis level='strong'>{piece}</emphasis>"
        parts.append(piece)
        if C.SSML_PAUSES and i in d.pauses and i < len(words) - 1:
            parts.append(f"<break time='{C.PAUSE_MS}ms'/>")
    body = " ".join(parts).replace(" <break", "<break").replace("/> ", "/>")
    if d.style in C.VOICE_STYLES and d.style != "default" and lang in C.STYLE_LANGS:
        body = f"[{d.style}] {body}" if C.STYLE_SYNTAX == "bracket" else f"<mstts:express-as style='{d.style}'>{body}</mstts:express-as>"
    locale = C.SPEECH_LOCALE[lang]
    params = f" parameters='{C.VOICE_PARAMS}'" if C.VOICE_PARAMS and "Omni" in voice else ""
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts' "
            f"xml:lang='{locale}'><voice name='{voice}'{params}>{body}</voice></speak>")


class SpeechClient:
    def __init__(self, settings: Settings, budget: Budget, audio_dir: Path, lookup_dirs: list[Path] | None = None):
        self.s = settings
        self.budget = budget
        self.audio_dir = audio_dir  # where new clips are written
        self.lookup_dirs = [audio_dir, *(lookup_dirs or [])]  # where an existing clip may already be

    def existing(self, audio_hash: str) -> Path | None:
        return next((d / f"{audio_hash}.mp3" for d in self.lookup_dirs if (d / f"{audio_hash}.mp3").is_file()), None)

    async def synth(self, text: str, voice: str, ssml: str, *, key: str) -> Clip:
        """The clip for this line, from disk if it exists, otherwise from Azure (spend-gated, recorded in the ledger)."""
        h = clip_hash(text, voice, ssml)
        found = self.existing(h)
        if found:
            data = found.read_bytes()
            if looks_like_mp3(data):  # a clip cut short by a restart is made again, not served forever
                return Clip(h, duration_of(data), f"/audio/{h}.mp3")
        self.budget.check_speech(len(text))
        url = f"https://{self.s.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self.s.speech_key, "Content-Type": "application/ssml+xml; charset=utf-8",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "player-lens",
        }
        try:
            async with httpx.AsyncClient(timeout=C.SPEECH_TIMEOUT_S) as client:
                response = await client.post(url, content=ssml.encode("utf-8"), headers=headers)
        except httpx.HTTPError as err:
            raise SpeechError(f"speech request failed: {type(err).__name__}") from err
        if response.status_code != 200 or not looks_like_mp3(response.content):
            raise SpeechError(f"speech returned HTTP {response.status_code}")
        self.budget.record_speech(key, len(text))  # Speech bills the spoken text, not the SSML tags
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.audio_dir / f"{h}.mp3.{os.getpid()}.tmp"
        tmp.write_bytes(response.content)
        tmp.replace(self.audio_dir / f"{h}.mp3")  # atomic, so a half-written clip never appears under its final name
        return Clip(h, duration_of(response.content), f"/audio/{h}.mp3")
