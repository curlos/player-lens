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
10. **Cost controls:** pre-generated hero match, persistent cache, all-time cap, template fallback.
11. **Real-world fit:** broadcast overlay feed, recap, personalization by language and mode.
12. **Limitations and next steps:** honest, short.
13. **License and credits:** audio sources and their licenses.

## Demo video script (target 1:50; the best moment lands before 0:45)

Revised Oct 28 from the real hero data. Follow Lima (#9 Azure City) the whole way, plus one 10-second click on another player to prove commentary is generated live for anyone, not pre-recorded. No voiceover: the product's own commentator voice and crowd carry the audio, and short on-screen captions (white text, bottom third, 2 to 6 words) say what the judge is seeing. That avoids talking over the commentator and keeps the video in English (captions) with the Spanish moment self-explained.

| Time | On screen (seek to) | What you hear | Caption |
| --- | --- | --- | --- |
| 0:00 to 0:06 | Start overlay, click **Start match** | crowd | "Follow one player. Not the ball." |
| 0:06 to 0:26 | Seek **9:35**, Lima selected, 1x. Lima loses the ball to Zimmermann (9:41, rating 6.2), then counterpresses (9:50, rating 6.5). Rating log rows appear, pills pop. | "Lima loses ball to Zimmermann, rating falls to 6.2." / "Lima counters fiercely after losing ball, rating rises to 6.5!" | "A rating that explains itself" then "Off-ball work counts" |
| 0:26 to 0:44 | Seek **38:38**. Lima's equaliser at 38:47: shot line, GOAL banner, crowd roar, rating pop to 8.2. | "Goal! Lima equalises for Azure City! Rating hits 8.2!" | "A personal AI commentator" |
| 0:44 to 1:08 | Seek **5:52**, pause right after the 5:58 line ("Weber passes in midfield to Moreno..."). Click **How this was made**: six agent steps, the amber Fact Guard badge, before/after. | silence or crowd | "6 agents on Microsoft Agent Framework" then "The model said 'Lima tracks back'. The event log says he didn't." then "Fact Guard caught it." |
| 1:08 to 1:24 | Seek **88:30**: aerial duel, then Lima's 89' title winner (88:38) in Casual English. Then seek back to 88:30, switch to **Analyst + Español**, replay the goal. | "Goal! Lima scores for Azure City, 3-2 now! Rating 8.9!" then "¡Golazo de Lima para Azure City, 3-2 y rating 8.9!" | "Casual or Analyst. English or Spanish." |
| 1:24 to 1:36 | Click a player Lima's not (for example #6 Weber, Redmond) at a minute nobody has watched: "Preparing commentary", then his AI lines and voice. Then the **All ratings** tab. | his commentary | "Any of 22 players: written live, then cached" |
| 1:36 to 1:50 | Full-time card with Lima's recap, click **Listen**. End card: live URL + stack. | recap voice | "Microsoft Foundry · Agent Framework · Azure AI Speech · Container Apps" and the URL |

Before recording:

- **Capture the app's sound.** macOS's built-in screen recorder (Cmd+Shift+5, QuickTime) records no system audio. Use OBS (free; a "macOS Screen Capture" source records the browser's audio on macOS 13+) or another recorder that captures app audio, and test 10 seconds first.
- Record against the live URL in Chrome at 1x, full-screen pitch off (the sidebar must show the rating log and commentary), browser zoom so the text is readable at 1080p. Hide bookmarks and other tabs.
- Warm the cache: play each moment once before the real take, so every clip is already loaded and nothing says "Preparing". For the 1:24 segment, do the opposite: pick a player and minute nobody has watched, so the live generation shows (it takes a few seconds; cut the wait in the edit).
- Record each segment as its own short take (seek, play, stop), then cut them together; no take needs real-time waiting.
- Captions: any editor (iMovie titles, CapCut). Keep each on screen at least 2 seconds.
- No music; no logos other than what the app shows (it shows none).
- Upload to YouTube as **Public** or **Unlisted**, and open the link logged out to check it plays.

Why this order: judges score technology, agentic design, real-world impact, UX and the category (Best Multi-Agent System), each 20%, and may stop early. The first 45 seconds show the unique idea (off-ball credit and a self-explaining rating) and the voice; the agent trace with a real Fact Guard catch is the multi-agent proof; Spanish/Analyst and "any player, live" show personalization and that it is a working product, not a recording.

## Pitch and judging criteria

**Elevator pitch (paste into the form, about 100 words):**

Player Lens turns a football match into one player's story. Pick any of 22 players in a live 2D match and a personal AI commentator follows him, while a deterministic rating engine credits the off-ball work normal stats miss (counterpresses, recovery runs, decoy runs) and every rating change explains itself in a log. Six agents on Microsoft Agent Framework with a Foundry-hosted GPT-4.1 mini write the words; code computes every number, and Fact Guard checks each line against the event log before Azure AI Speech voices it in English or Spanish, Casual or Analyst. It runs on Azure Container Apps. All data is synthetic.

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
- [ ] Budget alert active; `LIVE_CAP_USD` set; cache share mounted
- [ ] Live link stays up through Nov 10
- [ ] Submission form saved and confirmation received
