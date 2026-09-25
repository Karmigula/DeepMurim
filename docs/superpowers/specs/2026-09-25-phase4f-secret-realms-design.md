# DeepMurim Phase 4f: Secret Realms

**Status:** design approved in brainstorming (2026-09-25). Builds on 4d (world events, treasures, races), 4e (tournaments, sponsors, level of detail) and the entity cache on master at 31055cc.

## 1. Goal

Secret realms: sealed pocket worlds that open for a few days, where the young generation fights over an ancient master's legacy.

- A realm is a **lasting place** with floors and chambers. Its layout is seeded once, and each opening leaves its scars.
- The player **delves** it one step at a time, then leaves before the gate closes, or is sealed in until it reopens years later.
- Rival delvers from the sects are inside too, and inside there are no rules.
- What happens inside reaches the world only through survivors.

### Decisions (from brainstorming)

| Question | Decision |
|---|---|
| How it plays | A delve through floors and chambers, one step at a time; press deeper or leave before the gate closes. |
| When the gate closes | Anyone inside is sealed in until the next opening; the player may cultivate through the years, search for a hidden exit, or hand play to their heir. |
| Who may enter | Each realm has its own rule: a realm ceiling, jade tokens, open to all, or sect quotas. |
| What the chambers hold | Rival delvers, guardians and trials, treasures (better with depth), and an inheritance on the deepest floor. |
| Where realms come from | Three ancient realms seeded in every world, reopening on their own cycles; newborn realms cracked open by treasure lights. |
| Approach | A realm is a place: a lasting `secret_realm` entity people are `located_in`; each opening is a 4d world-event occurrence; chamber state is compact data on the realm. |

## 2. Architecture

### 2.1 New modules
- `systems/secret_realms.py`: realm entities, seeded layouts, entry rules, the delve, rival delvers, sealing, and summaries of openings far away. (`systems/realms.py` already means cultivation realms.)
- `systems/events/realm_opening.py`: the 4d event type for an opening (hooks: `places`, `start_data`, `on_stage`, `on_observe`).
- `engine/delve.py`: `DelveMixin`. While the player is inside a realm, the delve menu replaces the town scene, the way combat does.
- `engine/realm_page.py`: the realms page.
- `narrate/realm_text.py`, `narrate/grammar/realm.toml`: arrival lines, chamber words, outcomes, journal lines, rumour phrases.

### 2.2 The realm entity
- **Kind:** `secret_realm`, placed at a gate town (`gate`), with a seeded name ("The Sunken Palace of the Azure Sage").
- **The master:** a name, their art (a 2b technique generated at seeding, high grade), and their weapon (an item description).
- **Entry rule:** `{"kind": "ceiling" | "token" | "open" | "quota", "value": ...}`, fixed at seeding.
- **Period:** it reopens every N seasons (12–40 for ancient realms). `next_opening` is the season of the next opening; `null` for a spent one-off.
- **Floors:** 3–6 floors, each with 2–4 chambers. A chamber is `{"kind", "state", "contents"}`, where `kind` is `treasure`, `guardian`, `trial`, `rivals`, `stair` or `inheritance`, and `state` is `untouched`, `looted`, `slain` or `passed`.
  - Every floor but the last has one `stair`.
  - The last floor has the `inheritance`.
  - `rivals` chambers are filled at each opening by the teams inside.
- **History:** one line per opening: `{"season", "entered", "died", "sealed", "took", "inherited"}`.
- **`inheritance_claimed_by`:** set once, ever.
- **`sealed`:** the people sealed in now.

### 2.3 Being inside
- The player and the rival delvers placed inside are `located_in` the realm entity. Talking, duels, robbing, memories and the knowledge rule work unchanged.
- **The player's position** is player data: `delve = {"realm", "floor", "chamber"}`.
- **A rival team** is data on the opening's occurrence: `{"faction", "members", "floor", "chamber"}`.

### 2.4 Openings
- Each opening is a world-event occurrence of type `realm_opening`, in the town of the gate.
- Its stages are `foretold` (30 days), `announced` (10), `active` (the gate is open: 6–12 days, seeded per realm) and `aftermath` (20).
- **Scheduling:** the type uses `every = 1`. Its `places` hook returns the gates of realms whose `next_opening` is this season, so each realm keeps its own period.
- **News:** the heralds' `phenomenon` news at `foretold` and `announced`, as in 4d. A newborn realm is not heralded.

