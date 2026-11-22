from farmdash.analyze import build_jobs, worker_is_ready


def _node(name, state="idle", groups=None, pools=None, plugin="3.9.0"):
    return {
        "name": name,
        "state": state,
        "groups": groups or ["render"],
        "pools": pools or ["general"],
        "plugins": [{"plugin_name": "LightTrace", "plugin_version": plugin}],
    }


def _job(group="render", pool="general", version="3.9.0", status="queued", name="demo_spot_A"):
    return {
        "name": name,
        "status": status,
        "renderer": "LightTrace",
        "renderer_version": version,
        "group": group,
        "pool": pool,
        "user": "artist-01",
    }


def test_ready_requires_group_pool_and_plugin():
    node = _node("farm-01")
    assert worker_is_ready(node, _job()) == (True, True)


def test_wrong_pool_is_not_a_candidate():
    node = _node("farm-01", pools=["general"])
    assert worker_is_ready(node, _job(pool="priority")) == (False, False)


def test_wrong_plugin_version_is_candidate_but_not_ready():
    node = _node("farm-01", plugin="3.8.2")
    assert worker_is_ready(node, _job(version="3.9.0")) == (True, False)


def test_stalled_or_offline_workers_are_not_ready():
    stalled = _node("farm-03", state="stalled")
    offline = _node("farm-04", state="offline")
    assert worker_is_ready(stalled, _job()) == (True, False)
    assert worker_is_ready(offline, _job()) == (True, False)


def test_build_jobs_counts_ready_and_candidates():
    nodes = [
        _node("farm-01"),
        _node("farm-02", plugin="3.8.2"),
        _node("farm-03", state="offline"),
        _node("farm-04", pools=["priority"]),
    ]
    jobs = build_jobs([_job()], nodes)
    assert jobs[0]["candidates"] == 3
    assert jobs[0]["ready"] == 1
    assert jobs[0]["severity"] == 0


def test_job_with_no_ready_workers_is_flagged():
    nodes = [_node("farm-01", plugin="3.8.2"), _node("farm-02", state="stalled")]
    jobs = build_jobs([_job(version="3.9.0")], nodes)
    assert jobs[0]["ready"] == 0
    assert jobs[0]["candidates"] == 2
    assert jobs[0]["severity"] > 0
    assert "required plugin" in jobs[0]["issue"]


def test_job_with_no_candidates_is_flagged():
    nodes = [_node("farm-01", groups=["render"], pools=["general"])]
    jobs = build_jobs([_job(group="gpu-heavy")], nodes)
    assert jobs[0]["candidates"] == 0
    assert "No workers" in jobs[0]["issue"]
