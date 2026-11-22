"""Merge queue and inventory, assign severity flags, and score job readiness."""

from __future__ import annotations

import collections
import re
from datetime import datetime, timedelta

OK, INFO, WARNING, SERIOUS, CRITICAL = range(5)
SEVERITY_NAMES = {
    OK: "ok",
    INFO: "info",
    WARNING: "warning",
    SERIOUS: "serious",
    CRITICAL: "critical",
}

UNAVAILABLE_STATES = frozenset({"offline", "stalled"})

_CATEGORIES = (
    ("vram", re.compile(r"vram|video memory|gpu memory|out of (?:gpu|device) memory", re.I)),
    ("license", re.compile(r"licen[cs]e", re.I)),
    ("crash", re.compile(r"crash|fatal exception|access violation|segmentation fault", re.I)),
    (
        "missing path",
        re.compile(
            r"missing path|path could not|cannot find (?:the )?path|no such file|output path",
            re.I,
        ),
    ),
)


def categorize(message: str) -> str:
    text = message or ""
    for name, pattern in _CATEGORIES:
        if pattern.search(text):
            return name
    return "other"


def version_key(value: str) -> tuple:
    parts = []
    for chunk in re.split(r"[^\d]+", str(value)):
        if chunk:
            parts.append(int(chunk))
    return tuple(parts) if parts else (0,)


def most_common(values: list[str]) -> str | None:
    """Return the most frequent value. Ties go to the higher version-like sort."""
    counted = collections.Counter(v for v in values if v)
    if not counted:
        return None
    top = max(counted.values())
    tied = [value for value, count in counted.items() if count == top]
    return max(tied, key=version_key)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    try:
        return datetime.fromisoformat(text[:19])
    except ValueError:
        return None


def compute_standards(inventory: dict, worker_names: list[str], config: dict) -> dict:
    cfg = (config.get("standards") or {}) if config else {}
    configured_driver = (cfg.get("driver_version") or "").strip()
    configured_plugins = {k: (v or "").strip() for k, v in (cfg.get("plugins") or {}).items()}

    drivers = []
    plugins: dict[str, list[str]] = collections.defaultdict(list)
    wanted = {name.upper() for name in worker_names}
    for key, node in inventory.items():
        if wanted and key not in wanted:
            continue
        for gpu in node.get("gpus") or []:
            if gpu.get("driver_version"):
                drivers.append(gpu["driver_version"])
        for plugin in node.get("plugins") or []:
            name = plugin.get("plugin_name") or ""
            version = plugin.get("plugin_version") or ""
            if name and version:
                plugins[name].append(version)

    plugin_standards = {}
    for name, versions in plugins.items():
        plugin_standards[name] = configured_plugins.get(name) or most_common(versions)
    for name, version in configured_plugins.items():
        if version:
            plugin_standards.setdefault(name, version)

    return {
        "driver": configured_driver or most_common(drivers),
        "driver_configured": bool(configured_driver),
        "plugins": plugin_standards,
        "plugins_configured": {name: bool(ver) for name, ver in configured_plugins.items()},
    }


def _flag(flags: list, severity: int, text: str) -> None:
    flags.append({"severity": severity, "text": text})


