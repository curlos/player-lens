"""Spend tracking and caps (specs/agents-backend.md, "Caching, cap and fallback").

Every live LLM or Speech call is recorded as one line in ``<persist>/spend_ledger.jsonl`` (gitignored) with its
exact tokens or characters and dollars, so the running total is always known: there is no cost API to ask
and Azure's own cost page lags by hours. Two kinds of limit:

- the **live cap** (server): live generation for visitors stops once all-time spend (model + voice) reaches
  ``LIVE_CAP_USD``; a cap of 0 means no live generation at all. It is all-time, not daily: every generated
  chunk is cached for good, so total spend has a natural ceiling (every player, minute and variant once) and
  the cap is a safety net just above it, never a daily wall visitors hit;
- the **run limit** (offline scripts): ``--max-usd`` and ``--max-chars`` stop a pre-generation run, whatever
  the live cap says. A call is refused *before* it is made once the run has reached its limit.

The all-time totals are read from the ledger once and then kept in memory (the ledger may sit on a network
share, and one replica is the only writer in production).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.settings import Settings

log = logging.getLogger("player_lens.budget")


class BudgetExceeded(Exception):
    """A spend limit stopped a call. ``reason`` is the trace reason: always "cap"."""

    reason = "cap"


@dataclass
class Totals:
    usd: float = 0.0
    llm_usd: float = 0.0
    speech_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    chars: int = 0
    calls: int = 0


class Budget:
    def __init__(
        self,
        settings: Settings,
        ledger_path: Path | None = None,
        *,
        enforce_cap: bool = True,
        run_max_usd: float | None = None,
        run_max_chars: int | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.s = settings
        self.path = ledger_path or settings.persist / "spend_ledger.jsonl"
        self.enforce_cap = enforce_cap
        self.run_max_usd = run_max_usd
        self.run_max_chars = run_max_chars
        self.now = now
        self.run = Totals()
        self._lock = threading.Lock()
        self._warned: set[str] = set()
        self._all: Totals | None = None  # all-time totals, loaded from the ledger on first use

    # -- pricing ---------------------------------------------------------------------------------------
    def llm_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.s.llm_price_in + tokens_out * self.s.llm_price_out) / 1e6

    def speech_cost(self, chars: int) -> float:
        return chars * self.s.speech_price_per_1m / 1e6

    # -- ledger ------------------------------------------------------------------------------------------
    def _append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": self.now().isoformat(timespec="seconds"), **record}) + "\n")

    def _read(self) -> list[dict]:
        """Every ledger line that parses; a damaged line (say, a write cut short) is logged and skipped, never fatal."""
        if not self.path.is_file():
            return []
        rows = []
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("spend ledger line %d is not valid JSON; skipped", n)
        return rows

    def totals(self, today_only: bool = False) -> Totals:
        """Totals from the ledger: all time (cached after the first read), or only today (UTC)."""
        if not today_only and self._all is not None:
            return dataclasses.replace(self._all)
        out = Totals()
        today = self.now().date().isoformat()
        for r in self._read():
            if today_only and not r["ts"].startswith(today):
                continue
            out.calls += 1
            out.usd += r["usd"]
            if r["kind"] == "llm":
                out.llm_usd += r["usd"]
                out.tokens_in += r.get("tokens_in", 0)
                out.tokens_out += r.get("tokens_out", 0)
            else:
                out.speech_usd += r["usd"]
                out.chars += r.get("chars", 0)
        if not today_only:
            self._all = dataclasses.replace(out)
        return out

    # -- gates (called before a call) ----------------------------------------------------------------
    def check_llm(self) -> None:
        """Raises BudgetExceeded when a live LLM call is not allowed right now."""
        if self.run_max_usd is not None and self.run.usd >= self.run_max_usd:
            raise BudgetExceeded(f"run limit ${self.run_max_usd:.2f} reached")
        if self.enforce_cap:
            if not self.s.llm_live_allowed:
                raise BudgetExceeded("live generation is off (cap 0, or a price is missing)")
            spent = self.totals().usd
            if spent >= self.s.live_cap_usd:
                raise BudgetExceeded("live spend cap reached")
            if spent >= 0.8 * self.s.live_cap_usd and "cap80" not in self._warned:
                self._warned.add("cap80")
                log.warning("live spend is at 80%% of the cap")

    def check_speech(self, chars: int) -> None:
        if self.run_max_chars is not None and self.run.chars + chars > self.run_max_chars:
            raise BudgetExceeded(f"run limit {self.run_max_chars} characters reached")
        if self.run_max_usd is not None and self.run.usd >= self.run_max_usd:
            raise BudgetExceeded(f"run limit ${self.run_max_usd:.2f} reached")
        if self.enforce_cap and self.totals().usd + self.speech_cost(chars) > self.s.live_cap_usd:
            raise BudgetExceeded("live spend cap reached")

    # -- recording (called after a call) ---------------------------------------------------------------
    def record_llm(self, key: str, tokens_in: int, tokens_out: int) -> float:
        usd = self.llm_cost(tokens_in, tokens_out)
        with self._lock:
            self.run.calls += 1
            self.run.usd += usd
            self.run.llm_usd += usd
            self.run.tokens_in += tokens_in
            self.run.tokens_out += tokens_out
            self._append({"kind": "llm", "key": key, "tokens_in": tokens_in, "tokens_out": tokens_out, "usd": round(usd, 6)})
            self._add(usd, llm_usd=usd, tokens_in=tokens_in, tokens_out=tokens_out)
        return usd

    def record_speech(self, key: str, chars: int) -> float:
        usd = self.speech_cost(chars)
        with self._lock:
            self.run.calls += 1
            self.run.usd += usd
            self.run.speech_usd += usd
            self.run.chars += chars
            self._append({"kind": "speech", "key": key, "chars": chars, "usd": round(usd, 6)})
            self._add(usd, speech_usd=usd, chars=chars)
        return usd

    def _add(self, usd: float, **parts: float) -> None:
        """Keeps the cached all-time totals in step with the line just appended (rounded like the ledger)."""
        if self._all is None:
            return  # not loaded yet: the first totals() call reads the line from the file
        t = self._all
        t.calls += 1
        t.usd += round(usd, 6)
        for name, value in parts.items():
            setattr(t, name, getattr(t, name) + (round(value, 6) if name.endswith("usd") else value))
