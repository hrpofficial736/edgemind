"""The ONLY module that talks to the network (Qdrant Cloud).
Sync Now = pull first (detect conflicts), then push pending changes."""
import time

from qdrant_client import QdrantClient, models
import db
import memory
from config import (COLLECTION, DEVICE_ID, DIM, QDRANT_API_KEY, QDRANT_URL,
                    REMOTE_DEVICE_ID)
from embedder import embed

_client_factory = None
_online_cache = (0.0, False)
_last_error = ""


def last_online_error() -> str:
    return _last_error

def set_client_factory(f):
    """Tests inject an in-memory client here."""
    global _client_factory, _online_cache
    _client_factory = f
    _online_cache = (0.0, False)


def client() -> QdrantClient:
    if _client_factory:
        return _client_factory()
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=15, prefer_grpc=True)


def configured() -> bool:
    return bool(_client_factory or (QDRANT_URL and QDRANT_API_KEY))


def is_online(simulate_offline: bool = False, use_cache: bool = True) -> bool:
    global _online_cache, _last_error
    if simulate_offline or not configured():
        return False
    if use_cache:
        ts, val = _online_cache
        if time.time() - ts < 5:
            return val
    try:
        client().get_collections()
        val, _last_error = True, ""
    except Exception as e:
        val, _last_error = False, str(e)
    _online_cache = (time.time(), val)
    return val


def _ensure_collection(c: QdrantClient):
    if not c.collection_exists(COLLECTION):
        c.create_collection(collection_name=COLLECTION,
                            vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE))


def _cloud_points(c: QdrantClient):
    pts, offset = [], None
    while True:
        batch, offset = c.scroll(COLLECTION, limit=100, offset=offset, with_payload=True, with_vectors=False)
        pts += batch
        if offset is None:
            return pts


def _apply_remote(mid, pl):
    db.insert(mid, pl.get("text", ""), pl.get("tags", ""), False, "", "synced",
              float(pl.get("updated_ts", 0)), pl.get("device_id", REMOTE_DEVICE_ID),
              synced_ts=float(pl.get("updated_ts", 0)))
    memory.index(mid, pl.get("text", ""))


def sync_now(simulate_offline: bool = False) -> dict:
    res = {"online": False, "pulled_new": 0, "pulled_updates": 0, "conflicts": 0,
           "pushed": 0, "deleted": 0, "error": None}
    if not configured():
        res["error"] = "Qdrant Cloud is not configured (.env missing)"
        return res
    if not is_online(simulate_offline, use_cache=False):
        db.log("sync", "Sync skipped — device is offline; changes stay queued locally")
        return res
    res["online"] = True
    try:
        c = client()
        _ensure_collection(c)

        # ---- PULL -----------------------------------------------------------
        for p in _cloud_points(c):
            mid, pl = int(p.id), (p.payload or {})
            rts = float(pl.get("updated_ts", 0))
            local = db.get(mid)
            if local is None:
                _apply_remote(mid, pl)
                res["pulled_new"] += 1
                db.log("pull", f"#{mid} new from {pl.get('device_id', '?')}: {pl.get('text', '')[:60]}")
            elif local["local_only"] or local["deleted"]:
                continue
            elif local["sync_state"] == "synced":
                if rts > local["updated_ts"]:
                    _apply_remote(mid, pl)
                    res["pulled_updates"] += 1
                    db.log("pull", f"#{mid} updated by {pl.get('device_id', '?')}")
            elif local["sync_state"] == "pending" and rts > local["synced_ts"]:
                # remote changed since our last sync AND we edited offline -> real conflict
                remote_wins = rts > local["updated_ts"]
                db.log("conflict",
                       f"#{mid} edited on both sides. LOCAL: '{local['text'][:50]}' | "
                       f"REMOTE ({pl.get('device_id', '?')}): '{pl.get('text', '')[:50]}' "
                       f"→ {'remote' if remote_wins else 'local'} wins (last write wins)")
                res["conflicts"] += 1
                if remote_wins:
                    _apply_remote(mid, pl)

        # ---- PUSH -----------------------------------------------------------
        to_upsert, to_delete = [], []
        for row in db.pending():
            (to_delete if row["deleted"] else to_upsert).append(row)
        if to_upsert:
            c.upsert(COLLECTION, points=[models.PointStruct(
                id=r["id"], vector=embed(r["text"]),
                payload={"text": r["text"], "tags": r["tags"], "updated_ts": r["updated_ts"],
                         "device_id": r["device_id"]}) for r in to_upsert])
            for r in to_upsert:
                db.mark_synced(r["id"], r["updated_ts"])
            res["pushed"] = len(to_upsert)
            db.log("push", f"pushed {len(to_upsert)} memories to Qdrant Cloud")
        if to_delete:
            c.delete(COLLECTION, points_selector=models.PointIdsList(points=[r["id"] for r in to_delete]))
            for r in to_delete:
                db.hard_delete(r["id"])
            res["deleted"] = len(to_delete)
            db.log("push", f"deleted {len(to_delete)} memories on the cloud")

        db.set_meta("last_sync_ts", time.time())
        db.log("sync", f"Sync complete — pulled {res['pulled_new'] + res['pulled_updates']}, "
                       f"pushed {res['pushed']}, conflicts {res['conflicts']}")
    except Exception as e:                       # never crash the UI on a network hiccup
        res["error"] = str(e)
        db.log("sync", f"Sync failed: {e}")
    return res


# ---- demo helpers: pretend to be a second device (writes straight to the cloud) ----
def simulate_remote_new(text: str) -> int:
    c = client()
    _ensure_collection(c)
    mid = int(time.time())                      # far above local ids, so no clash
    c.upsert(COLLECTION, points=[models.PointStruct(
        id=mid, vector=embed(text),
        payload={"text": text, "tags": "", "updated_ts": time.time(), "device_id": REMOTE_DEVICE_ID})])
    db.log("simulate", f"[SIMULATION] {REMOTE_DEVICE_ID} added #{mid} on the cloud")
    return mid


def simulate_remote_edit(mid: int, new_text: str):
    c = client()
    _ensure_collection(c)
    c.upsert(COLLECTION, points=[models.PointStruct(
        id=mid, vector=embed(new_text),
        payload={"text": new_text, "tags": "", "updated_ts": time.time(), "device_id": REMOTE_DEVICE_ID})])
    db.log("simulate", f"[SIMULATION] {REMOTE_DEVICE_ID} edited #{mid} on the cloud")
