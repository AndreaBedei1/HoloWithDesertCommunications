import subprocess
from holo_desert.holoocean_adapter.adapter import HoloOceanAdapter
from holo_desert.scenarios.config import ScenarioManager


def test_upstream_teardown_timeout_reaps_only_owned_process():
    class OwnedProcess:
        waited = False
        def wait(self, timeout):
            self.waited = True
            return -1
    class Environment:
        attempts = 0
        _world_process = OwnedProcess()
        def __exit__(self, *args):
            self.attempts += 1
            if self.attempts == 1:
                raise subprocess.TimeoutExpired("owned-unreal", 10)
    adapter = HoloOceanAdapter(ScenarioManager().load("e01_chat"))
    environment = Environment()
    adapter.env = environment
    adapter.stop()
    assert environment._world_process.waited
    assert environment.attempts == 2
    assert adapter.env is None


def test_kernel_confirmed_exit_is_not_misreported_as_running(monkeypatch):
    from holo_desert.holoocean_adapter import adapter as module
    class OwnedProcess:
        returncode = None
        def wait(self, timeout):
            raise AssertionError("A kernel-confirmed exit needs no further blocking wait")
    class Environment:
        attempts = 0
        _world_process = OwnedProcess()
        def __exit__(self, *args):
            self.attempts += 1
            if self._world_process.returncode is None:
                raise subprocess.TimeoutExpired("owned-unreal", 10)
    monkeypatch.setattr(module, "_kernel_exit_code", lambda process: 1)
    adapter = HoloOceanAdapter(ScenarioManager().load("e01_chat"))
    environment = Environment()
    adapter.env = environment
    adapter.stop()
    assert environment._world_process.returncode == 1
    assert environment.attempts == 2
    assert adapter.env is None
