# Kickoff prompt for Claude Code

Paste the block below into Claude Code from the repo root.

---

You are building **Player Lens** for a hackathon. Deadline: submit by Tue Oct 27, 2026, 6:00 PM ET.

1. Read in order: `CLAUDE.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `TASKS.md`, then the spec for each piece just before you build it (`specs/`). `docs/` has decisions and research; `docs/ui/` has approved mockups (style references only, specs win).
2. If code and docs disagree, stop and ask. Don't guess on open decisions.
3. Work in plan mode per task: propose a short plan, wait for approval, then implement. One piece at a time.
4. Build order: (a) roster generator and `world.json` (models are in `sim/models.py`), (b) simulator, (c) rating engine, (d) match files and validation, (e) frontend, (f) agent pipeline and backend, (g) deploy.
5. Write tests alongside each piece (simulator invariants, determinism, rating sum, match-file validation, Fact Guard validator, backend endpoints with a mocked LLM). No live LLM calls in tests. Run them after every change.
6. Keys only in environment variables (`.env.example` lists them). Never commit or print a key.
7. Keep commits and PRs small with clear descriptions; CodeRabbit reviews the repo.
8. Fictional world only: no real players, clubs, logos, Microsoft/Azure logos, or copyrighted music.
9. Communication: short, answer first, bullets for lists, explain Docker/Azure/agent steps briefly.

Start by reading the docs, then propose the plan for step (a).