### 2.5 Level of detail
- **When the gate opens** (`active`), the delvers are chosen by the realm's rule (§4.2) and stored on the occurrence. Nobody moves.
- **If the player never enters,** the opening is summarised when the gate closes, in one `realm_closed` event (§4.5).
- **If the player enters,** the chosen delvers are placed inside at that moment, and play out chamber by chamber around them (§4.3).

## 3. The delve (the player's side)

### 3.1 Moving
- **Time:**
  - clearing or passing a chamber takes 2 watches;
  - a stair takes 1;
  - resting takes a watch.
- **The header** always shows the realm, the floor and chamber, and the gate countdown: "The Sunken Palace, floor 2 of 4, the Hall of Mirrors (the gate closes in 3 days)."
- **Moving between chambers:** the player moves on to the next chamber of a floor once the current one is looted, slain or passed. They can also turn back to one already visited.
- **Leaving:** only from floor 1, so going deep means walking back up in time.

### 3.2 Chambers
- **Treasure:** take it.
  - It is a 4d `treasure` item: a pill, a herb, a manual (grade and completeness grow with depth) or star iron.
  - Values scale ×(1 + 0.5 × floor).
  - Once taken it is gone. Each opening restocks each looted treasure chamber with chance 0.3.
- **Guardian:** a beast or a bronze puppet, at realm (the floor + 1), capped at Peak.
  - Fight it: a duel in mode `duel`, where the guardian never spares.
  - Or slip past: a chance of 0.3 + 0.03 × (agility − 10) − 0.1 × (guardian realm − your realm), clamped to 0.05–0.8. Failing starts the fight.
  - A slain guardian stays slain until the next opening.
- **Trial**, one of three, seeded per chamber:
  - **Formation:** passing chance 0.2 + 0.04 × comprehension, clamped to 0.1–0.9, seeded per attempt. Passing grants 0.5 + 0.2 × floor insight; failing costs half your qi and a light injury. One attempt per opening.
  - **Qi pressure:** passing needs qi at least 40% of your maximum and a realm of at least floor − 1. Passing grants 0.2 × floor years of cultivation energy (through `realms.add_energy`, respecting bottlenecks); failing costs a quarter of your qi.
  - **Mirror:** a duel in mode `spar` against a copy of yourself (`fighter_for` on your own body and best art). Winning raises your mastery of that art by 0.05 and marks the trial passed; losing is a spar loss (no death).
- **Rivals:** a team placed in the chamber.
  - Talk to them (the normal talk menu), ask to pass (they let you if their attitude is at least neutral and their sect is not hostile to yours), fight (a duel in mode `duel`, where any verdict is allowed), or rob.
  - Or travel with them for a floor: they must be warm. Travelling together means you move as one and share the chambers' dangers.
  - A hostile or proud team with a realm margin over you attacks first, with chance 0.5.
  - **No rules inside:** killings are ordinary `killed` facts, but only those who come out can tell them (§5).
