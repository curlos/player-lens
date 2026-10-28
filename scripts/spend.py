"""Prints what the live Azure calls have cost so far, from the spend ledger (spend_ledger.jsonl in PERSIST_DIR, default data/).

Run from the repo root:  python scripts/spend.py
There is no cost API to ask and Azure's own Cost analysis page lags by hours, so this ledger (one line per live
LLM or Speech call, with exact tokens or characters) is the running total. Cross-check Cost analysis the next day.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.budget import Budget  # noqa: E402
from app.settings import load_settings  # noqa: E402


def main() -> None:
    budget = Budget(load_settings())
    total, today = budget.totals(), budget.totals(today_only=True)
    print(f"ledger: {budget.path}")
    for label, t in (("all time", total), ("today (UTC)", today)):
        print(f"{label:12} ${t.usd:.4f}  (model ${t.llm_usd:.4f}, speech ${t.speech_usd:.4f})  "
              f"{t.calls} calls, {t.tokens_in} tokens in, {t.tokens_out} out, {t.chars} speech characters")


if __name__ == "__main__":
    main()
