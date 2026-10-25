# Gemini UI Prompts: Player Lens

Oct 24, 2026 · @Carlos Martinez

> Paste the base prompt first, attach your current mockup as the style reference, then send one screen prompt per image. Each screen prompt is self-contained below the base. The mockups are style and layout references only; PRODUCT and the specs win on any conflict.

## How to use

1. New Gemini chat. Attach the style-reference screenshot and paste the base prompt; it generates the base layout image. Later, attach the approved base image (below the base prompt) when you want the same look.
2. Ask for one screen at a time (paste its screen prompt). Attach the best earlier result when you want the same look.
3. Names and numbers below are placeholders. The real roster comes from the roster generator.

## Timeline used across screens

| Minute | Score (AZC-RDM) | Event |
| --- | --- | --- |
| 12' | 1-0 | Azure goal (not the star) |
| 34' | 1-1 | Redmond goal |
| 61' | 2-1 | Star goal #1 |
| 69' | 2-2 | Redmond goal |
| 71' | 2-2 | Yellow card, Redmond #4 |
| 78' | 2-2 | Red card, Redmond #5 (Redmond play with 10) |
| 84' | 3-2 | Star scores a penalty, goal #2 |
| 90+3' | 3-2 | Full time |

## Base prompt (paste first)

```text
You are a senior product designer. Create high-fidelity desktop web-app UI mockups (16:9, 1440x900) for "Player Lens", a live 2D synthetic football match viewer where the viewer follows ONE selected player. Use the attached screenshot only as a style reference (dark UI, a dark desaturated forest-green pitch (about #2E5A30, never bright, light or pastel green), lime-green accent, rounded cards, clean sans-serif like Inter). Do NOT copy its layout where it conflicts with the layout below.

Everything is fictional. League: "Atlas League". Clubs: "Azure City" (abbreviation AZC, blue kit) and "Redmond United" (abbreviation RDM, red kit). No real clubs, players, leagues or brand logos, and no Microsoft or Azure logos. Use the abbreviations AZC and RDM everywhere.

LAYOUT (identical in every image):
1. SCORE BAR, centered at the top of the pitch. One row, left to right: AZC on a blue segment, the score "2 - 1", RDM on a red segment, then the match clock (for example 74:04) in a light box at the right end. Abbreviations are large and bold. Nothing else in the bar: no league name, no matchday caption, no icons. A very small yellow or red card icon may appear under a team's abbreviation ONLY after that team has received a card (tiny number only if more than one). With no cards, show nothing. After a red card, add a tiny "10 men" label under that abbreviation.
2. PITCH, the main area, filling the window down to the bottom edge. Pitch color: dark desaturated forest green (about #2E5A30) with very subtle mowing stripes (slightly lighter and darker bands) and white lines at about 60% opacity. Top-down 2D, 105 x 68 proportions, correct markings (both goals, penalty areas, six-yard boxes, penalty spots, center circle, corner arcs). AZC attacks left to right. NOTHING sits on the pitch except the score bar, the playback bar, the dots, the ball, the referee and brief action visuals.
3. PLAYBACK BAR (video-player style, auto-hides). By DEFAULT it is HIDDEN: show nothing along the bottom of the pitch. Only when I write "controls visible" show it along the bottom of the pitch: pause/play button, a 1x | 2x | 4x | 6x | 8x | 10x speed selector, and a thin timeline with tiny markers for goals (ball icon) and cards. At its right end a small gear icon. The gear opens a small "View" popover with: Mute, Show ratings, Colorblind colors (switches ratings to blue-to-orange), Match info, Settings. Show the popover only in images where I ask for it.
4. RIGHT SIDEBAR, about 28% width, full height, two tabs: "Player" and "All ratings". The Player tab shows: silhouette avatar (default-user style, no photo), name, shirt number, position, overall rating shown as a small neutral grey label "OVR 91" (never colored), a large live rating pill (6.0 to 9.9, one decimal, colored by the RATING COLORS rule below), a small rating line chart starting at 6.0, a stat badges row always visible under the chart (a ball icon with the goal count and a boot icon with the assist count, shown even when 0), a RATING LOG (minute, signed delta, short reason) and a tall COMMENTARY panel with Casual/Analyst toggle, EN | ES toggle, a small speaker icon, the full commentary text (no cut-off text) and a small "How this was made" link under the latest line.
5. There is NO agent strip, pipeline row, "Behind the Scenes" label or bottom bar anywhere on screen. The window ends at the pitch and sidebar.

PITCH RULES:
- Exactly 11 dots per team, large (about 26 px) team-colored circles with the shirt number inside in bold white. Every dot has a thin white outline and a soft dark shadow so it stands out on the dark pitch. Use bright, saturated team colors (blue about #3B82F6, red about #E5484D). Numbers 1 to 11, unique within each team. The two goalkeepers (shirt #1, one on each goal line) must NOT use their team's color: the AZC keeper is a neon yellow dot (about #E6F23A), the RDM keeper is an orange dot (about #FF9F1C), both with a dark number and no text label, so they are instantly different from every outfield dot.
- The ball is a small solid white dot (about 12 px, roughly half the size of a player dot) with a thin dark outline. The referee is a SMALL solid black DIAMOND with a thin white outline (single color, no stripes) (about half the size of a player dot), no number, about 60% opacity normally and dimmed to the same 35% as the other dots whenever spotlight dimming is on, never drawn on top of a player.
- AZC plays 4-3-3, RDM plays 4-4-2. Believable positions with natural variation, not a perfect grid.
- The selected player is AZC #9 "R. Valdemar" (forward, overall 91). Always show a thin lime RING (an outline only, not a glow, and never print the word "ring" or any other label for it) around his dot, and exactly ONE thin fading lime trail behind him (a slim line, never a blob or a chain of big circles). Directly above his dot show a small name tag: a translucent dark rounded pill reading "R. Valdemar #9" (the "#9" in lime) with a tiny downward notch pointing at the dot, drawn underneath all dots so it never covers a player. No tags on other players. In spotlight mode ALL other dots are dimmed to about 35%. Otherwise nothing is dimmed. Never dim only some dots: it is every other dot plus the referee, or none.
- RATING COLORS (pill, All ratings dots), default red-to-green: below 5.0 red, 5.0 to 5.9 orange, 6.0 to 6.9 yellow, 7.0 to 7.9 light green, 8.0 and above strong green, the number always visible. A colorblind option (blue-to-orange) exists as a setting in the View popover; do not use it unless I ask. Lime green is reserved for the selected-player ring, trail and accent, so keep the rating green clearly different from the lime. Rating log deltas: positive in green, negative in red, always with a + or - sign.
- Brief fading action visuals only when relevant: pass line, shot line with speed (for example "112 km/h"), tackle flash, pressure pulse, rating pop above a dot.
- Keep names, numbers, colors and layout identical across all images. Everything stays legible at 1440x900.

FIRST IMAGE, generate it now as an actual image: the base layout in live play at 74:04, score AZC 2 - 1 RDM, normal view (no dimming), playback bar hidden, selected player #9 with the thin lime ring and one thin trail, rating pill 8.2, rating log with a few rows, commentary text and the "How this was made" link. Afterwards I will ask for specific screens one at a time.
```

