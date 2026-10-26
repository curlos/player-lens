# Spec: Roster Generator

Oct 25, 2026 · @Carlos Martinez

## Purpose and inputs

The roster generator builds the two squads once, writes them to `world.json`, and every match uses that same file, so players keep the same names, numbers and attributes across all three matches. Run it with a fixed world seed; same seed, same roster.

- Inputs: world seed, the two team definitions below, the position templates below.
- Output: `data/world.json`, validated two ways: against `contracts/world.schema.json` (shape only) and by loading it with `World.model_validate_json` (`load_world` in `sim/models.py`), which also runs the model-level roster checks the JSON schema cannot express (unique shirt numbers, one keeper per team, at most 2 hot-headed players, no duplicate names). Both must pass before the file is accepted, and the contract test runs both.
- Pure Python, no network, no LLM. All names are fictional and checked against a real-player blocklist.

## Teams, formations and positions

|  | Azure City (AZC, blue) | Redmond United (RDM, red) |
| --- | --- | --- |
| Role | Home side, title contenders | Away side |
| Formation | 4-3-3 | 4-4-2 |
| Team strength | average player level about 78 | average player level about 74 |
| Keeper colour | neon yellow | orange |

Each squad has 11 starters. No bench is simulated (no substitutions in this version).

Slot to shirt number (unique 1 to 11 per team):

- **4-3-3:** 1 GK, 2 RB, 3 LB, 4 CB, 5 CB, 6 DM, 8 CM, 10 AM, 7 RW, 9 ST, 11 LW.
- **4-4-2:** 1 GK, 2 RB, 3 LB, 4 CB, 5 CB, 6 CM, 8 CM, 7 RM, 11 LM, 9 ST, 10 ST.

Positions map to the formation slots used by Spec: Simulator Movement. The star is AZC #9 (ST).

## Attributes, star and OVR

Attributes are integers 25 to 99: Pace, Passing, Vision, Finishing, Dribbling, Defending, Positioning, Composure, Strength, Work rate, Stamina, Set pieces, plus Shot-stopping for keepers only. Each player also gets a `temperament` (calm, normal or hot-headed) and `gender` (always male for now).

**Generation:** for each attribute, draw from a normal distribution with mean = the position template mean + the team offset + the player's quality offset, standard deviation 6, clamp to 25 to 99, round.

