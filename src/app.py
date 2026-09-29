from datetime import datetime

import db
import memory
import sync
import seed
import pandas as pd
import streamlit as st

def app():

    st.set_page_config(page_title="Edge Mind", page_icon="🧠", layout="wide")
    db.init()
    memory.shard()          # open the shard once at startup

    BADGE = {"synced": "✅ synced", "pending": "🕓 pending sync", "local_only": "🔒 local only"}
    fmt = lambda ts: datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S") if ts else "never"

    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)

    # ---------------------------------------------------------------- sidebar
    with st.sidebar:
        st.title("🧠 Edge Mind")
        sim = st.toggle("Simulate offline", key="sim_offline",
                        help="Forces the app to behave as if there's no internet.")
        online = sync.is_online(sim)
        st.markdown("**Status:** " + ("🟢 Online" if online else "🔴 Offline"))
        if not sync.configured():
            st.warning("No cloud credentials in .env — running local-only.")
        st.metric("Pending sync", db.count_pending())
        st.caption(f"Last sync: {fmt(float(db.get_meta('last_sync_ts', 0)))}")

        if st.button("🔄 Sync Now", type="primary", use_container_width=True):
            r = sync.sync_now(sim)
            if r["error"]:
                st.session_state["flash"] = ("error", r["error"])
            elif not r["online"]:
                detail = sync.last_online_error()
                msg = "Offline — nothing synced. Changes stay queued on this device."
                if detail:
                    msg += f"\n\n`{detail}`"
                st.session_state["flash"] = ("warning", msg)
            else:
                st.session_state["flash"] = ("success",
                    f"Synced: pushed {r['pushed']}, pulled {r['pulled_new'] + r['pulled_updates']}, "
                    f"conflicts {r['conflicts']}")
            st.rerun()

        with st.expander("🧪 Demo tools"):
            if st.button("Load sample notes"):
                st.session_state["flash"] = ("success", f"Added {seed.load()} sample notes")
                st.rerun()
            st.caption("Pretend to be a second device. Writes straight to the cloud (needs real internet).")
            rt = st.text_input("Other device adds a note", key="rt")
            if st.button("Add from other device") and rt:
                try:
                    sync.simulate_remote_new(rt)
                    st.session_state["flash"] = ("success", "Other device added a note on the cloud. Now click Sync Now.")
                except Exception as e:
                    st.session_state["flash"] = ("error", f"Needs internet + cloud credentials: {e}")
                st.rerun()
            eid = st.number_input("Other device edits memory #", min_value=1, step=1, key="eid")
            et = st.text_input("…to this text", key="et")
            if st.button("Edit from other device") and et:
                try:
                    sync.simulate_remote_edit(int(eid), et)
                    st.session_state["flash"] = ("success", f"Other device edited #{int(eid)} on the cloud.")
                except Exception as e:
                    st.session_state["flash"] = ("error", f"Needs internet + cloud credentials: {e}")
                st.rerun()

    # ---------------------------------------------------------------- tabs
    t_search, t_add, t_inspect, t_log = st.tabs(["🔎 Search", "➕ Add memory", "🗂 Inspector", "📜 Activity"])

    with t_search:
        q = st.text_input("Search by meaning", placeholder="e.g. why is the machine so noisy?")
        if q:
            results, ms = memory.search(q, limit=5)
            st.caption(f"⚡ {len(results)} results in {ms:.0f} ms — computed on this device, no network used")
            for r in results:
                with st.container(border=True):
                    st.markdown(f"**{r['text']}**")
                    st.caption(f"#{r['id']} · similarity {r['score']:.2f} · {BADGE[r['sync_state']]}"
                            + (f" · tags: {r['tags']}" if r["tags"] else ""))

    with t_add:
        with st.form("add", clear_on_submit=True):
            text = st.text_area("What should the device remember?")
            tags = st.text_input("Tags (optional)")
            local = st.checkbox("Keep on this device only (never sync)")
            if st.form_submit_button("Save to on-device memory") and text.strip():
                mid = memory.add(text.strip(), tags.strip(), local)
                row = db.get(mid)
                note = f"Saved #{mid}. " + (f"🔒 Local only — {row['reason']}." if row["local_only"] else "Queued for sync.")
                st.session_state["flash"] = ("success", note)
                st.rerun()

    with t_inspect:
        rows = db.all_memories()
        st.caption(f"{len(rows)} memories on this device")
        if rows:
            st.dataframe(pd.DataFrame([{
                "id": r["id"], "text": r["text"], "tags": r["tags"], "state": BADGE[r["sync_state"]],
                "why local-only": r["reason"], "device": r["device_id"], "updated": fmt(r["updated_ts"])}
                for r in rows]), hide_index=True)
            with st.expander("Edit or delete a memory"):
                sel = st.selectbox("Memory #", [r["id"] for r in rows])
                cur = db.get(sel)
                new_text = st.text_area("Text", value=cur["text"], key=f"edit_{sel}")
                c1, c2 = st.columns(2)
                if c1.button("Save changes") and new_text.strip():
                    memory.edit(sel, new_text.strip(), cur["tags"])
                    st.session_state["flash"] = ("success", f"Updated #{sel}")
                    st.rerun()
                if c2.button("Delete"):
                    memory.delete(sel)
                    st.session_state["flash"] = ("success", f"Deleted #{sel}")
                    st.rerun()

    with t_log:
        st.dataframe(pd.DataFrame([{"time": fmt(a["ts"]), "event": a["kind"], "details": a["details"]}
                                for a in db.activity(100)]), hide_index=True)
