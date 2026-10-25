# Submission Plan: Player Lens

Oct 25, 2026 · @Carlos Martinez

## What must be submitted

From the Official Rules (section 4.4). Official cutoff is Oct 27, 11:59 pm PT (Oct 28, 2:59 am ET); personal target is Tue Oct 27, 6:00 pm ET.

| Item | Requirement |
| --- | --- |
| Project | Newly built, uses synthetic football data |
| Pitch or description | Short elevator pitch: what you built, which Microsoft and Azure technologies, what it does, what problem it solves |
| Demo video | Under 2 minutes; shows the project working on its real platform; public URL on YouTube, Vimeo, Facebook Video or Youku; no third-party trademarks or copyrighted music |
| GitHub repo | Public URL |
| Working project access | Live link (free, no restrictions) until the judging period ends Nov 10, with testing instructions |
| Language | All materials in English |

Submitted on the Projects page of the Hackathon Website. Category target: Best Multi-Agent System; judges look for distinct roles, shared state and handoffs, failure recovery, and an end-to-end result a single agent could not match.

## README outline

The README is where judges check code quality and the Microsoft stack, so keep it short and scannable.

1. **Title and one-liner:** "Player Lens: follow one player through a live synthetic match, with a personal AI commentator that explains every rating change."
2. **Live demo link and video link** at the top.
3. **What it does:** 4 bullets (follow one player, off-ball credit, self-explaining rating, Casual/Analyst and English/Spanish).
4. **Architecture diagram:** simulator, rating engine, agent pipeline, backend, frontend, Azure.
5. **Multi-agent design:** table of the six agents with their roles and handoffs; mention schema validation, Fact Guard recovery and the "How this was made" trace.
6. **Microsoft and Azure used:** Microsoft Foundry model, Microsoft Agent Framework, Azure AI Speech, Azure Container Apps (add GitHub Copilot only if actually used).
7. **Synthetic data:** all players and matches are fictional; the simulator is seeded and deterministic.
8. **Run it locally:** 5 commands, `.env.example`, what works with no keys.
9. **Deploy:** link to Spec: Deployment and Environment content.
10. **Cost controls:** pre-generated hero match, daily cap, template fallback.
11. **Real-world fit:** broadcast overlay feed, recap, personalization by language and mode.
12. **Limitations and next steps:** honest, short.
13. **License and credits:** audio sources and their licenses.

## Demo video script (target 1:45)

Record the live site, screen only, with a voiceover. No music (or only music you made or that is licensed for this use). No third-party logos. Judges stop at 2:00, so the strongest moment must come before 1:00.

| Time | On screen | Voiceover |
| --- | --- | --- |
| 0:00 to 0:10 | Start overlay, click Start match | Football is watched through the ball. Player Lens lets you follow one player, all match long. |
| 0:10 to 0:30 | Live play, star selected, commentary and rating line moving | A personal AI commentator follows him. Every rating change is explained, including off-ball work that stats ignore. |
| 0:30 to 0:50 | Goal: shot line, banner, rating pop, crowd | A goal, a rating jump, and the log tells you exactly why. |
| 0:50 to 1:10 | Click a line's How this was made | Six agents built this line: Interpreter, Moments, Commentator, Fact Guard, Personalizer, Voice. Here Fact Guard caught an unsupported claim and fixed it. |
| 1:10 to 1:25 | Switch to Analyst and Spanish | The same moment, as an analyst, in Spanish. |
| 1:25 to 1:38 | All ratings tab, Show ratings | Every player's rating, live, with reasons. |
| 1:38 to 1:48 | Full-time card | Built on Microsoft Foundry, Agent Framework, Azure Speech and Container Apps. All data is synthetic. |

Recording rules:

- Record against the live URL at 1x speed, with the hero match and default star, so everything shown is pre-generated and reliable.
- Pick the clip window first (a goal around the 30-minute mark works well), then seek straight to it; do not wait through real time.
- Write the voiceover first, read it aloud against a timer, and trim words rather than speeding up.
- The Fact Guard fix shown in the trace must be a real one from the pre-generated hero data; find one before recording.
- Upload to YouTube as public or unlisted-with-link, and test the link logged out.

## Pitch and judging criteria

**Elevator pitch (paste into the form, about 90 words):**

Player Lens turns a synthetic football match into a personal story. Pick any player and follow him through a live 2D match while a six-agent pipeline on Microsoft Agent Framework and a Foundry-hosted model narrates his game. A deterministic rating engine credits off-ball work that normal stats miss, and every rating change explains itself in a log. Fact Guard checks every line against the event log, a Personalizer switches Casual or Analyst and English or Spanish, and Azure AI Speech voices it. It runs on Azure Container Apps. All data is synthetic.

**Criteria mapping (each is 20%):**

| Criterion | Our answer | Show it in |
| --- | --- | --- |
| Technological implementation | Seeded simulator and rating engine, Pydantic contracts, Foundry, Agent Framework, Speech, Container Apps | README architecture, repo structure |
| Agentic design | Six agents with distinct roles, schema-validated handoffs, Fact Guard recovery, visible trace | Video 0:50 to 1:10, README table |
| Real-world impact | Overlay feed with timestamps, automated recap, Casual/Analyst and EN/ES personalization for broadcasters and fans | README, pitch |
| User experience | Single-screen player view, rating pills, clear screens | Video throughout |
| Category adherence | Best Multi-Agent System: distinct roles, shared state, recovery, an outcome one agent cannot match as well | README multi-agent section |

Honesty rule: claim only what runs in the live build. If a feature is cut, remove it from the pitch, README and video the same day.

## Schedule and final checklist

Working backward from Tue Oct 27, 6:00 pm ET. Dates assume Claude Code builds in the order: simulator, rating engine, match files, frontend, agents, deploy.

| When (ET) | Goal |
| --- | --- |
| Sun Oct 25 | Docs reviewed; repo synced; Claude Code kickoff; Azure account and Foundry model set up in parallel |
| Mon Oct 26 morning | Simulator and rating engine producing valid match files; hero seed chosen |
| Mon Oct 26 afternoon | Frontend playing the hero match |
| Mon Oct 26 night | Agents running; hero match and default star commentary pre-generated |
| Tue Oct 27 morning | Deploy to Azure; fix bugs; cut anything unfinished from the docs |
| Tue Oct 27 noon | Record and upload video; finish README |
| Tue Oct 27 3:00 pm | Fill in the Projects page form, double-check every link |
| Tue Oct 27 6:00 pm | Submit (about 9 hours of buffer before the official cutoff) |

If behind schedule, cut in this order: extra matches (the library is three matches; a 0-0 fourth is optional and only built if time allows), league table, Spanish, recaps, Analyst mode (same order as CLAUDE.md and TASKS.md). Never cut the rating reason log or the "How this was made" trace.

**Final checklist**

- [ ] Live URL plays the hero match end to end from a fresh browser and a phone
- [ ] Public GitHub repo: README, `.env.example`, no keys (search the history too)
- [ ] Video under 2:00, public, link works logged out, no copyrighted music or logos
- [ ] Pitch text pasted; README, pitch and video describe only what runs
- [ ] Testing instructions written (what to click, what to expect)
- [ ] Budget alert active; daily caps set
- [ ] Live link stays up through Nov 10
- [ ] Submission form saved and confirmation received
