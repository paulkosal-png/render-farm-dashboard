"""Command-line entry: collect, analyze, and write the dashboard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from farmdash import analyze, inventory_source, queue_source, report_html
from farmdash.analyze import SEVERITY_NAMES, WARNING
from farmdash.config import load_config, resolve_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _prune_snapshots(folder: Path, days: int, now: datetime) -> None:
    cutoff = (now - timedelta(days=days)).timestamp()
    if not folder.is_dir():
        return
    for path in folder.glob("snapshot-*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink()


def build_report(cfg: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    queue = queue_source.load_queue(resolve_path(cfg, "queue_fixture"), now=now)
    inventory = inventory_source.load_inventory(resolve_path(cfg, "inventory_db"))
    nodes, standards = analyze.build_nodes(queue, inventory, cfg, now)
    jobs = analyze.build_jobs(queue.get("jobs") or [], nodes)
    summary = analyze.summarize(nodes, jobs, standards, float(cfg.get("error_window_hours", 24)))
    meta = {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "error_window_hours": cfg.get("error_window_hours", 24),
        "inventory_machines": len(inventory),
        "queue_workers": len(queue.get("workers") or []),
        "synthetic": True,
    }
    return {
        "nodes": nodes,
        "jobs": jobs,
        "standards": standards,
        "summary": summary,
        "meta": meta,
    }


def _print_summary(report: dict) -> None:
    meta, summary = report["meta"], report["summary"]
    print(
        "Inventory: %s machines | Queue: %s workers | nodes: %s | need attention: %s | "
        "errors %sh: %s | jobs: %s (%s active)"
        % (
            meta["inventory_machines"],
            meta["queue_workers"],
            summary["nodes"],
            summary["attention"],
            int(summary["error_window_hours"]),
            summary["errors"],
            summary["jobs_total"],
            summary["jobs_active"],
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="farmdash",
        description="Build a read-only render-farm dashboard from local fixtures.",
    )
    parser.add_argument("--config", help="Path to a JSON config file (see config.example.json).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read sources and print a summary without writing files.",
    )
    parser.add_argument("--out", help="Override output_dir from the config.")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.out:
        cfg["output_dir"] = args.out
    report = build_report(cfg)
    _print_summary(report)

    if args.check:
        for node in report["nodes"]:
            if node["severity"] >= WARNING:
                flag = node["flags"][0]["text"] if node["flags"] else ""
                print("  %-12s %-8s %s" % (node["name"], SEVERITY_NAMES[node["severity"]], flag))
        for job in report["jobs"]:
            if job["severity"] >= WARNING:
                print(
                    "  job %-20s %-8s %s"
                    % (job["name"], SEVERITY_NAMES[job["severity"]], job.get("issue") or "")
                )
        return 0

    out = resolve_path(cfg, "output_dir")
    snap_dir = out / "snapshots"
    page = report_html.render(
        report["nodes"],
        report["jobs"],
        report["summary"],
        report["meta"],
        report["standards"],
    )
    payload = {
        "meta": report["meta"],
        "summary": report["summary"],
        "nodes": report["nodes"],
        "jobs": report["jobs"],
        "standards": {
            "driver": report["standards"].get("driver"),
            "plugins": report["standards"].get("plugins"),
        },
    }
    text = json.dumps(payload, indent=2, default=str)
    now = datetime.now()
    _write(out / "index.html", page)
    _write(out / "latest.json", text)
    _write(snap_dir / now.strftime("snapshot-%Y%m%d-%H%M.json"), text)
    _prune_snapshots(snap_dir, int(cfg.get("keep_snapshots_days", 14)), now)
    print("Wrote", out / "index.html")
    return 0
