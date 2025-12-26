#!/usr/bin/env python3
"""
Build a per-session index from raw platform events using a 30-minute inactivity timeout.

Input index pattern:
  - platform-events-*
Required fields:
  - player_id (keyword)
  - @timestamp (date)

Output index:
  - player-sessions-000001 (alias: player-sessions)
Fields:
  - player_id (keyword)
  - session_id (keyword)
  - session_start (date)
  - session_end (date)
  - session_duration_seconds (long)
  - session_duration_minutes (float)
  - event_count (integer)

Sessionization rule:
  - Events grouped by player_id, ordered by @timestamp.
  - New session starts when gap between consecutive events > 30 minutes.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

import requests
from requests.auth import HTTPBasicAuth

ES_HOST = "http://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"

AUTH = HTTPBasicAuth(ES_USER, ES_PASS)
HEADERS = {"Content-Type": "application/json"}

SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 minutes
SESSIONS_INDEX_ALIAS = "player-sessions"
SESSIONS_INDEX_NAME = "player-sessions-000001"


def parse_timestamp(value: str) -> datetime:
    """Parse ISO8601 timestamp (with or without trailing 'Z')."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def ensure_sessions_index() -> None:
    """Create the sessions index with a fixed mapping if it does not exist."""
    resp = requests.get(f"{ES_HOST}/{SESSIONS_INDEX_NAME}", auth=AUTH)
    if resp.status_code == 200:
        print(f"✅ Sessions index already exists: {SESSIONS_INDEX_NAME}")
        return

    print(f"📊 Creating sessions index: {SESSIONS_INDEX_NAME}")
    mapping = {
        "mappings": {
            "properties": {
                "player_id": {"type": "keyword"},
                "session_id": {"type": "keyword"},
                "session_start": {"type": "date"},
                "session_end": {"type": "date"},
                "session_duration_seconds": {"type": "long"},
                "session_duration_minutes": {"type": "float"},
                "event_count": {"type": "integer"},
            }
        },
        "aliases": {
            SESSIONS_INDEX_ALIAS: {}
        },
    }

    create_resp = requests.put(
        f"{ES_HOST}/{SESSIONS_INDEX_NAME}", auth=AUTH, headers=HEADERS, data=json.dumps(mapping)
    )
    if create_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create sessions index: {create_resp.status_code} {create_resp.text}"
        )
    print("✅ Sessions index created")


