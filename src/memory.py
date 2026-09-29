"""On-device memory: Qdrant Edge shard (vectors) + SQLite ledger (state). Never touches the network."""
import time

from qdrant_edge import (Distance, EdgeConfig, EdgeShard, EdgeVectorParams,
                         Point, Query, QueryRequest, UpdateOperation)

import db
import policy
from config import DEVICE_ID, DIM, SHARD_DIR, VECTOR_NAME
from embedder import embed

_shard = None


def shard() -> EdgeShard:
    """Open the shard once per process (create on first run, load afterwards)."""
    global _shard
    if _shard is None:
        SHARD_DIR.mkdir(parents=True, exist_ok=True)
        if any(SHARD_DIR.iterdir()):
            _shard = EdgeShard.load(str(SHARD_DIR))
        else:
            _shard = EdgeShard.create(str(SHARD_DIR), EdgeConfig(
                vectors={VECTOR_NAME: EdgeVectorParams(size=DIM, distance=Distance.Cosine)}))
    return _shard


def close():
    global _shard
    if _shard is not None:
        _shard.close()
        _shard = None


def index(mid: int, text: str):
    """Write/overwrite one vector in the shard."""
    shard().update(UpdateOperation.upsert_points(
        [Point(id=mid, vector={VECTOR_NAME: embed(text)}, payload={"text": text})]))


def add(text: str, tags: str = "", force_local: bool = False) -> int:
    local_only, reason = policy.classify(text, tags, force_local)
    mid = db.next_id()
    db.insert(mid, text, tags, local_only, reason,
              "local_only" if local_only else "pending", time.time(), DEVICE_ID)
    index(mid, text)
    db.log("add", f"#{mid} saved on device — " + (f"LOCAL ONLY ({reason})" if local_only else "queued for sync"))
    return mid


def edit(mid: int, text: str, tags: str = "", force_local: bool = False):
    old = db.get(mid)
    local_only, reason = policy.classify(text, tags, force_local or bool(old and old["local_only"] and old["reason"] == "marked local-only by user"))
    keep_synced_ts = old["synced_ts"] if old else 0.0
    db.insert(mid, text, tags, local_only, reason,
              "local_only" if local_only else "pending", time.time(), DEVICE_ID, keep_synced_ts)
    index(mid, text)
    db.log("edit", f"#{mid} edited on device — " + ("LOCAL ONLY" if local_only else "queued for sync"))


def delete(mid: int):
    row = db.get(mid)
    if not row:
        return
    shard().update(UpdateOperation.delete_points([mid]))
    if row["sync_state"] == "local_only":
        db.hard_delete(mid)
    else:
        db.mark_deleted(mid)          # cloud delete happens on next sync
    db.log("delete", f"#{mid} deleted on device")


def search(query: str, limit: int = 5):
    """Returns (results, latency_ms). Pure on-device work."""
    t0 = time.perf_counter()
    vec = embed(query)
    hits = shard().query(QueryRequest(
        query=Query.Nearest(vec, using=VECTOR_NAME),
        limit=limit, with_vector=False, with_payload=True))
    ms = (time.perf_counter() - t0) * 1000
    out = []
    for h in hits:
        row = db.get(int(h.id))
        if row and not row["deleted"]:
            out.append({"id": row["id"], "score": float(h.score), "text": row["text"],
                        "tags": row["tags"], "sync_state": row["sync_state"]})
    db.log("search", f"'{query}' → {len(out)} results in {ms:.0f} ms (on-device)")
    return out, ms
