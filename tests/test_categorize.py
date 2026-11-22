from farmdash.analyze import categorize


def test_vram_messages():
    assert categorize("LightTrace ran out of VRAM while rendering the beauty pass") == "vram"
    assert categorize("GPU memory allocation failed") == "vram"
    assert categorize("out of gpu memory on device 0") == "vram"


def test_license_messages():
    assert categorize("SceneApp license checkout failed for LightTrace") == "license"
    assert categorize("Licence server unreachable") == "license"


def test_crash_messages():
    assert categorize("SceneApp worker process crashed with a fatal exception") == "crash"
    assert categorize("access violation at address 0") == "crash"


def test_missing_path_messages():
    msg = "Output path could not be created: share/projects/demo_spot_A/frames"
    assert categorize(msg) == "missing path"
    assert categorize("cannot find the path for the cache folder") == "missing path"
    assert categorize("no such file or directory: cache") == "missing path"


def test_other_is_the_fallback():
    assert categorize("color profile mismatch on the display") == "other"
    assert categorize("") == "other"
