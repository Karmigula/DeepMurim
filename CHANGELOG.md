# Changelog

DeepMurim is built in phases. Each one has a design spec in `docs/superpowers/specs/` and a verified implementation plan in `docs/superpowers/plans/`. Each phase lands on `master` after a review round and a minors round. Newest first.

## The whole-project review (2026-10-01)

Merged from `ultrareview-fixes` as `0cd36b5`. One ultrareview of the core slice (45 files, 6,560 lines; the review's cap is 8,000): the AI layer and app shell, the engine core and invariants, the world core. Its 10 findings were all fixed, each behaviour fix with a test that failed first (`tests/test_ultrareview.py`).

### Added
- `README.md`: what the game is, how to run it, the controls, the AI layer and its backends.
- `docs/REVIEW-GUIDE.md`: a map of the code for reviewers, with the rules it keeps, its performance budgets, its threads, and what is already known.

### Fixed
- F11 opens the tournaments, as help says; the full screen is now Alt+Enter (help names it).
- A belief made surer in place is checked again by the invariants (the incremental check skipped it).
- A crash report that cannot be written (a full disk) is told, never raised.
- Prose left behind lets its backend exchange go, so the next turn's prose never waits behind it.
- The prose cache keeps the latest 200 turns, not a whole session's.
- The body check's memory belongs to its world and dies with it.
- Turning the AI off never waits for the MCP server to stop; the server's imports are warmed while the title shows.
- One shared helper each for names in a text, a free port, and ending a process tree.

## Phase 6c: Typed actions and free talk (2026-10-01)

Merged from `phase-6c`. Spec: `2026-10-01-phase6-claude-layer-design.md`, section 14. Plan: `2026-10-01-phase6c-typed-actions-talk.md`.

### Added
- **Type what you do.** With the AI on, a line the game does not know goes to the model: in a conversation, as words said to that person; else, as a deed.
  - The model answers in a paragraph and proposes changes from a fixed vocabulary: pay, give, a feeling, a deed, a belief told, a newcomer, a hurt, time passing, or one of this turn's choices.
  - The engine checks each change against the rules and your real state, and commits only what stands.
  - In assist mode, each change also shows as a short engine line; in AI-only mode, only the paragraph.
- **The wait.** Input pauses under an animated line naming the backend; Esc lets it go and nothing happens. A failure says "You hesitate; nothing comes of it."
- **Free talk is remembered.** Each exchange is a `talked` event, which the person recalls in later talk and briefs.
- **Deeds count.** A kind or cruel deed is a tale that spreads, and moves karma and the dao heart; one a day.
- **F12** shows the last typed line: its job, what stood, what was rejected and why; bug reports keep the whole exchange.

### Faster
- The grammar is read once a process: every MCP request and prompt was re-reading all 34 files (a prompt went from 15 ms to 2 ms).
- The AI's events are checked through a partial index, and only what is new each turn.

### Fixed (review)
- A paragraph telling of a payment the engine rejected is never shown, even when you typed the sum.
- Deeds and feelings weigh once a day, so they cannot be farmed.
- The same line asking for a newcomer twice no longer crashes; a turn that fails partway takes its changes back.
- AI-only mode keeps what an action itself brought (an ambush, a death); possessive names pass the guard; a conversation's lines are forgotten when it ends.

### Fixed (minors)
- Talking past a person's patience (three lines a point of it) ends the conversation, as asking too much does.
- Esc also lets the backend's exchange go, so the next typed line never waits behind it.
- In a fight, heaven's waves or a heart trial, a typed line may only choose or feel.
- An action the accepted changes made impossible is not run; deed names are whole names; a newcomer never shares a name with someone here; a wielded thing no longer hides another of its name.
- `check_ai` checks every kind; the session log keeps at most 4,000 characters of a prompt; "An innkeeper".

## Phase 6b: Two backends, the AI menu, one MCP server (2026-10-01)

Merged from `phase-6b`. Spec: `2026-10-01-phase6-claude-layer-design.md`, section 13. Plan: `2026-10-01-phase6b-backends-menu.md`.

### Added
- **Two backends.**
  - **Claude Code**, through the Claude Agent SDK, on your own Pro/Max login. `ANTHROPIC_API_KEY` is overridden to empty, so it never bills the API. About 3.5 s a paragraph.
  - **OpenCode**, with its own free models only. A hidden `opencode serve` is kept warm while the AI is on: about 8 s a paragraph.
- **The AI menu (F1).** It sets the mode, the backend, the prose model, and the model for typed actions and talk (used from 6c).
  - Claude Code offers Haiku 4.5, Sonnet 5 and Opus 5.5.
  - OpenCode offers only its own provider's models at a cost of 0. The list is read once a session, never on the game's thread.
  - The menu says why a backend cannot be used.
- **The Connect page.** It shows what is installed and how to sign in, plus copy-paste MCP setup for your own Claude Code or OpenCode.
- **One long-lived MCP server** over HTTP on 127.0.0.1. It runs while the AI is on, reads the save anew on every request, and never writes.
- **Prose a paragraph long**, of about 3–6 sentences.
- **Prefetch:** the lookups a model would ask for, made in advance, for 6c's talk.

### Fixed (review)
- A reply that came too late is never shown as the next turn's prose.
- Turning the AI off closes the backend, so no warm server or open session is left running.
- A hand-edited settings file can't choose a model the menu wouldn't offer.
- Stopping the server, or closing an old backend, never holds the game.

### Fixed (minors)
- The notices name the backend in use ("OpenCode's prose cannot be used").
- OpenCode's commands open no console window. A server that dies at start is let go at once, and a prompt too long for the command line is refused whole rather than cut.
- Claude Code bundled with the Agent SDK counts as installed.
- The Connect page looks for the programs once, not every frame.
- F1 over the character sheet shows the menu.
- Prefetch finds a name only as a whole word.

## Phase 6a: The Claude layer's foundation, and Claude's prose (2026-10-01)

Merged from `phase-6a`. Spec: `2026-10-01-phase6-claude-layer-design.md`. Plan: `2026-10-01-phase6a-claude-foundation.md`.

### Added
- **Claude's prose (F1).** Off by default. *Assist* shows the engine's text at once, then Claude's in its place; *AI only* shows "…" until Claude's prose comes. Any failure leaves the engine's text.
  - One `claude -p` call per turn, run bare (no user settings, skills, hooks or MCP servers; thinking off): about 4 s and well under a cent a call, on the user's own Claude subscription.
  - A guard refuses prose that names someone unheard of, makes up a name, states a number the turn did not carry, or drops one it did.
  - Three failures in a row pause Claude for five minutes. A logged-out Claude Code turns the prose off and says to log in.
- **The state pack.** What Claude is told of you: here, your limits, what you carry, lately, your sheet. Built only from what you could read yourself.
- **A read-only MCP server** (`mcp_server/`), the world as its player knows it, for phase 6b's Claude jobs. It opens the save so that nothing can be written.
- **Seeing it work.** The F12 overlay shows the mode, the last exchange and why prose was refused; bug reports keep each exchange.

### Fixed
- The 5d, 5e and 5f sub-tick speed tests are timed by the fine wall clock.
- In a world of centuries, the chronicle of one person and the gossip of a town are read far faster (the journal and every attitude benefit).

## Phase 5f: Karma and tribulations, and the close of phase 5 (2026-09-28)

Merged as `af32a92`. Spec: `2026-09-28-phase5f-karma-tribulations-design.md`.

### Added
- **Heaven's ledger.** Karma is hidden merit and sin, kept apart from the dao heart.
  - Deeds, duel verdicts and killings all count toward it. Killing someone who yielded, or a mortal, counts heaviest; killing the wicked earns merit.
  - A fortune teller reads it back in words for 50 silver and names your heaviest ties.
- **Karmic threads.** Sparing, healing, freeing, robbing, crippling, false accusation and killing tie you to particular people (at most twelve).
  - On the road, the heaviest tie within reach can turn up.
  - Those who owe you repay you in silver. Those you wronged block the road as a new kind of encounter; you can make amends or fight them.
- **Tribulations weighed by karma.** Sin adds waves and strength, and merit lightens them.
  - From Transcendent onward, heavenly fire alternates with the lightning. A demon you carry comes once, as a wave.
  - Each wave is played: endure it, swallow a strong enough pill, shelter under the new Tribulation-Splitting array, or face or bury the demon.
  - A heavy sinner can die on the last wave of six or more.
- **Minor tribulations** come at the breakthrough to Second-rate, and once a year when sin outweighs merit by 150.
- **The world.**
  - 4d's lightning can kill NPCs who carry heavy sin, and it spreads as news.
  - Heaven sometimes strikes down the wicked.
  - A heavy sinner loses silver or takes a fall.
  - A town with a monk has a temple that takes alms (for merit) and incense.

### Fixed
- **Phase 5's two deferred rules.** An NPC master living in another town no longer feeds their bound. A smith who dies with a commission unforged has their estate return the silver.
- Misfortune and the commission refund had no narration grammar.
- A tribulation that gathers during a duel now waits until the fight is over.
- Paying respects where the dead don't lie now says why.

## Phase 5e: The dao heart (2026-09-28)

Merged as `cf45716`. Spec: `2026-09-28-phase5e-dao-heart-design.md`.

### Added
- **The heart.** A steadiness gauge and a lean between righteous and ruthless, both moved by deeds. It weighs on breakthroughs and deviation, and pivots at its rest (60), so an untouched heart changes nothing.
- **Heart demons.**
  - Guilt, grudges, fear and grief are gathered from what happens to you.
  - Beating the foe, paying respects at a grave, amends to the dead one's kin, or time lays them to rest.
  - The heaviest rises at a breakthrough to Second-rate or beyond, to be faced, buried or turned back from.
- **Epiphanies and daos.** Each martial form and element, yin and yang included, has a dao. A completed dao sets `returned_to_origin`, which makes Life-and-Death reachable for the first time.
- **Oaths on the heart.** Vengeance, protection and abstinence can be kept, broken or released, and spread as rumours.
- **Weapon spirits and cursed blades.** Blades count their kills and wake a loyal or bloodthirsty spirit. One famous blade in five is cursed. A smith of skill 3 or more can read a blade.
- **The world.** Troubled masters sometimes go mad and hunt the player, and a master enlightened in a dao resonance opens a dao.

### Fixed
- A hungry blade in a troubled hand no longer offers "Spare" at the verdict.
- The mad no longer say "they have not forgotten you".
- Reactions made by listeners (epiphanies, oaths kept at a death, spirits felt) are now shown on screen, not only in the journal.
- A protected person who dies of illness releases the oath.
- Killing a beast breaks no abstinence.
- The season speed tests of 5c, 5d and 5e now run twenty rounds and compare the fastest five.

## Phase 5d: Forging and formations (2026-09-28)

Merged as `78e2f25`. Spec: `2026-09-28-phase5d-forging-formations-design.md`.

### Added
- **Materials.** Ore sold by the smith, bones and cores from slain beasts, and star iron.
- **Forges.** You can own one, rent a smith's, or build one for your sect.
- **Forging.** Mastery per form, refining held gear a grade, and naming a masterwork into a famous weapon.
- **Formations.** Patterns are learnt from manuals and ancient arrays, and laid with flags. They cover sect defences, battle arrays, concealment and a seclusion ward.
- **Crafters and the Meet.** Smiths and formation masters have skill that grows, sell wares and take commissions. The yearly Meet of Hammer and Furnace judges forging and refining.

### Fixed
- Forging, refining, laying and a master's wares no longer fall off the numbered menu.
- Commissions name their piece properly.
- The crafts page says where the Meet is held.

## Phase 5c: The alchemy world (2026-09-27)

Merged as `a8e1af9`. Spec: `2026-09-26-phase5c-alchemy-world-design.md`.

### Added
- Sect pill halls and herb gardens, raided at night.
- The Alchemists' Guild and its ranks.
- Recipe scrolls that are bought, taught and stolen.
- Physicians, famous doctors, and poisoners for hire.
- NPCs who refine and take pills.
- Control pills with their masters and their bound.

## Phase 5b: Alchemy, medicine and poison (2026-09-26)

Merged as `08545cc`. Spec: `2026-09-26-phase5b-alchemy-design.md`.

### Added
- Herbs, tasting and gathering; recipes found by experiment.
- Pills for cultivation, healing, cures, poison and body tempering.
- Residue left in the body.
- Poisons that spread until they are sealed, forced out or cured.
- The poison path and the Poison Body.

## Phase 5a: Items with history (2026-09-26)

Merged as `4a13bce`. Spec: `2026-09-26-phase5a-items-history-design.md`.

### Added
- Weapon and armour grades that matter in a fight.
- Provenance: each notable item remembers its maker, owners and deeds.
- Famous weapons, known by legend, change hands, and are ranked each spring.
- The smith's stall and the sect armoury.

## Phase 4h: Succession intrigue (2026-09-26)

Merged as `dd9b4bd`. Spec: `2026-09-25-phase4h-succession-intrigue-design.md`.

### Added
- A hidden layer under succession crises: poisoned masters, puppet claimants, cult spies, forged wills, and framed heirs who return.
- New ways to the seat: the supreme art, the founder's test, marriage, an arbiter's verdict.
- The player's own plots, and the risk of being found out.

## Phase 4g: Succession crises (2026-09-25)

Merged as `b5932dc`. Spec: `2026-09-25-phase4g-succession-crises-design.md`.

### Added
- Leaderless sects fall into crisis. Claimants rise and camps form around them.
- The seat is won by backing, by trial by combat or by war, and a war that drags on can split the sect.
- The player plays in their own sects' crises and can lose their own sect.

## Phase 4f: Secret realms (2026-09-25)

Merged as `d24f529`. Spec: `2026-09-25-phase4f-secret-realms-design.md`.

### Added
- Seeded pocket worlds that open for a few days.
- They are delved floor by floor, with rival delvers inside, ancient formation trials, and the risk of being sealed in.

## Phase 4e: Tournaments (2026-09-24)

Spec: `2026-09-24-phase4e-tournaments-design.md`.

### Added
- The Grand Martial Assembly, the Dragon-Phoenix Meet, sect contests and lei tai platforms.
- Bouts fought live, betting, watching rivals, and fixed matches.

## Phase 4d: World events (2026-09-24)

Spec: `2026-09-24-phase4d-world-events-design.md`.

### Added
- The world-event framework, and the fork guide (`docs/world-events.md`).
- Heavenly phenomena: comets, blood moons, qi tides, dao resonance, beast tides, and tribulation lightning.
- The Heavenly Ranking Pavilion.

## Phase 4c: Trade (2026-09-23)

Spec: `2026-09-23-phase4c-trade-design.md`.

### Added
- Town markets with regional prices, and price events such as war, famine and festivals.
- Carrying goods between towns, and price knowledge that comes from travel and rumour.

## Phase 4b: Lineage (2026-09-23)

Spec: `2026-09-23-phase4b-lineage-design.md`.

### Added
- Death by age, by a killer's hand, by qi deviation or by execution.
- Heirs chosen from those bound to you, inheritance, and avengers.

## Phase 4a: The world clock (2026-09-23)

Spec: `2026-09-23-phase4a-world-clock-design.md`.

### Added
- NPCs live without you: they age, cultivate, marry, move, feud and die.
- Factions grow, clash, and replace their leaders.

## Phase 3c: Founding (2026-09-23)

Spec: `2026-09-23-phase3c-founding-design.md`.

### Added
- Founding your own sect: land, sworn followers and a charter.
- Running it: recruiting, teaching, halls, the treasury, and the gate.

## Phase 3b: Factions (2026-09-23)

Spec: `2026-09-23-phase3b-factions-design.md`.

### Added
- Factions in the world: joining, trials, ranks, duties and arts.
- Politics, the law, leaving a faction, and spies.

## Phase 3a: Social memory and rumours (2026-09-23)

Spec: `2026-09-23-phase3a-social-rumours-design.md`.

### Added
- Facts and beliefs, rumours that change as they are retold, and town reputation.
- Kin, killing, and masks.

## Phase 2: Cultivation and combat (2026-09-22 to 2026-09-23)

Spec: `2026-09-22-phase2-cultivation-combat-design.md`.

### Added
- **2a.** A body that remembers: a dantian, meridians, injuries and a hidden constitution. Also meditation, seclusion, breakthroughs, qi deviation, and the F4 character sheet.
- **2b.** Exchange-round duels, road encounters, and grudge challenges. Arts come from teachers, from manuals that may lie about how complete they are, and from fragments turned into arts of your own.

## Phase 1: Foundation (2026-09-22)

Spec: `2026-09-22-deepmurim-design.md`.

### Added
- A seeded, endless world of towns to walk between.
- NPCs who remember you across saves.
- Procedural prose beside ASCII art.