**Approved image (base layout):**

&#91;image: Approved base layout\]

## 1. Pre-match: Start match overlay

```text
Screen 1: the start of the game. Clock 00:00, score 0-0. Players stand in kickoff formation (AZC 4-3-3, RDM 4-4-2), the ball on the center spot, the referee diamond nearby. A dark translucent overlay covers the pitch with ONE centered dark rounded card (about 85% opaque, no logos or crests). At the top of the card a headline "Follow one player. Hear their story." and three short lines, each with a small outline icon: "Broadcasts follow the ball. Here the commentary follows one player." / "A personal commentator talks only about them, on and off the ball." / "A live rating shows how they are doing, and why." Then a thin divider and below it the title "Atlas League title decider - Matchday 38 of 38", two club lines "Azure City (1st) vs Redmond United (2nd)" with a tiny two-row standings snippet (AZC 86 pts, RDM 85 pts), a large lime button "Start match" and a small note "Click to start the match and enable commentary audio". The right sidebar already shows the selected star: silhouette avatar, "R. Valdemar", #9, ST, overall 91, match rating 6.0 with an empty rating chart, empty rating log, and the commentary panel saying "Waiting for kickoff". The playback bar at the bottom of the pitch is visible but disabled. The score bar shows AZC 0 - 0 RDM and 00:00.
```