**Quality offset (added in review):** each non-star player gets one offset drawn once from a normal distribution with mean 0 and standard deviation about 6 OVR points, then applied to all of their attributes. Without it every player lands within about 2 points of the team mean, so a 91 star would stand alone next to a squad of near-identical players. The target shape is a few players in the 80s, most in the mid-70s to low-80s and one or two weaker starters (both teams; Azure mean about 78, Redmond about 74, Redmond's best about 85). Non-stars are capped at OVR 89 so the star stays the standout. The spread is a guess from general knowledge of top squads, not researched data; keep it in one config value so it can be tuned.

| Position | High (mean 80) | Medium (mean 68) | Low (mean 50) |
| --- | --- | --- | --- |
| GK | Shot-stopping, Composure, Positioning | Passing, Strength | Pace, Dribbling, Finishing |
| CB | Defending, Strength, Positioning | Composure, Stamina, Passing | Dribbling, Finishing, Vision |
| RB / LB | Pace, Stamina, Work rate | Defending, Passing, Dribbling | Finishing, Vision |
| DM | Defending, Positioning, Work rate | Passing, Stamina, Strength | Finishing, Dribbling |
| CM | Passing, Vision, Stamina | Positioning, Work rate, Dribbling | Defending, Finishing |
| AM | Vision, Passing, Dribbling | Finishing, Composure, Set pieces | Defending, Strength |
| RW / LW / RM / LM | Pace, Dribbling, Passing | Finishing, Stamina, Vision | Defending, Strength |
| ST | Finishing, Composure, Positioning | Pace, Strength, Dribbling | Defending, Work rate |

Attributes not listed use mean 60. Team offset: chosen so each team's mean OVR hits its target (the template means alone give about 71, so expect roughly AZC +7 and RDM +3; the earlier +4 and 0 would land at about 75 and 71, outside the 2-point check). One designated set-piece taker per team gets Set pieces mean 85; for Azure that is the star (hand-set at 93), so only Redmond's taker is generated this way.

**Star:** AZC #9 (ST). The name is generated (see Names below); the attributes are set by hand, because the hero-seed search needs a fixed star: Finishing 94, Composure 92, Positioning 92, Pace 88, Dribbling 87, Strength 84, Vision 78, Passing 76, Work rate 80, Stamina 82, Defending 40, Set pieces 93 (he is Azure's penalty and free-kick taker, matching the approved penalty screen), temperament normal. OVR 91 (Set pieces is not in the striker's OVR formula).

**OVR** (shown as grey "OVR 91" on the card): weighted mean of the position's High, Medium and Low attributes with weights 3, 2, 1, rounded. For the star it is forced to 91.

**Derived values** (computed by the simulator, not stored): max speed = min(9, 7 + 2 x Pace / 99) m/s; acceleration = 2.5 + 2.0 x Pace / 99 m/s squared.

## Names, numbers and other fields

- **Nationality (added in review):** each player draws a nationality with the world seed from nine: England, Spain, Brazil, France, Germany, Portugal, Austria, Netherlands, Italy. Each team must have a good mix: at least 3 different nationalities and no more than 4 players of one nationality. Players need not all differ.
- **Names:** the first name is drawn from that nationality's first-name pool (about 10 of the most common male given names for births around 1995 to 2000, not recent baby-name lists); the surname from its surname pool (about 15 of the most common surnames). The UI shows initial plus surname (for example "J. Okafor"); `first_name` is stored too.
- **No shared names (owner rule, added in review):** no two players in the world share a surname, and no two players on a team share a first name, so commentary and the lineup never confuse two players. The generator redraws on any clash. Also redraw if a first name equals the surname (France has Thomas in both lists).
- **Name pools (researched Oct 25; "sourced" means seen in a web source, "memory" means added from general knowledge to reach the pool size; the owner verifies and edits before the generator is built):**

  | Nationality | First names | Surnames | Sourcing |
  | --- | --- | --- | --- |
  | England | Jack, Thomas, James, Joshua, Daniel, Matthew, Samuel, Joseph, Callum, William | Smith, Jones, Williams, Taylor, Brown, Davies, Wilson, Evans, Thomas, Johnson, Roberts, Walker, Wright, Robinson, Thompson | First names 1 to 5 sourced (England and Wales top 100, 1996 to 2000), 6 to 10 memory. Surnames 1 to 10 sourced (sources vary slightly in order), 11 to 15 memory |
  | Spain | Alejandro, Daniel, Pablo, David, Adrián, Álvaro, Javier, Sergio, Carlos, Jorge | García, Rodríguez, González, Fernández, López, Martínez, Sánchez, Pérez, Gómez, Martín, Jiménez, Ruiz, Hernández, Díaz, Moreno | First names 1 to 5 sourced (INE for people born from 2000; Guiainfantil for 2000), 6 to 10 memory. Surnames 1 to 10 sourced (INE), Jiménez named in a source, 12 to 15 memory |
  | Brazil | Lucas, José, João, Gabriel, Matheus, Pedro, Rafael, Guilherme, Felipe, Bruno | Silva, Santos, Oliveira, Souza, Pereira, Ferreira, Lima, Alves, Rodrigues, Costa, Gomes, Martins, Araújo, Ribeiro, Carvalho | First names: Lucas, José, João, Gabriel sourced (IBGE Census 2010 by decade), the rest memory. Surnames 1 to 10 sourced (IBGE Census 2022), 11 to 15 memory |
  | France | Thomas, Alexandre, Nicolas, Lucas, Théo, Julien, Kévin, Maxime, Quentin, Antoine | Martin, Bernard, Thomas, Petit, Robert, Richard, Durand, Dubois, Moreau, Laurent, Simon, Michel, Leroy, Lefebvre, Garcia | First names 1 to 9 sourced (third-party copies of the INSEE file, 1995 to 2000), Antoine memory. Surnames 1 to 8 sourced, 9 to 15 memory |
  | Germany | Alexander, Maximilian, Lukas, Jan, Leon, David, Paul, Daniel, Niklas, Felix | Müller, Schmidt, Schneider, Fischer, Weber, Meyer, Wagner, Becker, Schulz, Hoffmann, Schäfer, Koch, Bauer, Richter, Klein, Wolf, Schröder, Neumann, Schwarz, Zimmermann | First names sourced but sources disagree on order (Frankfurt 2000, familie.de, GfdS notes); no official table found. Surnames 1 to 20 sourced (one German list; order varies by source) |
  | Portugal | João, Pedro, Tiago, Diogo, André, José, Ricardo, Luís, Bruno, Miguel | Silva, Santos, Ferreira, Pereira, Costa, Oliveira, Rodrigues, Fernandes, Sousa, Martins, Gomes, Lopes, Marques, Alves, Almeida | First names sourced (1990s list from a names blog citing registry data). Surnames 1 to 10 sourced as a group (order inside it unclear), 11 to 15 memory |
  | Austria | Lukas, Michael, Florian, Daniel, Alexander, Thomas, Stefan, David, Sebastian, Philipp | Gruber, Huber, Bauer, Wagner, Müller, Pichler, Steiner, Moser, Mayer, Hofer, Leitner, Berger, Fuchs, Eder, Fischer | First names 1 to 7 sourced (Statistik Austria charts, 1995 to 2000), 8 to 10 memory. Surnames: weak (secondary pages only, no official ranking found) |
  | Netherlands | Thomas, Tim, Daan, Max, Niels, Lars, Rick, Nick, Tom, Kevin | De Jong, De Vries, Jansen, Van den Berg, Van Dijk, Bakker, Janssen, Visser, Smit, Meijer, Bos, Mulder, De Boer, Vos, Peters | First names sourced (Meertens table for 2000, hard to parse, order uncertain). Surnames 1 to 10 sourced (Meertens), 11 to 15 memory |
  | Italy | Andrea, Francesco, Alessandro, Matteo, Luca, Lorenzo, Marco, Davide, Simone, Giuseppe | Rossi, Russo, Ferrari, Esposito, Bianchi, Romano, Colombo, Bruno, Ricci, Marino, Costa, Gallo, Conti, Greco, Mancini | First names sourced (ISTAT 1999 via Fanpage). Surnames sourced (Money.it 2026 top 20; Villa, Franco, Martino, Giordano, Rizzo left out) |

  The same surname appears in several pools (Silva, Santos, Costa, Müller, Thomas and others), which the no-shared-surname rule handles automatically.
- **Star name:** generated the same way, but the surname must be short (one or two syllables) and easy to say aloud in English, since commentary says it often. It must not resemble a famous footballer or a fictional character.
- **Blocklist:** a file of real player full names and surnames; any generated name matching it is redrawn, and the common first name plus common surname combination must not equal a well-known real player. A reviewer should also scan the final 22 names by eye.
- **Temperament:** 25% calm, 60% normal, 15% hot-headed; the star is normal; at most 2 hot-headed players per team.
- **Fields per player:** `id` (`azc_09`), `team`, `name`, `first_name`, `nationality`, `number`, `position`, `slot`, `gender`, `temperament`, `attributes{}`, `ovr`.
- **Fields per team:** `id`, `name`, `abbr`, `formation`, `color`, `keeper_color`, `players[]`. Team tactics (`press_intensity`, `tempo`, `width`, `def_line`, `style`) are not stored here; they live in the simulator config (`TEAM_TACTICS` in Spec: Simulator Movement), because they are tuning knobs.
- The referee is not a player; he has no attributes and is added by the simulator.

## Output and validation

`data/world.json` holds `{seed, teams[2]}`. `meta.json` for each match copies the roster it needs, so the frontend never reads `world.json`.

Checks that must pass before the file is accepted:

- Exactly 11 players per team; shirt numbers 1 to 11 unique per team; exactly one GK per team.
- All attributes within 25 to 99; keepers have Shot-stopping, outfielders do not.
- Team mean OVR within 2 points of the targets (AZC about 78, RDM about 74).
- No name on the blocklist; no two players share a surname; no two players on a team share a first name.
- Each team has at least 3 nationalities and no more than 4 players of one nationality.
- The star's attributes match the hand-set values above; no non-star exceeds OVR 89; no other player has Set pieces above 92, so the star always has the highest Set pieces and takes Azure's penalties (the generator clamps Set pieces to 92 for everyone else).
- Each team has at least two players at OVR 80 or above (Azure) or at least one (Redmond), and a spread (standard deviation) of at least 4 OVR points.
- Same seed produces a byte-identical file.

## Open questions

- Whether the target OVR gap (78 vs 74) gives the right goal rates; calibration may adjust it.
- Decided: everyone except the star's attributes is generated, names included (no other hand-set players).
- Done: `sim/models.py` `Player` now has required `first_name` and `nationality` (a nine-value enum), and `contracts/world.schema.json` was regenerated with `scripts/export_schemas.py`.
- Whether a bench is needed later for substitutions (out of scope now).
