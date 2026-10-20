import subprocess
import sys
from types import SimpleNamespace
import pytest
from holo_desert.holoocean_adapter.adapter import HoloOceanAdapter
from holo_desert.scenarios.config import ScenarioManager


def test_windows_ipc_waits_for_both_handles_and_closes_probe_handles(monkeypatch):
    from holo_desert.holoocean_adapter.adapter import _wait_windows_ipc
    class Missing(Exception):winerror=2
    closed=[];calls=[]
    class Handle:
        def Close(self):closed.append(True)
    def opening(access,inherit,name):
        calls.append(name)
        if len(calls)==2:raise Missing()
        return Handle()
    monkeypatch.setitem(sys.modules,'win32event',SimpleNamespace(OpenSemaphore=opening))
    monkeypatch.setattr('holo_desert.holoocean_adapter.adapter.time.sleep',lambda _:None)
    _wait_windows_ipc('unique-session',SimpleNamespace(poll=lambda:None))
    assert len(calls)==4 and len(closed)==3
    assert all(name.endswith('unique-session') for name in calls)


def test_windows_ipc_does_not_retry_permission_errors(monkeypatch):
    from holo_desert.holoocean_adapter.adapter import _wait_windows_ipc
    class Denied(Exception):winerror=5
    def opening(*args):raise Denied()
    monkeypatch.setitem(sys.modules,'win32event',SimpleNamespace(OpenSemaphore=opening))
    with pytest.raises(Denied):_wait_windows_ipc('session',SimpleNamespace(poll=lambda:None))


def test_failed_windows_constructor_keeps_process_ownership(monkeypatch):
    import types
    class Environment:
        closed=False
        def __init__(self,**kwargs):
            self._world_process=object()
            raise RuntimeError('partial initialization')
        def __exit__(self,*args):self.closed=True
    monkeypatch.setitem(sys.modules,'holoocean.environments',types.SimpleNamespace(HoloOceanEnvironment=Environment))
    monkeypatch.setitem(sys.modules,'holoocean.packagemanager',types.SimpleNamespace(
        get_package_config_for_scenario=lambda cfg:{'worlds':[{'name':'OpenWater','pre_start_steps':2}]},
        get_binary_path_for_package=lambda name:'owned-binary'))
    adapter=HoloOceanAdapter(ScenarioManager().load('e01_chat'))
    with pytest.raises(RuntimeError,match='partial'):
        adapter._start_windows_environment({'world':'OpenWater','package_name':'Ocean'})
    environment=adapter.env
    assert environment._world_process is not None
    adapter.stop()
    assert environment.closed and adapter.env is None


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
