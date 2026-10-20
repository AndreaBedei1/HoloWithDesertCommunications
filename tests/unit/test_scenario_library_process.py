"""Cross-process locking, not a simulated network or a filesystem mock."""
import subprocess
import sys

import pytest
from holo_desert.scenarios.library import ScenarioLibrary


def test_os_lock_releases_when_owner_process_exits(tmp_path):
    code = "from holo_desert.scenarios.library import ScenarioLibrary; import os,sys; lib=ScenarioLibrary(sys.argv[1]); lock=lib._write_lock(); lock.__enter__(); os._exit(0)"
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=15)
    assert result.returncode == 0
    # File remains, but its OS lock must not remain held after a crash/exit.
    assert (tmp_path / ".library.lock").exists()
    with ScenarioLibrary(tmp_path)._write_lock():
        pass


def test_symlink_cannot_redirect_a_personal_file(tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("private", encoding="utf-8")
    root = tmp_path / "library"
    root.mkdir()
    identifier = "user_" + "0" * 32
    try:
        (root / (identifier + ".yaml")).symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires privileges on this Windows host")
    with pytest.raises(ValueError, match="consentito"):
        ScenarioLibrary(root).get(identifier)
    assert outside.read_text(encoding="utf-8") == "private"