**Approved image (screen 1):**

&#91;image: Approved screen 1\]

## 2. Live play, default view

```plain
Screen 2: live play at 34:20, score AZC 1 - 0 RDM. Normal view (no spotlight dimming), selected player AZC #9 R. Valdemar with a lime ring and one fading trail. A progressive pass line from AZC #8 to #9 is fading. Right sidebar: rating 7.2, line chart rising from 6.0 with small steps, stat badges empty, rating log (newest first): "34' +0.10 Progressive pass received under pressure", "31' +0.05 Held shape, good positioning", "24' -0.08 Dispossessed". Commentary in Casual mode, English, short lines like "Valdemar drifts into the pocket and Azure find him, nice pass through the middle." with the speaker icon active. The playback bar is hidden. A small "How this was made" link sits under the latest commentary line (collapsed).
```

**Approved image (screen 2):**

&#91;image: Approved screen 2\]

## 3. Goal moment

```text
Screen 3: the moment of the goal at 61:10, score AZC 2 - 1 RDM, scored by the selected player #9 R. Valdemar. Show the shot line from the edge of the box into the net with a speed pop "112 km/h" and the ball in the goal. A large "GOAL - R. Valdemar 61'" banner slides in just below the score bar; the score bar flashes. A gold rating pop "+0.87" floats above his dot. Sidebar: rating 7.4 to 8.3 (the chart jumps up), rating log new top row "61' +0.87 Goal (soft cap applied)", one ball icon in the stat badges. Commentary is excited: two short lines with a larger font for the first ("GOAL! Valdemar buries it!"). A small sound-wave indicator next to the gear icon shows crowd noise. Other players frozen, spotlight dimming on (all other dots dimmed).
```

**Approved image (screen 3):**

&#91;image: Approved screen 3\]

## 4. Celebration

```text
Screen 4: the celebration right after the goal, 61:25. The scorer #9 R. Valdemar is running toward the corner flag with arms spread, a small jump motion mark; the assister AZC #8 is already next to him and four more AZC players (#11, #7, #10, #6) are sprinting toward him in a converging cluster. RDM players stand still, a couple with hands-on-head indicators, the RDM goalkeeper in his goal. The referee diamond is near the center circle. A subtle "Celebrating" label under the scorer. Sidebar: rating 8.3, rating log still shows the goal row, commentary shows two warm lines ("That is his second-half special..."), the speaker icon active. The playback bar is hidden.
```

**Approved image (screen 4):**

&#91;image: Approved screen 4\]

## 5. All ratings tab

```text
Screen 5: the right sidebar is on the "All ratings" tab and is slightly wider. It shows ONE single continuous tall vertical pitch (one set of markings: one goal and penalty area at the top, one at the bottom, one center circle and halfway line in the middle; never two stacked pitches), like a match-lineup view in a sports app, with BOTH teams in their real formations: a header bar at the top "Azure City 4-3-3" with the AZC goalkeeper (neon yellow dot #1) at the top goal and the AZC players in rows below him (back four, midfield three, front three, attacking downward), and a header bar at the bottom "Redmond United 4-4-2" with the RDM goalkeeper (orange dot #1) at the bottom goal and the RDM players in rows above him (back four, midfield four, front two, attacking upward). Both goalkeepers must be visible. The halfway line is a thin white line at 50% opacity, never lime or colored. Every rating pill is colored by the current match rating on a red-to-green scale (red below 5.0, orange, yellow, light green, strong green from 8.0) (numbers always visible). Each player is a numbered dot in the team color (blue AZC, red RDM) with a thin white outline, a small rating pill overlapping the bottom edge of the dot, and no names anywhere (names appear only on hover in the real app) (for example 8.3, 7.1, 6.4, 5.8). The selected star #9 is outlined in lime. Above the lineup pitch, a small toggle "Pitch | List" with Pitch selected. No list is shown in this image. The main pitch on the left still plays (clock 66:40, score 2-1), normal view.
```

**Approved image (screen 5):**

&#91;image: Approved screen 5 (layout reference; the lineup panel is smaller than it should be, it fills the sidebar in the real app)\]

**Lineup panel reference (standalone):**

&#91;image: Lineup panel reference\]

## 6. Show ratings ON and agent trace expanded

