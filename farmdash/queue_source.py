"""Load a render-queue snapshot from a JSON fixture.

Timestamps in the fixture can be written as hours_ago (relative to a clock
you pass in) so the demo stays current every time it is run.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def _when(item: dict, field: str, now: datetime) -> str | None:
    relative_key = f"{field}_hours_ago"
    if relative_key in item and item[relative_key] is not None:
        delta = timedelta(hours=float(item[relative_key]))
        return (now - delta).replace(microsecond=0).isoformat()
    value = item.get(field)
    return str(value) if value else None


def load_queue(path: str | Path, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    workers = []
    for raw in payload.get("workers", []):
        errors = []
        for err in raw.get("errors", []):
            errors.append(
                {
                    "time": _when(err, "time", now),
                    "message": err.get("message") or "",
                    "job": err.get("job") or "",
                }
            )
        workers.append(
            {
                "name": raw["name"],
                "state": (raw.get("state") or "idle").lower(),
                "state_changed": _when(raw, "state_changed", now),
                "groups": list(raw.get("groups") or []),
                "pools": list(raw.get("pools") or []),
                "errors": errors,
            }
        )
    jobs = []
    for raw in payload.get("jobs", []):
        jobs.append(
            {
                "id": raw.get("id") or raw["name"],
                "name": raw["name"],
                "user": raw.get("user") or "",
                "submitted": _when(raw, "submitted", now),
                "status": (raw.get("status") or "queued").lower(),
                "plugin": raw.get("plugin") or "",
                "plugin_version": raw.get("plugin_version") or "",
                "renderer": raw.get("renderer") or "",
                "renderer_version": raw.get("renderer_version") or "",
                "group": raw.get("group") or "",
                "pool": raw.get("pool") or "",
                "frames_total": int(raw.get("frames_total") or 0),
                "frames_done": int(raw.get("frames_done") or 0),
            }
        )
    return {"workers": workers, "jobs": jobs}
