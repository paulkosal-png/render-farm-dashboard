"""Read machine inventory from a local SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_NOTE = "machines, gpus, and plugins tables built by scripts/build_inventory_db.py"


def load_inventory(path: str | Path) -> dict[str, dict]:
    db_path = Path(path)
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Inventory database not found: {db_path}. "
            "Build it first with: python scripts/build_inventory_db.py"
        )
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        machines = {}
        for row in con.execute(
            "SELECT id, name, os_name, last_scan, ram_gb FROM machines ORDER BY name"
        ):
            machines[row["id"]] = {
                "name": row["name"],
                "os_name": row["os_name"],
                "last_scan": row["last_scan"],
                "ram_gb": row["ram_gb"],
                "gpus": [],
                "plugins": [],
            }
        for row in con.execute(
            "SELECT machine_id, model, driver_version, vram_mb FROM gpus ORDER BY id"
        ):
            node = machines.get(row["machine_id"])
            if node is not None:
                node["gpus"].append(
                    {
                        "model": row["model"],
                        "driver_version": row["driver_version"],
                        "vram_mb": row["vram_mb"],
                    }
                )
        for row in con.execute(
            """SELECT machine_id, app_name, app_version, plugin_name, plugin_version
               FROM plugins ORDER BY id"""
        ):
            node = machines.get(row["machine_id"])
            if node is not None:
                node["plugins"].append(
                    {
                        "app_name": row["app_name"],
                        "app_version": row["app_version"],
                        "plugin_name": row["plugin_name"],
                        "plugin_version": row["plugin_version"],
                    }
                )
        return {node["name"].upper(): node for node in machines.values()}
    finally:
        con.close()