- **Stair:** go down (it creates your position on the next floor's first chamber) or up.
- **Inheritance:** the master's remnant soul tests you, **once per realm, ever**.
  - It is a duel in mode `test` against the master's shade: a fighter built from the master's art at one realm above yours.
  - Winning claims the inheritance:
    - the art, complete (1.0) and at its grade;
    - the weapon, as an item;
    - the title "Last Disciple of <master>";
    - a `master` kin bond to the dead master, who is made as a dead ancestor-like person the first time so the lineage page can name them.
  - Losing throws you back to the floor's first chamber, hurt, and you may not try again this opening.

### 3.3 Dying inside
- The usual 4b death and succession.
- The body stays in the realm. What the dead carried becomes loot in their chamber (`contents`) for later delvers.

## 4. Rivals, entry and the gate

### 4.1 Entry rules
- **Ceiling:** no one above the ceiling realm (First-rate or Second-rate, seeded) may pass. The gate refuses: "The seal presses you back; it will not admit a <realm>."
- **Token:**
  - each opening makes 3–8 jade tokens (`treasure` items, kind `token`, bound to the realm);
  - half go to the great sects with a seat within 3 regions at `announced`;
  - one hides as loot in a treasure chamber of another realm or a 4d race prize, if one is live;
  - one becomes an extra prize of the next Dragon-Phoenix Meet;
  - the rest are held by seeded wanderers;
  - a token is an ordinary item: bought, stolen or robbed;
  - entering uses it up.
- **Open:** anyone at the gate while it is open.
- **Quota:** each great sect with a seat within 3 regions may send up to 3.
  - Anyone else needs a sponsor (4e `sponsor_of`) or must sneak in. Sneaking in is a chance of 0.2 + 0.03 × (agility − 10), clamped to 0.05–0.6.
  - A caught sneak loses 1 standing with every sect sending delvers there.
- **Rule mix:** ancient realms are 50% ceiling, 30% token and 20% quota; newborn realms are 60% open and 40% token.

### 4.2 Who the NPCs send
- At `active`, each eligible sect sends its strongest members who pass the rule: up to 3 each (up to 2 for a token realm, one token each).
- Wanderers join with chance 0.3 each, up to 3.
- In total, 4–12 delvers, grouped into teams by sect (wanderers alone).
- The list is stored on the occurrence (`delvers`).

### 4.3 Rivals while the player is inside (full detail)
- **Placement:** on entering, the chosen teams are placed. Each goes on floor min(the realm's depth, max(1, the team's best realm)), in a seeded chamber of that floor; the strong go deeper.
- **Each player action,** each team takes one step:
  - they clear their chamber (taking the treasure, slaying the guardian by a realm-gap roll, attempting the trial by roll);
  - or they move on (to the next chamber, down a found stair).
- **Two teams in one chamber:**
  - rival sects (stance hostile, or a proud member) fight with the 2b duel sim, and the losers die with chance 0.5 (otherwise they flee up a floor);
  - other teams pass each other.
