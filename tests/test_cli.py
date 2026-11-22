import json
from pathlib import Path

import pytest

from farmdash.cli import main
from farmdash.config import load_config
from scripts.build_inventory_db import DEFAULT_SEED, build

ROOT = Path(__file__).resolve().parents[1]


def _write_config(tmp_path: Path, db_path: Path, out_dir: Path) -> Path:
    cfg = {
        "queue_fixture": str(ROOT / "fixtures" / "queue.json"),
        "inventory_db": str(db_path),
        "output_dir": str(out_dir),
        "keep_snapshots_days": 14,
        "error_window_hours": 24,
        "stale_scan_hours": 26,
        "error_burst_count": 5,
        "standards": {"driver_version": "", "plugins": {"LightTrace": ""}},
    }
    path = tmp_path / "config.example.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


@pytest.fixture
def demo_config(tmp_path, now):
    db_path = tmp_path / "inventory.db"
    build(DEFAULT_SEED, db_path, now=now)
    out_dir = tmp_path / "output"
    return _write_config(tmp_path, db_path, out_dir)


def test_check_prints_summary_and_writes_nothing(demo_config, capsys, tmp_path):
    out_dir = tmp_path / "output"
    code = main(["--config", str(demo_config), "--check"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Inventory: 14 machines" in captured
    assert "Queue: 12 workers" in captured
    assert "need attention:" in captured
    assert not out_dir.exists()


def test_cli_writes_html_json_and_snapshot(demo_config, capsys, tmp_path):
    out_dir = tmp_path / "output"
    code = main(["--config", str(demo_config)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Wrote" in captured
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    latest = json.loads((out_dir / "latest.json").read_text(encoding="utf-8"))
    snapshots = list((out_dir / "snapshots").glob("snapshot-*.json"))
    assert "<!DOCTYPE html>" in html
    assert "farm-01" in html
    assert "demo_spot_A" in html
    assert "synthetic" in html.lower() or latest["meta"]["synthetic"] is True
    assert latest["summary"]["nodes"] == 12
    assert latest["summary"]["jobs_total"] == 5
    assert len(snapshots) == 1
    assert "function apply()" in html  # filters shipped inline


def test_out_flag_overrides_config_directory(demo_config, tmp_path):
    custom = tmp_path / "elsewhere"
    code = main(["--config", str(demo_config), "--out", str(custom)])
    assert code == 0
    assert (custom / "index.html").is_file()
    assert not (tmp_path / "output" / "index.html").exists()


def test_missing_config_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/tmp/does-not-exist-farmdash.json")
