# EdgeMind

**Semantic memory that keeps working when the internet doesn't.**

An offline-first app where a device holds its own local, searchable memory —
real semantic search, not just keyword matching — and syncs to the cloud only
when a connection is available and the user chooses to.

---

## The problem

Edge devices — robots, kiosks, field devices, vehicles — often need to search
and reason over their own data, but most AI-powered systems assume constant
access to a cloud service. When connectivity drops, search either breaks
completely or falls back to plain keyword matching, which misses anything
phrased differently from how it was originally written.

## The solution

A local, in-process vector memory (Qdrant Edge) stores each memory's meaning,
not just its text, so semantic search works with zero network calls. A
"Sync Now" button pushes local changes to a Qdrant Cloud collection and pulls
down anything new, whenever the user decides to reconnect. The app behaves
identically online or offline — the only thing that changes is whether
"Sync Now" does something or stays queued.

## Features

- **Offline semantic search** — meaning-based, not keyword-based, computed
  entirely on-device
- **Add, edit, delete** memories locally, no network required for any of it
- **Manual two-way sync** — push local changes up, pull remote changes down
- **Local-only policy** — memories matching sensitive keywords (passwords,
  PINs, gate codes, etc.) never sync unless the user overrides it, with the
  reason shown in the UI
- **Conflict detection** — if the same memory changed on both sides,
  last-write-wins, and the conflict is logged with both versions
- **Activity log** — a readable timeline of every add, search, sync, and
  conflict
- **Simulated second device** — demo tools let you show pull and conflict
  behavior from one laptop, clearly labeled as a simulation in the UI

## Architecture

```
┌─────────────────────────────────────┐
│              DEVICE                  │
│                                       │
│   Streamlit UI                       │
│        │                             │
│   memory.py ── policy.py             │
│        │                             │
│   Qdrant Edge shard  (local vectors) │
│   FastEmbed          (local CPU)     │
│   SQLite ledger      (state + log)   │
│                                       │
└───────────────┬───────────────────────┘
                 │  "Sync Now" (manual, only when online)
                 ▼
        ┌─────────────────┐
        │  Qdrant Cloud     │
        │  (free tier)      │
        │  "memories"       │
        │  collection       │
        └─────────────────┘
```

Only `sync.py` ever makes a network call. Everything else — search, add,
edit, delete — runs entirely against the local shard and the local ledger.

## Tech stack

| Piece | Tool | Cost |
|---|---|---|
| Local vector engine | [qdrant-edge-py](https://pypi.org/project/qdrant-edge-py/) | Free, open source, runs in-process |
| Local embeddings | FastEmbed (`BAAI/bge-small-en-v1.5`, 384-dim) | Free, runs on CPU, no API |
| App / UI | Streamlit | Free |
| Local state | SQLite | Free |
| Cloud sync target | Qdrant Cloud (free tier) | Free — 1GB RAM / 4GB disk, no card |
| Tests | pytest | Free |
| Environment | uv | Free |

No paid services anywhere in the stack, no credit card required for any
piece.

## Project structure

```
EDGEMIND/
├── src/
│   ├── app.py         # Streamlit UI — all tabs and sidebar
│   ├── memory.py       # Local add / edit / delete / search — never touches the network
│   ├── sync.py          # The only module that talks to the network: push, pull, conflicts
│   ├── db.py             # SQLite ledger — sync state per memory, activity log
│   ├── embedder.py     # Local FastEmbed wrapper
│   ├── policy.py         # Rule-based local-only classifier
│   ├── config.py        # Paths, model name, constants, sensitive keyword list
│   ├── seed.py            # Sample demo data (field-maintenance notes scenario)
│   └── main.py
├── tests/
│   ├── conftest.py
│   └── test_core.py      # Offline search, local-only policy, persistence, sync, conflicts
├── .env                 # Qdrant Cloud credentials (gitignored, not committed)
├── .env.example
├── .gitignore
├── pyproject.toml
└── uv.lock
```

## Setup

```bash
git clone <this repo>
cd EDGEMIND
uv sync
```

1. Copy `.env.example` to `.env` and fill in your Qdrant Cloud cluster URL
   and API key (free tier, no card required at
   [cloud.qdrant.io](https://cloud.qdrant.io)).

2. Download the embedding model once, while online:
   ```bash
   cd src
   uv run python -c "from embedder import embed; print(len(embed('hello')))"
   ```
   Should print `384`. From this point on, search works fully offline.

3. Run the tests:
   ```bash
   uv run pytest -q tests
   ```

4. Run the app:
   ```bash
   cd src
   uv run streamlit run app.py
   ```

5. Load sample data: sidebar → **Demo tools** → **Load sample notes**.

## Demo script

1. Load sample notes.
2. Turn on **Simulate offline** — search by meaning (e.g. "why is the
   machine so noisy?") and get relevant results with zero network calls.
3. Add a new note while still offline — Pending count goes up.
4. Turn simulated offline off, click **Sync Now** — local changes push to
   Qdrant Cloud.
5. Demo tools → simulate a second device adding a note directly to the
   cloud, then **Sync Now** again — it pulls down and becomes searchable.
6. Edit the same memory on both "devices" while offline, then sync — the
   Activity tab shows the conflict and which version won.

## Honest scope

This is a working proof-of-concept of the offline-first-with-sync pattern.
Specifically, as built:

- Demoed on a single real device; a second device is simulated for pull and
  conflict scenarios, not run on separate hardware.
- Sync is triggered manually via a button, not automatic background
  detection of connectivity.
- Conflicts resolve as last-write-wins — no merge or CRDT logic.
- The local-only sync policy is keyword-based, not LLM-based.
- No authentication or multi-user support.
- Pull scans the full cloud collection each time — fine at demo scale, not
  optimized for large datasets or many devices.
- Deletes made on one device don't currently propagate back to another
  device on pull.

## Future work

- Multi-device fleet sync with per-device tracking
- Automatic background sync instead of a manual button
- LLM-assisted sync policy (deciding what should stay local vs. sync)
- The two-shard mutable/immutable snapshot pattern from Qdrant's own sync
  guide, once verified against the free-tier cluster