"""Offline pre-generation of commentary text and audio for the hero match and default star (the owner's cost rule: only
``md38_title_decider`` for ``azc_09``; never other players or matches).

Writes plain files (committed to git, baked into the image): ``data/commentary/<match>/<player>/<mode>_<lang>_<chunk>.json``
(plus traces and recaps) and ``data/audio/<hash>.mp3``. Run from the repo root with the venv active:

    python scripts/pregenerate.py --chunks 38,88          # a small measured batch (all four variants), then STOP and read the cost
    python scripts/pregenerate.py --chunks 0-5 --variants casual:en
    python scripts/pregenerate.py --all --recaps          # the full run: only after the owner has seen the measured cost

Safety: every run has a hard limit (``--max-usd``, default 5; ``--max-chars``) and stops before a call that would pass it. A chunk
is stored only if the model really produced it (never a cap-stopped template chunk), and a chunk already stored is skipped, so a
stopped run resumes where it left off. Every call is recorded in the spend ledger (scripts/spend.py shows the total).
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.inputs import build_plan, load_match  # noqa: E402
from agents.llm import FoundryLLM  # noqa: E402
from agents.recap import build_recap  # noqa: E402
from agents.service import CommentaryService  # noqa: E402
from agents.speech import SpeechClient  # noqa: E402
from app.budget import Budget  # noqa: E402
from app.cache import Store  # noqa: E402
from app.settings import load_settings  # noqa: E402

ALLOWED = ("md38_title_decider", "azc_09")  # owner's rule: pre-generate only this match and player
ALL_VARIANTS = [("casual", "en"), ("analyst", "en"), ("casual", "es"), ("analyst", "es")]


def parse_chunks(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return sorted({c for c in out if 0 <= c <= 89})


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--match", default=ALLOWED[0])
    ap.add_argument("--player", default=ALLOWED[1])
    ap.add_argument("--chunks", help="e.g. 38,88 or 0-5")
    ap.add_argument("--all", action="store_true", help="all 90 chunks (the full run)")
    ap.add_argument("--variants", default="all", help="'all' or e.g. casual:en,analyst:es")
    ap.add_argument("--recaps", action="store_true", help="also write the four full-time recaps")
    ap.add_argument("--max-usd", type=float, default=5.0)
    ap.add_argument("--max-chars", type=int, default=250_000)
    ap.add_argument("--dry-run", action="store_true", help="show what would run, make no calls")
    args = ap.parse_args()

    if (args.match, args.player) != ALLOWED:
        sys.exit(f"Refusing: only {ALLOWED[0]} for {ALLOWED[1]} is ever pre-generated (cost rule).")
    if not args.all and not args.chunks:
        sys.exit("Say which chunks: --chunks 38,88 (a small batch) or --all (the full run).")
    chunks = list(range(90)) if args.all else parse_chunks(args.chunks)
    variants = ALL_VARIANTS if args.variants == "all" else [tuple(v.split(":")) for v in args.variants.split(",")]

    settings = load_settings()
    store = Store(settings.data_dir)
    todo = [c for c in chunks if not all(store.has_chunk(args.match, args.player, m, l, c) for m, l in variants)]
    plan = build_plan(settings.data_dir, args.match, args.player)
    print(f"{len(chunks)} chunks asked, {len(chunks) - len(todo)} already stored, {len(todo)} to generate x {len(variants)} variants; "
          f"{sum(len(plan.chunk_moments(c)) for c in todo)} moments")
    if args.dry_run or not todo:
        return
    if not settings.llm_configured:
        sys.exit("The model is not configured (see .env.example).")

    budget = Budget(settings, enforce_cap=False, run_max_usd=args.max_usd, run_max_chars=args.max_chars)
    speech = SpeechClient(settings, budget, store.audio_pre, [store.audio_pre]) if settings.speech_configured else None
    service = CommentaryService(settings, budget, store, llm=FoundryLLM(settings, budget), speech=speech)
    previous: list[str] = []
    done = 0
    for c in todo:
        before = (budget.run.usd, budget.run.tokens_in, budget.run.tokens_out, budget.run.chars)
        try:
            budget.check_llm()
        except Exception as err:
            print(f"STOP before chunk {c}: {err}")
            break
        result = await service.generate(args.match, args.player, c, variants, where="pre", previous_lines=previous, write=False)
        if not result.model_produced():
            print(f"STOP at chunk {c}: a spend limit or a failed model call; nothing stored for this chunk")
            break
        for key in variants:
            store.write_chunk(result.chunks[key], result.traces, "pre")
        previous = result.final_lines
        done += 1
        lines = [ln for ch in result.chunks.values() for ln in ch.lines]
        kinds = {k: sum(1 for ln in lines if ln.fact_check == k) for k in ("pass", "fixed", "template")}
        spent = (budget.run.usd - before[0], budget.run.tokens_in - before[1], budget.run.tokens_out - before[2], budget.run.chars - before[3])
        print(f"chunk {c:2d}: ${spent[0]:.4f}  {spent[1]} tokens in, {spent[2]} out, {spent[3]} speech chars  lines {kinds}")

    if args.recaps and done == len(todo):
        bundle = load_match(settings.data_dir, args.match)
        for mode, lang in variants:
            if store.read_recap(args.match, args.player, mode, lang):
                continue
            recap, complete = await build_recap(bundle, settings.data_dir, args.player, mode, lang, service.llm, speech, settings.voice(mode, lang))
            if not complete:
                print(f"recap {mode}_{lang}: the model or the voice failed (or a limit was hit); not stored")
                continue
            store.write_recap(args.match, args.player, mode, lang, recap, "pre")
            print(f"recap {mode}_{lang}: {len(recap.text.split())} words, audio {'yes' if recap.audio_url else 'no'}")

    run = budget.run
    print(f"\nthis run: ${run.usd:.4f} (model ${run.llm_usd:.4f}, speech ${run.speech_usd:.4f}), {run.tokens_in} tokens in, "
          f"{run.tokens_out} out, {run.chars} speech characters, {run.calls} calls")
    if done:
        print(f"average per chunk: ${run.usd / done:.4f}  ->  projected all 90 chunks: ${run.usd / done * 90:.2f} "
              f"({run.chars / done * 90:,.0f} speech characters)")
    print("stored sizes:", store.sizes())


if __name__ == "__main__":
    asyncio.run(main())
