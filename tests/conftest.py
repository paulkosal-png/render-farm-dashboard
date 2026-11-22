from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.build_inventory_db import build

NOW = datetime(2026, 11, 21, 15, 0, 0)


def _machine(name, driver="566.14", plugin="3.9.0", hours_ago=1):
    return {
        "name": name,
        "os_name": "Test OS",
        "last_scan_hours_ago": hours_ago,
        "ram_gb": 64,
        "gpus": [{"model": "Example GPU", "driver_version": driver, "vram_mb": 16384}],
        "plugins": [
            {
                "app_name": "SceneApp",
                "app_version": "2026.1",
                "plugin_name": "LightTrace",
                "plugin_version": plugin,
            }
        ],
    }


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def inventory_db(tmp_path: Path, now: datetime) -> Path:
    seed = {
        "machines": [
            _machine("farm-01"),
            _machine("farm-02"),
            _machine("farm-03", hours_ago=40),
            _machine("farm-04", driver="551.86"),
            _machine("farm-05", plugin="3.8.2"),
            _machine("artist-01", driver="551.86"),
        ]
    }
    seed_path = tmp_path / "seed.json"
    db_path = tmp_path / "inventory.db"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    build(seed_path, db_path, now=now)
    return db_path
