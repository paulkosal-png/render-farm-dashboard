#!/usr/bin/env python3
"""Build the demo SQLite inventory database from fixtures/inventory_seed.json."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "fixtures" / "inventory_seed.json"
DEFAULT_DB = ROOT / "fixtures" / "inventory.db"

SCHEMA = """
DROP TABLE IF EXISTS plugins;
DROP TABLE IF EXISTS gpus;
DROP TABLE IF EXISTS machines;

CREATE TABLE machines (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    os_name TEXT,
    last_scan TEXT,
    ram_gb INTEGER
);
CREATE TABLE gpus (
    id INTEGER PRIMARY KEY,
    machine_id INTEGER NOT NULL REFERENCES machines(id),
    model TEXT,
    driver_version TEXT,
    vram_mb INTEGER
);
CREATE TABLE plugins (
    id INTEGER PRIMARY KEY,
    machine_id INTEGER NOT NULL REFERENCES machines(id),
    app_name TEXT,
    app_version TEXT,
    plugin_name TEXT,
    plugin_version TEXT
);
"""


def last_scan_value(machine: dict, now: datetime) -> str | None:
    if machine.get("last_scan_hours_ago") is not None:
        stamp = now - timedelta(hours=float(machine["last_scan_hours_ago"]))
        return stamp.replace(microsecond=0).isoformat()
    return machine.get("last_scan")


def build(seed_path: Path, db_path: Path, now: datetime | None = None) -> int:
    now = now or datetime.now()
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        count = 0
        for machine in seed.get("machines", []):
            cur = con.execute(
                "INSERT INTO machines (name, os_name, last_scan, ram_gb) VALUES (?, ?, ?, ?)",
                (
                    machine["name"],
                    machine.get("os_name"),
                    last_scan_value(machine, now),
                    machine.get("ram_gb"),
                ),
            )
            machine_id = cur.lastrowid
            count += 1
            for gpu in machine.get("gpus") or []:
                con.execute(
                    "INSERT INTO gpus (machine_id, model, driver_version, vram_mb)"
                    " VALUES (?, ?, ?, ?)",
                    (machine_id, gpu.get("model"), gpu.get("driver_version"), gpu.get("vram_mb")),
                )
            for plugin in machine.get("plugins") or []:
                con.execute(
                    """INSERT INTO plugins
                       (machine_id, app_name, app_version, plugin_name, plugin_version)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        plugin.get("app_name"),
                        plugin.get("app_version"),
                        plugin.get("plugin_name"),
                        plugin.get("plugin_version"),
                    ),
                )
        con.commit()
    finally:
        con.close()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    count = build(args.seed, args.db)
    print(f"Wrote {count} machines to {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
