"""Plain-file commentary storage, no database (specs/agents-backend.md, "Caching, cap and fallback").

Two roots with the same layout, so baked read-only files are never mixed with runtime writes:
- pre-generated (committed to git, baked into the image): ``data/commentary/`` and ``data/audio/``;
- on-demand (gitignored): ``<persist>/commentary_ondemand/`` and its ``audio/`` folder. ``persist`` defaults to
  ``data/``; in production it is an Azure Files share (``PERSIST_DIR``), so generated chunks survive restarts and
  each one is paid for once.

A chunk is ``<root>/<match>/<player>/<mode>_<lang>_<chunk>.json`` with its traces next to it as
``<mode>_<lang>_<chunk>.trace.json`` (a map of line id to trace). Recaps are ``recap_<mode>_<lang>.json``.
Lookup order is pre-generated, then on-demand. Writes are atomic (temp file, then rename).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agents.models import CommentaryChunk, Recap, Trace

_SAFE = re.compile(r"^[a-z0-9_]+$")


class Store:
    def __init__(self, data_dir: Path, persist_dir: Path | None = None):
        self.data_dir = data_dir
        self.pre = data_dir / "commentary"
        self.ondemand = (persist_dir or data_dir) / "commentary_ondemand"
        self.audio_pre = data_dir / "audio"
        self.audio_ondemand = self.ondemand / "audio"

    # -- helpers -----------------------------------------------------------------------------------------
    def root(self, where: str) -> Path:
        return self.pre if where == "pre" else self.ondemand

    def _dir(self, root: Path, match: str, player: str) -> Path:
        if not (_SAFE.match(match) and _SAFE.match(player)):
            raise ValueError("bad match or player id")
        return root / match / player

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)

    def _read(self, match: str, player: str, name: str) -> dict | None:
        for root in (self.pre, self.ondemand):
            path = self._dir(root, match, player) / name
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    # -- chunks and traces --------------------------------------------------------------------------------
    @staticmethod
    def chunk_name(mode: str, lang: str, chunk: int) -> str:
        return f"{mode}_{lang}_{chunk}"

    def read_chunk(self, match: str, player: str, mode: str, lang: str, chunk: int) -> dict | None:
        return self._read(match, player, self.chunk_name(mode, lang, chunk) + ".json")

    def has_chunk(self, match: str, player: str, mode: str, lang: str, chunk: int) -> bool:
        return self.read_chunk(match, player, mode, lang, chunk) is not None

    def write_chunk(self, chunk: CommentaryChunk, traces: dict[str, Trace], where: str) -> None:
        d = self._dir(self.root(where), chunk.match, chunk.player)
        name = self.chunk_name(chunk.mode, chunk.lang, chunk.chunk)
        self._write(d / f"{name}.trace.json", {line.id: traces[line.id].model_dump(exclude_none=True) for line in chunk.lines})
        self._write(d / f"{name}.json", chunk.model_dump(mode="json"))  # the chunk last: its presence means the traces exist too

    def read_trace(self, line_id: str) -> dict | None:
        """The trace for a line id ``match.player.mode.lang.chunk.n``, or None."""
        parts = line_id.split(".")
        if len(parts) != 6 or not parts[4].isdigit():
            return None
        match, player, mode, lang, chunk, _ = parts
        if mode not in ("casual", "analyst") or lang not in ("en", "es"):  # parts of a file name: only known values
            return None
        try:
            traces = self._read(match, player, f"{self.chunk_name(mode, lang, int(chunk))}.trace.json")
        except ValueError:
            return None
        return traces.get(line_id) if isinstance(traces, dict) else None

    # -- recaps --------------------------------------------------------------------------------------------
    def read_recap(self, match: str, player: str, mode: str, lang: str) -> dict | None:
        return self._read(match, player, f"recap_{mode}_{lang}.json")

    def write_recap(self, match: str, player: str, mode: str, lang: str, recap: Recap, where: str) -> None:
        self._write(self._dir(self.root(where), match, player) / f"recap_{mode}_{lang}.json", recap.model_dump(mode="json"))

    # -- audio ---------------------------------------------------------------------------------------------
    def audio_path(self, audio_hash: str) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{32}", audio_hash):
            return None
        return next((d / f"{audio_hash}.mp3" for d in (self.audio_pre, self.audio_ondemand) if (d / f"{audio_hash}.mp3").is_file()), None)

    def sizes(self) -> dict[str, int]:
        """Bytes under the two committed folders (for the phase report)."""
        def size(root: Path) -> int:
            return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.is_dir() else 0
        return {"commentary": size(self.pre), "audio": size(self.audio_pre)}
