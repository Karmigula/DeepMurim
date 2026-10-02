# DeepMurim

A single-player wuxia text game set in a world that keeps running for centuries. Every person remembers what you did to them. Rumours of your deeds spread from town to town, and are retold, garbled, or lied about along the way. Sects rise, feud and fall, masters die and their disciples fight over the seat, and heaven keeps its own ledger of your merit and sin.

The world is procedural and seeded. The engine is the truth: it keeps every fact, memory and belief in a save file. An optional AI layer (Claude Code, or OpenCode's free models) can narrate it in prose and answer what you type, but it can only propose changes. The engine checks every one before anything happens.

## Quick start (Windows)

1. Install [Python 3.14](https://www.python.org/downloads/).
2. Double-click `run.bat`. The first run creates `.venv` and installs `requirements.txt`; after that it starts the game.

From a shell instead:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Your saves go to `saves/`, settings to `settings.json`, and crash and bug reports to `logs/`, all beside the game.

## What you can do

- **Live a cultivator's life.** You have a body and meridians, techniques to practise, and breakthroughs from mortal to the higher realms, with tribulations at the gates.
- **Fight.** You can duel, spar, and win your way through road encounters and tournaments. A won duel ends with a verdict: spare, rob, cripple or kill. The world remembers which.
- **Talk.** Ask people about work, the town and each other, trade rumours, tell lies, and wear a mask.
- **Belong.** Join or found a sect, climb its ranks, take its duties, and fight in its succession crises and intrigues.
- **Make things:**
  - alchemy: herbs, pills, poisons and medicine;
  - forging and formations;
  - items that carry their own history.
- **Explore** secret realms, the markets, and a world that keeps moving: a clock, seasons, lineages, the rise and fall of the ranked.
- **Keep your heart:**
  - the dao heart leans with what you do;
  - karma counts your merit and sin;
  - heavenly tribulations weigh both.

## Controls

Press a number to pick a choice, or type a command and press Enter. `help` lists them all. The most used:

| Keys or words | What they do |
|---|---|
| `look`, `talk <name>`, `go <place>`, `bye`, `journal` | Look around, speak, travel, end a talk, read your chronicle |
| `cultivate`, `meditate <day\|week\|month\|season>`, `practise <art>`, `breakthrough` | Cultivation |
| `challenge`, `spar`, `strike`, `feint`, `guard`, `flee`, `yield` | Fighting |
| `news`, `rumours`, `tell`, `ask about <name>` | Talk and rumour |
| F1 | The AI menu (see below) |
| F2 / F3 | Swap the art's side / hide the art |
| F4 | Your character sheet |
| F5, F6, F7, F8, F10, F11 | Realms, standing, ledger, lineage, rankings, tournaments |
| F9 | Report a bug (saves the session for you) |
| F12 | The debug overlay |
| Alt+Enter | Full screen |
| Esc | Back, or the title menu |

## The AI layer (optional)

The game is complete without it. To turn it on, press **F1** and set the mode:

- **assist:** the engine's words show at once, and the model's prose replaces them when it comes;
- **AI only:** only the model's prose is shown;
- **off** (the default): no AI, and no cost.

With the AI on, you can also **type what you do** ("I buy the tea seller a cup of tea"), or in a conversation **type what you say**.
- The model answers in a paragraph and proposes changes: a payment, a feeling, a deed, a newcomer.
- The engine accepts only what your state allows.
- While it waits, a small animation runs. **Esc** lets it go, and nothing happens.

Choose a backend in the F1 menu:

- **Claude Code** runs on your own Claude login (Pro or Max plan) through the Claude Agent SDK. Install [Claude Code](https://claude.com/claude-code), run `claude` once, and log in with `/login`.
  - DeepMurim never asks for your login.
  - It sets `ANTHROPIC_API_KEY` empty for Claude Code, so your plan is used and the API is never billed.
- **OpenCode** offers only OpenCode's own free models. Install [OpenCode](https://opencode.ai); the menu lists the free ones. It is slower: about 10-60 s for a typed action.

The F1 menu's **Connect** page shows what is installed. It also gives the address of DeepMurim's read-only MCP server, which runs while the AI is on, so your own Claude Code or OpenCode sessions can look up the world as your character knows it.

What the model is told is only what your character could know. What you type and the game's state are sent to the backend you choose.

## For developers

- **Tests:** `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` runs about 1,750 tests in about 6 minutes.
- **The soak:** add `-m slow` for a 500-year history and a 200-year speed test (about 3 minutes).
- **Live AI round trips:** set `DEEPMURIM_LIVE=1` and add `-m live`. They need Claude Code logged in, and OpenCode installed.
- **Where things are:** `docs/REVIEW-GUIDE.md` maps the code and lists the rules it keeps:
  - only events change the world;
  - the player sees only what they know;
  - the AI never writes the world.
- **Adding to the world** (events, crafts, proposal kinds, MCP tools): see the fork guide, `docs/world-events.md`.
- **History:**
  - `CHANGELOG.md` says what each phase added;
  - `PROGRESS.md` says where things stand and what is deferred;
  - `docs/superpowers/specs/` and `docs/superpowers/plans/` hold each phase's design and plan.