def stream_events(batch_size: int = 1000):
    """Yield events from platform-events-* sorted by player_id, @timestamp."""
    search_body = {
        "size": batch_size,
        "sort": [
            {"player_id.keyword": "asc"},
            {"@timestamp": "asc"},
        ],
        "_source": ["player_id", "@timestamp"],
        "query": {"exists": {"field": "player_id"}},
    }

    print("🔍 Scanning platform-events-* for player_id + @timestamp ...")
    resp = requests.post(
        f"{ES_HOST}/platform-events-*/_search?scroll=2m",
        auth=AUTH,
        headers=HEADERS,
        data=json.dumps(search_body),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Initial search failed: {resp.status_code} {resp.text}")

    data = resp.json()
    scroll_id = data.get("_scroll_id")
    hits = data.get("hits", {}).get("hits", [])

    while hits:
        for hit in hits:
            src = hit.get("_source", {})
            player_id = src.get("player_id")
            ts = src.get("@timestamp")
            if not player_id or not ts:
                continue
            yield player_id, ts

        resp = requests.post(
            f"{ES_HOST}/_search/scroll",
            auth=AUTH,
            headers=HEADERS,
            data=json.dumps({"scroll": "2m", "scroll_id": scroll_id}),
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        scroll_id = data.get("_scroll_id")
        hits = data.get("hits", {}).get("hits", [])

    if scroll_id:
        try:
            requests.delete(
                f"{ES_HOST}/_search/scroll",
                auth=AUTH,
                headers=HEADERS,
                data=json.dumps({"scroll_id": [scroll_id]}),
            )
        except Exception:
            pass


def index_sessions_bulk(sessions: List[Dict[str, Any]]) -> None:
    if not sessions:
        return
    lines = []
    for s in sessions:
        lines.append(json.dumps({"index": {"_index": SESSIONS_INDEX_NAME, "_id": s["session_id"]}}))
        lines.append(json.dumps(s))
    body = "\n".join(lines) + "\n"
    resp = requests.post(f"{ES_HOST}/_bulk", auth=AUTH, headers=HEADERS, data=body)
    if resp.status_code != 200:
        raise RuntimeError(f"Bulk index failed: {resp.status_code} {resp.text}")
    rj = resp.json()
    if rj.get("errors"):
        raise RuntimeError(f"Bulk index reported errors: {resp.text}")


def build_sessions() -> None:
    ensure_sessions_index()

    current_player = None
    current_start: datetime | None = None
    current_end: datetime | None = None
    last_ts: datetime | None = None
    event_count = 0

    sessions_buffer: List[Dict[str, Any]] = []
    total_events = 0
    total_sessions = 0

    for player_id, ts_str in stream_events():
        total_events += 1
        ts = parse_timestamp(ts_str)

        if current_player is None:
            # first event overall
            current_player = player_id
            current_start = current_end = ts
            last_ts = ts
            event_count = 1
            continue

        if player_id != current_player:
            # flush previous player's last session
            if current_start is not None and current_end is not None:
                duration_sec = int((current_end - current_start).total_seconds())
                if duration_sec < 0:
                    duration_sec = 0
                session_doc = {
                    "player_id": current_player,
                    "session_id": str(uuid.uuid4()),
                    "session_start": current_start.isoformat().replace("+00:00", "Z"),
                    "session_end": current_end.isoformat().replace("+00:00", "Z"),
                    "session_duration_seconds": duration_sec,
                    "session_duration_minutes": duration_sec / 60.0,
                    "event_count": event_count,
                }
                sessions_buffer.append(session_doc)
                total_sessions += 1

            # start new player's first session
            current_player = player_id
            current_start = current_end = ts
            last_ts = ts
            event_count = 1
        else:
            # same player, decide if same session or new session
            gap = (ts - last_ts).total_seconds() if last_ts is not None else 0
            if gap > SESSION_TIMEOUT_SECONDS:
                # flush previous session
                if current_start is not None and current_end is not None:
                    duration_sec = int((current_end - current_start).total_seconds())
                    if duration_sec < 0:
                        duration_sec = 0
                    session_doc = {
                        "player_id": current_player,
                        "session_id": str(uuid.uuid4()),
                        "session_start": current_start.isoformat().replace("+00:00", "Z"),
                        "session_end": current_end.isoformat().replace("+00:00", "Z"),
                        "session_duration_seconds": duration_sec,
                        "session_duration_minutes": duration_sec / 60.0,
                        "event_count": event_count,
                    }
                    sessions_buffer.append(session_doc)
                    total_sessions += 1

                # start new session
                current_start = current_end = ts
                event_count = 1
            else:
                # extend current session
                current_end = ts
                event_count += 1
            last_ts = ts

        if len(sessions_buffer) >= 1000:
            index_sessions_bulk(sessions_buffer)
            sessions_buffer.clear()
            print(f"  ⏩ Indexed {total_sessions} sessions from {total_events} events so far...")

    # flush last session after loop
    if current_player is not None and current_start is not None and current_end is not None:
        duration_sec = int((current_end - current_start).total_seconds())
        if duration_sec < 0:
            duration_sec = 0
        session_doc = {
            "player_id": current_player,
            "session_id": str(uuid.uuid4()),
            "session_start": current_start.isoformat().replace("+00:00", "Z"),
            "session_end": current_end.isoformat().replace("+00:00", "Z"),
            "session_duration_seconds": duration_sec,
            "session_duration_minutes": duration_sec / 60.0,
            "event_count": event_count,
        }
        sessions_buffer.append(session_doc)
        total_sessions += 1

    if sessions_buffer:
        index_sessions_bulk(sessions_buffer)

    print("\n✅ Sessionization complete")
    print(f"   Events processed : {total_events}")
    print(f"   Sessions created : {total_sessions}")


def main() -> None:
    print("=" * 80)
    print("🎯 Building player sessions index (30 min timeout)")
    print("=" * 80)
    build_sessions()


if __name__ == "__main__":
    main()
