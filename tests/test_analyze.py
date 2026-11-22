from farmdash.analyze import (
    CRITICAL,
    INFO,
    SERIOUS,
    WARNING,
    build_nodes,
    categorize,
    summarize,
)


def _worker(name, state="idle", errors=(), groups=None, pools=None, hours=1):
    return {
        "name": name,
        "state": state,
        "state_changed": "2026-11-21T14:00:00",
        "groups": groups or ["render"],
        "pools": pools or ["general"],
        "errors": list(errors),
    }


def _inv(name, driver="566.14", plugin="3.9.0", last_scan="2026-11-21T14:00:00"):
    return {
        name.upper(): {
            "name": name,
            "os_name": "Test OS",
            "last_scan": last_scan,
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
    }


def _config(**extra):
    cfg = {
        "error_window_hours": 24,
        "stale_scan_hours": 26,
        "error_burst_count": 5,
        "standards": {},
    }
    cfg.update(extra)
    return cfg


def test_stalled_worker_is_critical(now):
    queue = {"workers": [_worker("farm-01", "stalled")], "jobs": []}
    nodes, _ = build_nodes(queue, _inv("farm-01"), _config(), now)
    assert nodes[0]["severity"] == CRITICAL
    assert any("stalled" in flag["text"].lower() for flag in nodes[0]["flags"])


def test_offline_worker_is_a_warning(now):
    queue = {"workers": [_worker("farm-01", "offline")], "jobs": []}
    nodes, _ = build_nodes(queue, _inv("farm-01"), _config(), now)
    assert nodes[0]["severity"] == WARNING


def test_error_burst_is_serious(now):
    errors = [
        {
            "time": "2026-11-21T14:0%s:00" % i,
            "message": "LightTrace ran out of VRAM",
            "job": "demo_spot_A",
        }
        for i in range(5)
    ]
    queue = {"workers": [_worker("farm-01", errors=errors)], "jobs": []}
    nodes, _ = build_nodes(queue, _inv("farm-01"), _config(), now)
    assert nodes[0]["severity"] == SERIOUS
    assert len(nodes[0]["errors_recent"]) == 5
    assert all(err["category"] == "vram" for err in nodes[0]["errors_recent"])


def test_old_errors_are_ignored(now):
    errors = [
        {"time": "2026-11-19T12:00:00", "message": "LightTrace ran out of VRAM", "job": "old"}
    ]
    queue = {"workers": [_worker("farm-01", errors=errors)], "jobs": []}
    nodes, _ = build_nodes(queue, _inv("farm-01"), _config(), now)
    assert nodes[0]["errors_recent"] == []
    assert nodes[0]["severity"] == 0


def test_stale_inventory_is_a_warning(now):
    queue = {"workers": [_worker("farm-01")], "jobs": []}
    nodes, _ = build_nodes(queue, _inv("farm-01", last_scan="2026-11-19T12:00:00"), _config(), now)
    assert nodes[0]["severity"] == WARNING
    assert any("stale" in flag["text"].lower() for flag in nodes[0]["flags"])


def test_missing_inventory_is_a_warning(now):
    queue = {"workers": [_worker("farm-09")], "jobs": []}
    nodes, _ = build_nodes(queue, {}, _config(), now)
    assert any("not in inventory" in flag["text"].lower() for flag in nodes[0]["flags"])


def test_driver_drift_is_info_until_configured(now):
    inventory = {**_inv("farm-01"), **_inv("farm-02"), **_inv("farm-03", driver="551.86")}
    queue = {"workers": [_worker("farm-01"), _worker("farm-02"), _worker("farm-03")], "jobs": []}
    nodes, std = build_nodes(queue, inventory, _config(), now)
    assert std["driver"] == "566.14"
    drifted = next(node for node in nodes if node["name"] == "farm-03")
    assert drifted["severity"] == INFO
    nodes, _ = build_nodes(
        queue,
        inventory,
        _config(standards={"driver_version": "566.14", "plugins": {}}),
        now,
    )
    drifted = next(node for node in nodes if node["name"] == "farm-03")
    assert drifted["severity"] == WARNING


def test_plugin_drift_against_most_common(now):
    inventory = {**_inv("farm-01"), **_inv("farm-02"), **_inv("farm-03", plugin="3.8.2")}
    queue = {"workers": [_worker("farm-01"), _worker("farm-02"), _worker("farm-03")], "jobs": []}
    nodes, std = build_nodes(queue, inventory, _config(), now)
    assert std["plugins"]["LightTrace"] == "3.9.0"
    drifted = next(node for node in nodes if node["name"] == "farm-03")
    assert any("3.8.2" in flag["text"] for flag in drifted["flags"])


def test_farm_is_the_queue_list(now):
    inventory = {**_inv("farm-01"), **_inv("artist-01")}
    queue = {"workers": [_worker("farm-01")], "jobs": []}
    nodes, _ = build_nodes(queue, inventory, _config(), now)
    assert [node["name"] for node in nodes] == ["farm-01"]


def test_error_messages_are_categorized():
    assert categorize("SceneApp license checkout failed") == "license"


def test_summary_counts_attention(now):
    inventory = {**_inv("farm-01"), **_inv("farm-02")}
    queue = {
        "workers": [_worker("farm-01", "stalled"), _worker("farm-02")],
        "jobs": [],
    }
    nodes, std = build_nodes(queue, inventory, _config(), now)
    summary = summarize(nodes, [], std, 24)
    assert summary["nodes"] == 2
    assert summary["attention"] == 1
    assert summary["critical"] == 1
    assert summary["states"]["stalled"] == 1