```text
Screen 6: two features at once. (a) with the playback bar visible, "Show ratings" has been turned ON in the View popover (shown open above the gear icon at the bottom right): every one of the 22 dots has a small rating pill above it (for example 6.8, 7.4, 5.9) without cluttering the pitch. (b) The "How this was made" link under the latest commentary line is expanded into a compact trace inside the commentary panel (the panel grows taller), showing that one commentary line passing through the agents as a short vertical handoff chain: Interpreter (done, 12 ms), Moments (done, "key moment: goal"), Commentator (done), Fact Guard with a small amber badge "1 fix" and a tiny before/after diff ("third goal" changed to "second goal"), Personalizer (Casual, EN), Voice (clip 4.2 s ready). Keep the pitch fully visible, clock 62:10, score 2-1.
```

&#91;image: Screen 6 approved: Show ratings on, View popover, agent trace\]

## 7. Yellow card and players crowding the referee

```text
Screen 7: 71:15, score AZC 2 - 2 RDM. A foul just happened. The selected star #9 R. Valdemar is lying on the ground (a small "down" marker). RDM #4 stands next to him; the referee diamond has moved next to them and a yellow card icon pops up beside the referee and RDM #4. Two other RDM players (#9 and #7) are walking toward the referee, arguing (small speech marks). The score bar now shows a very small yellow card icon under the RDM abbreviation (nothing under AZC). Sidebar: rating 7.4, rating log top row "71' +0.05 Foul won". Commentary (Casual): a calm line about the foul and the booking. A small caption near the card icon: "Yellow card - RDM #4".
```

&#91;image: Screen 7 approved: yellow card\]

## 8. Red card, playing with 10, and 2x speed

```text
Screen 8: 78:30, score 2 - 2. Redmond #5 has just been sent off: a red card icon pops next to the referee and #5, who walks toward the touchline. Redmond now have 10 players in a 4-4-1 shape. The score bar shows very small yellow and red card icons and a tiny "10 men" label under the RDM abbreviation. Controls visible: the playback bar shows "2x" active. Because 2x is active, the commentary panel shows a muted state: "Commentary pauses at 2x speed" with a greyed speaker icon, while the pitch, rating chart and rating log keep updating. The crowd icon still shows sound waves. Sidebar rating 7.6.
```

&#91;image: Screen 8 approved: red card, 10 men, 2x\]

## 9. Penalty kick

```text
Screen 9: 84:00, score 2 - 2. Azure City have a penalty. The selected player #9 R. Valdemar stands at the penalty spot with the ball; the RDM goalkeeper (orange) stands on the goal line. All other 20 field players stand outside the penalty area in a loose line (small ones, dimmed), the referee diamond at the edge of the box. A large "PENALTY" banner at the top. A small chip "xG 0.78" near the spot. Sidebar for the taker: rating 7.9, a small "Set pieces 93" stat line, commentary building tension (short calm line), the spoken-commentary icon active. Spotlight dimming on, no trail.
```

&#91;image: Screen 9 approved as style reference only: penalty. Real rule: only the taker and the keeper are inside the box.\]

## 10. Full time

```text
Screen 10: full time at 90+3, score AZC 3 - 2 RDM. The pitch is dimmed and a centered "Full time" card appears: "Azure City 3 - 2 Redmond United - Atlas League champions". Beneath it the selected player's recap: "R. Valdemar - match rating 9.1 - 2 goals" (two ball icons), a small bar chart of the top 3 rating moments (Penalty goal +0.58, Goal +0.87, Pressure regain +0.12) and a "Replay match" button plus "Pick another player". The right sidebar keeps the rating chart (final 9.1, with a gentle soft-cap curve near the top) and the rating log.
```

&#91;image: Screen 10 approved: full time\]

## 11. Analyst mode in Spanish (variant of screen 2)

```text
Screen 11: the same layout as screen 2 at 34:20, but the commentary toggle is set to Analyst and the language toggle to ES. Commentary text is Spanish and more data-driven (for example "Valdemar recibe entre lineas con presion; 3 de 4 pases progresivos, xG acumulado 0.41."). The rating log reasons are also in Spanish. Show a small "xG" and "distance 7.8 km" stat line in the player card. Everything else identical.
```

&#91;image: Screen 11 approved: Analyst mode + Spanish (only commentary and log reasons localized; UI labels stay English)\]
