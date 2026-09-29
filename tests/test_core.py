import socket

from qdrant_client import QdrantClient
import db
import memory
import sync

db.init()


def test_add_and_search_work_with_network_blocked(monkeypatch):
    def blocked(*a, **k):
        raise OSError("network is blocked in this test")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    memory.add("Pump 3 makes a grinding noise at startup")
    memory.add("Forklift battery drains within three hours")
    results, ms = memory.search("grinding noise pump", limit=2)
    assert results[0]["text"].startswith("Pump 3")


def test_sensitive_text_stays_local_only():
    mid = memory.add("The wifi password is hunter2")
    row = db.get(mid)
    assert row["local_only"] == 1 and row["sync_state"] == "local_only"


def test_memory_survives_restart():
    memory.add("Unique restart survivor note about compressor filters")
    memory.close()                                  # simulate app restart
    results, _ = memory.search("compressor filters", limit=1)
    assert "restart survivor" in results[0]["text"]


def test_delete_removes_from_search():
    mid = memory.add("Temporary zebra note to delete")
    memory.delete(mid)
    results, _ = memory.search("zebra", limit=5)
    assert all(r["id"] != mid for r in results)


def test_sync_push_pull_and_conflict():
    cloud = QdrantClient(":memory:")
    sync.set_client_factory(lambda: cloud)

    # offline: nothing leaves the device
    r = sync.sync_now(simulate_offline=True)
    assert r["pushed"] == 0

    # online push: only non-local-only pending items go up
    before = db.count_pending()
    assert before > 0
    r = sync.sync_now()
    assert r["pushed"] + r["deleted"] == before and db.count_pending() == 0
    cloud_ids = {p.id for p in cloud.scroll("memories", limit=500)[0]}
    assert not any(row["id"] in cloud_ids for row in db.all_memories() if row["local_only"])

    # pull a note created on another device
    new_id = sync.simulate_remote_new("Air dryer drain valve is clogged")
    r = sync.sync_now()
    assert r["pulled_new"] == 1 and db.get(new_id)["sync_state"] == "synced"
    results, _ = memory.search("clogged drain valve", limit=1)
    assert results[0]["id"] == new_id

    # conflict: edit locally, other device edits same memory, remote is newer -> remote wins
    mid = db.all_memories()[0]["id"] if not db.all_memories()[0]["local_only"] else [m for m in db.all_memories() if not m["local_only"]][0]["id"]
    memory.edit(mid, "LOCAL edit of this note")
    sync.simulate_remote_edit(mid, "REMOTE edit of this note")
    r = sync.sync_now()
    assert r["conflicts"] == 1
    assert db.get(mid)["text"] == "REMOTE edit of this note"
    assert any(a["kind"] == "conflict" for a in db.activity())

    # delete propagates
    memory.delete(new_id)
    sync.sync_now()
    assert new_id not in {p.id for p in cloud.scroll("memories", limit=500)[0]}