- **The inheritance:** a team that reaches it first tries it by a roll: chance 0.1 + 0.15 × (best realm − master's shade realm + 1), clamped to 0.02–0.6. It can be lost to them.
- **Deaths are real** (`died` with cause `realm`, plus a `killed` fact when someone killed them).

### 4.4 The gate closes
- At the end of `active`, everyone still inside is **sealed** until the next opening:
  - `sealed_in = realm` on the person;
  - the name goes on the realm's `sealed` list;
  - the sect sets their membership `status = "missing"` (as for the vanished in 4e).
- **A sealed NPC:**
  - lives on the 4a life clock at half pace;
  - gains cultivation ×3;
  - may die of age inside.
- **The sealed player** gets these choices:
  - **Cultivate in the realm's qi:**
    - time passes to the next opening, in one step per season, cultivating at ×3;
    - you age normally;
    - you may break through, and you may die of old age.
  - **Search the sealed floors for another way out:** each attempt takes a season, with chance 0.05 + 0.01 × comprehension. It is a formation trial; passing lets you out at the gate town.
  - **Let your heir carry on:** the 4b handoff while you live on, sealed. You stay a person in the world, and may walk out later as an NPC elder.
- **At the next opening,** the sealed walk out at `active` (a `walked_out` event). Their stories become facts, and their membership returns to `member`.
- **A one-off realm that closes on the sealed** leaves them sealed for good.
  - A player sealed in a one-off realm gets only the search and heir choices.
  - A search success is the only way out.

### 4.5 Openings far away (summarised)
- At the end of `active`, if the player never entered, one `realm_closed` event decides each delver's fate:
  - they came out with loot (chance 0.6 minus 0.05 × the floors they reached beyond 2);
  - they died (0.25);
  - or they were sealed (the rest).
- Loot is rolled per surviving delver: a treasure of the depth they reached, with chance 0.5.
- The inheritance falls to the best delver with chance 0.1 × max(0, best realm − master's shade realm + 2), rolled once.
- Survivors' `delved` facts (and `took`, `inherited`) spread from the gate town as rumours.
- Nobody moves, except the sealed, who leave their town and are `located_in` the realm.

### 4.6 Newborn realms
- When a treasure light (4d) starts, it cracks a newborn realm open instead of a race with chance 0.25.
- The realm is created at the light's site: 3–4 floors, a lesser master (the art's grade is lower), and the rule is open or token.
- Its first opening begins at once: no foretold stage, announced 3 days.
- It is one-off (60%) or cyclic with a period of 8–20 seasons.
- It is known only to those near the site (the site town's gossip), then by rumour.

## 5. Knowledge vs truth

- **A realm is known** by the heralds' news of an opening (a `phenomenon` fact, as in 4d), by being at its gate, or by rumour.
- **What happened inside** is known only by those who were there, or from the facts survivors carry out:
  - `delved` (entered and came out);
  - `took` (a treasure);
  - `slain_in` (killed someone inside);
  - `inherited`;
  - `sealed` (heard from those who came out without them).
- **The dead and the sealed tell no tales.** A killing inside records its fact without witnesses beyond those present. It spreads only when a present survivor comes out.
- **Screens** list only realms the player knows. They show the next opening as the player believes it, and past openings as heard.

## 6. Screens

- **`realms` / F5** (F11 is tournaments; the app sees no Shift):
  - known realms with gate town, entry rule and next opening;
  - your tokens for each realm;
  - past openings as you heard them;
  - the inheritance as you believe it ("claimed by X", "unclaimed", "unknown").
- **The delve:** the header (§3.1) and the chamber's choices. "Leave the realm" appears on floor 1; the page, sheet and journal work inside.
- **`enter`:** at the gate while it is open. Refusals are explained (the ceiling, no token, no quota place).
- **Brief:** inside, "Inside the Sunken Palace, floor 2 of 4; the gate closes in 3 days; Iron Fist disciples are near". At the gate town, the opening's stage.
- **Arrival lines** for heralds and "the gate stands open".
- **Journal** lines for every new event kind.
- **Sheet:** tokens, sealed-in status, inheritance titles.
- **Lineage page:** the dead master as `master`.
- **Help and commands:** `realms`, `enter`, `deeper`, `up`, `leave realm`.

## 7. Debug rules (in `check_world`)

1. A realm's inheritance is claimed at most once, and `inheritance_claimed_by` matches the `inherited` event.
2. Anyone `located_in` a realm is either inside during its active opening or on its `sealed` list.
3. A token is used at most once, and a live token has exactly one `owns` holder.
4. No one above a ceiling realm's ceiling is inside it during an opening (the sealed may outgrow it).
5. The player's `delve` position names a floor and chamber that exist in the realm they are `located_in`, and is absent when they are not inside one.

## 8. Testing

- **Seeding:**
  - three ancient realms per world;
  - a layout stable for a seed;
  - an old save gains its realms with first openings ahead (never backdated).
- **Openings:**
  - each realm opens on its own period;
  - the treasure light's branch cracks a newborn realm;
  - every entry rule: the ceiling refuses the strong, a token is used once, open entry, a quota with a sponsor, and sneaking in.
- **The delve:**
  - moving and time;
  - every chamber kind: treasure, guardian (fight or slip past), the three trials, rivals, stair;
  - the inheritance once per realm;
  - leaving only from floor 1;
  - dying inside.
- **Rivals:**
  - placed when you enter;
  - they step as you act, and loot they take is gone;
  - rival sects clash;
  - a team can win the inheritance first.
- **The gate:**
  - sealing NPCs and the player;
  - the three sealed choices;
  - walking out at the next opening;
  - a one-off realm keeps its sealed.
- **Far away:** a summarised closing and its rumours; nobody moves but the sealed.
- **Screens:** the realms page and F5, the delve header, briefs, arrival, journal, sheet, lineage, help.
- **Fuzz:** `test_a_realm_delver`: 300 turns with openings made frequent and a gate at the player's town. Entering, delving, fighting, leaving and sealing; every rule holds.
- **Speed (CPU time, `time.process_time`):**
  - a delve step with three rival teams inside: under 40 ms;
  - a summarised closing with 12 delvers: under 10 ms;
  - the realms page: under 30 ms;
  - the 200-year soak keeps its 100 ms season budget and the 500-year soak its 200 ms.
- **The entity cache:** all realm and delve state is written through `update_data`, and `check_world`'s drift check stays clean in the fuzz and soak.

## 9. Out of scope for 4f

- Succession crises (4g). A sealed sect heir is a natural hook, but it is not built here.
- Realms or cave abodes the player makes.
- Realms beyond 6 floors.
- A drawn ASCII map of a realm (the delve has a text header only).
