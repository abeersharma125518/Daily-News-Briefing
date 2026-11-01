import json
import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

STATE_FILE = "state.json"
STATE_TTL_DAYS = 14


def load_state(filepath: str = STATE_FILE) -> dict:
    if not os.path.exists(filepath):
        return {"sent_guids": []}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=STATE_TTL_DAYS)).timestamp()
        data["sent_guids"] = [
            entry for entry in data.get("sent_guids", [])
            if entry.get("timestamp", 0) > cutoff
        ]
        return data
    except Exception as e:
        logger.warning("Failed to load state: %s", e)
        return {"sent_guids": []}


def save_state(state: dict, filepath: str = STATE_FILE):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save state: %s", e)


def filter_new_articles(articles: list, state: dict) -> list:
    sent_guids = set(entry["guid"] for entry in state.get("sent_guids", []))
    return [a for a in articles if a.guid not in sent_guids]


def mark_sent(articles: list, state: dict):
    now_ts = datetime.now(timezone.utc).timestamp()
    sent_set = set(entry["guid"] for entry in state.get("sent_guids", []))
    for a in articles:
        if a.guid not in sent_set:
            state["sent_guids"].append({
                "guid": a.guid,
                "title": a.title,
                "source": a.source_name,
                "timestamp": now_ts,
            })
