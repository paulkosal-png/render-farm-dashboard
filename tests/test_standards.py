from farmdash.analyze import compute_standards, most_common, version_key


def test_most_common_picks_the_majority():
    assert most_common(["3.9.0", "3.9.0", "3.8.2"]) == "3.9.0"


def test_most_common_tie_uses_higher_version():
    assert most_common(["3.8.2", "3.9.0", "3.8.2", "3.9.0"]) == "3.9.0"


def test_version_key_orders_numeric_parts():
    assert version_key("3.9.0") > version_key("3.8.2")
    assert version_key("566.14") > version_key("551.86")


def test_farm_standard_uses_configured_driver_when_set():
    inventory = {
        "FARM-01": {"gpus": [{"driver_version": "566.14"}], "plugins": []},
        "FARM-02": {"gpus": [{"driver_version": "566.14"}], "plugins": []},
        "FARM-03": {"gpus": [{"driver_version": "551.86"}], "plugins": []},
    }
    names = ["farm-01", "farm-02", "farm-03"]
    cfg = {"standards": {"driver_version": "551.86", "plugins": {}}}
    std = compute_standards(inventory, names, cfg)
    assert std["driver"] == "551.86"
    assert std["driver_configured"] is True


def test_farm_standard_falls_back_to_most_common():
    inventory = {
        "FARM-01": {
            "gpus": [{"driver_version": "566.14"}],
            "plugins": [{"plugin_name": "LightTrace", "plugin_version": "3.9.0"}],
        },
        "FARM-02": {
            "gpus": [{"driver_version": "566.14"}],
            "plugins": [{"plugin_name": "LightTrace", "plugin_version": "3.9.0"}],
        },
        "FARM-03": {
            "gpus": [{"driver_version": "551.86"}],
            "plugins": [{"plugin_name": "LightTrace", "plugin_version": "3.8.2"}],
        },
    }
    std = compute_standards(inventory, ["farm-01", "farm-02", "farm-03"], {"standards": {}})
    assert std["driver"] == "566.14"
    assert std["driver_configured"] is False
    assert std["plugins"]["LightTrace"] == "3.9.0"


def test_standards_ignore_machines_not_on_the_farm():
    inventory = {
        "FARM-01": {"gpus": [{"driver_version": "566.14"}], "plugins": []},
        "ARTIST-01": {"gpus": [{"driver_version": "551.86"}], "plugins": []},
    }
    std = compute_standards(inventory, ["farm-01"], {"standards": {}})
    assert std["driver"] == "566.14"