def _ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return ""
    delta = now - moment
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def build_nodes(queue: dict, inventory: dict, config: dict, now: datetime | None = None) -> tuple:
    now = now or datetime.now()
    window_h = float(config.get("error_window_hours", 24))
    stale_h = float(config.get("stale_scan_hours", 26))
    burst = int(config.get("error_burst_count", 5))
    names = [w["name"] for w in queue.get("workers", [])]
    standards = compute_standards(inventory, names, config)
    since = now - timedelta(hours=window_h)

    nodes = []
    for worker in queue.get("workers", []):
        key = worker["name"].upper()
        inv = inventory.get(key)
        flags: list[dict] = []
        state = worker.get("state") or "unknown"
        changed = _ago(parse_time(worker.get("state_changed")), now)

        if state == "stalled":
            _flag(flags, CRITICAL, f"Worker stalled{(' ' + changed) if changed else ''}")
        elif state == "offline":
            _flag(flags, WARNING, f"Worker offline{(' ' + changed) if changed else ''}")

        recent = []
        for err in worker.get("errors") or []:
            stamped = parse_time(err.get("time"))
            if stamped is None or stamped >= since:
                item = dict(err)
                item["category"] = categorize(err.get("message") or "")
                recent.append(item)
        if recent:
            counts = collections.Counter(item["category"] for item in recent)
            summary = ", ".join(f"{name} x{count}" for name, count in counts.most_common())
            level = SERIOUS if len(recent) >= burst else WARNING
            _flag(
                flags,
                level,
                f"{len(recent)} error{'s' if len(recent) != 1 else ''}"
                f" in {int(window_h)}h ({summary})",
            )

        drivers = []
        plugins = []
        last_scan = None
        if inv is None:
            _flag(flags, WARNING, "Not in inventory")
        else:
            last_scan = parse_time(inv.get("last_scan"))
            if last_scan is None:
                _flag(flags, WARNING, "Inventory has never been scanned")
            elif (now - last_scan).total_seconds() > stale_h * 3600:
                _flag(flags, WARNING, f"Inventory is stale ({_ago(last_scan, now)})")
            drivers = [
                gpu.get("driver_version")
                for gpu in inv.get("gpus") or []
                if gpu.get("driver_version")
            ]
            plugins = list(inv.get("plugins") or [])
            standard_driver = standards["driver"]
            if standard_driver and any(drv != standard_driver for drv in drivers):
                level = WARNING if standards["driver_configured"] else INFO
                _flag(
                    flags,
                    level,
                    "GPU driver %s (farm standard %s)"
                    % (", ".join(sorted(set(drivers))), standard_driver),
                )
            for plugin in plugins:
                name = plugin.get("plugin_name") or ""
                version = plugin.get("plugin_version") or ""
                expected = (standards.get("plugins") or {}).get(name)
                if name and version and expected and version != expected:
                    configured = (standards.get("plugins_configured") or {}).get(name)
                    level = WARNING if configured else INFO
                    _flag(
                        flags,
                        level,
                        f"{name} {version} (farm standard {expected})",
                    )

        severity = max((flag["severity"] for flag in flags), default=OK)
        nodes.append(
            {
                "name": worker["name"],
                "state": state,
                "state_changed": worker.get("state_changed"),
                "groups": list(worker.get("groups") or []),
                "pools": list(worker.get("pools") or []),
                "flags": flags,
                "severity": severity,
                "errors_recent": recent,
                "drivers": drivers,
                "plugins": plugins,
                "last_scan": inv.get("last_scan") if inv else None,
                "os_name": inv.get("os_name") if inv else None,
                "gpus": list(inv.get("gpus") or []) if inv else [],
            }
        )
    return nodes, standards


def worker_is_ready(node: dict, job: dict) -> tuple[bool, bool]:
    """Return (is_candidate, is_ready) for a job against one worker node."""
    group = job.get("group") or ""
    pool = job.get("pool") or ""
    in_group = (not group) or group in (node.get("groups") or [])
    in_pool = (not pool) or pool in (node.get("pools") or [])
    candidate = in_group and in_pool
    if not candidate:
        return False, False
    if node.get("state") in UNAVAILABLE_STATES:
        return True, False
    required_name = job.get("renderer") or job.get("plugin") or ""
    required_version = job.get("renderer_version") or job.get("plugin_version") or ""
    if required_name and required_version:
        versions = [
            plugin.get("plugin_version")
            for plugin in node.get("plugins") or []
            if plugin.get("plugin_name") == required_name
        ]
        if required_version not in versions:
            return True, False
    return True, True


def build_jobs(raw_jobs: list, nodes: list[dict]) -> list[dict]:
    built = []
    for job in raw_jobs:
        candidates = 0
        ready = 0
        for node in nodes:
            is_candidate, is_ready = worker_is_ready(node, job)
            if is_candidate:
                candidates += 1
            if is_ready:
                ready += 1
        flags = []
        status = (job.get("status") or "").lower()
        active = status in {"active", "rendering", "queued", "pending"}
        if candidates == 0:
            _flag(flags, WARNING, "No workers in this job's group and pool")
        elif ready == 0:
            _flag(flags, WARNING, "Candidates exist but none have the required plugin version")
        severity = max((flag["severity"] for flag in flags), default=OK)
        built.append(
            {
                **job,
                "active": active,
                "candidates": candidates,
                "ready": ready,
                "flags": flags,
                "severity": severity,
                "issue": flags[0]["text"] if flags else "",
            }
        )
    return built


def summarize(nodes: list[dict], jobs: list[dict], standards: dict, window_h: float) -> dict:
    states = collections.Counter(node["state"] for node in nodes)
    categories = collections.Counter()
    error_count = 0
    for node in nodes:
        error_count += len(node.get("errors_recent") or [])
        for err in node.get("errors_recent") or []:
            categories[err["category"]] += 1
    drivers = collections.Counter()
    for node in nodes:
        for drv in set(node.get("drivers") or []):
            drivers[drv] += 1
    return {
        "nodes": len(nodes),
        "attention": sum(1 for node in nodes if node["severity"] >= WARNING),
        "critical": sum(1 for node in nodes if node["severity"] >= CRITICAL),
        "states": dict(states),
        "errors": error_count,
        "error_window_hours": window_h,
        "error_categories": categories.most_common(),
        "drivers": drivers.most_common(),
        "jobs_total": len(jobs),
        "jobs_active": sum(1 for job in jobs if job.get("active")),
        "jobs_flagged": sum(1 for job in jobs if job["severity"] >= WARNING),
        "standards": {
            "driver": standards.get("driver"),
            "plugins": dict(standards.get("plugins") or {}),
        },
    }
