"""Load and resolve dashboard configuration."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULTS = {
    "queue_fixture": "fixtures/queue.json",
    "inventory_db": "fixtures/inventory.db",
    "output_dir": "output",
    "keep_snapshots_days": 14,
    "error_window_hours": 24,
    "stale_scan_hours": 26,
    "error_burst_count": 5,
    "standards": {"driver_version": "", "plugins": {}},
}


def load_config(path: str | Path | None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    if not path:
        cfg["_root"] = Path.cwd()
        return cfg
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a JSON object: {config_path}")
    cfg.update(raw)
    standards = dict(DEFAULTS["standards"])
    standards.update(raw.get("standards") or {})
    if "plugins" not in standards or standards["plugins"] is None:
        standards["plugins"] = {}
    cfg["standards"] = standards
    cfg["_root"] = config_path.parent
    return cfg


def resolve_path(cfg: dict, key: str) -> Path:
    value = Path(cfg[key])
    if value.is_absolute():
        return value
    return (cfg["_root"] / value).resolve()
