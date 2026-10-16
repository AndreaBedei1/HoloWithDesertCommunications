import time
import pytest
from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.scenarios.config import ScenarioManager

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def wait_until(condition, timeout=120):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail("Lifecycle transition timed out")
        time.sleep(.02)


def test_pause_and_stop_freeze_both_real_simulator_clocks(engine):
    scenario = ScenarioManager().load("e01_chat")
    scenario.duration = 5
    run = SimulationOrchestrator(scenario, manage_docker=False, show_viewport=False)
    try:
        run.start_background()
        wait_until(lambda: run.state == "failed" or run.clock.time >= .2)
        assert run.error is None, run.error
        run.pause()
        wait_until(lambda: run.state == "paused")
        clocks = (run.clock.time, run.backend.time, run.physics.env._num_ticks)
        time.sleep(.2)
        assert (run.clock.time, run.backend.time, run.physics.env._num_ticks) == clocks
        run.resume()
        wait_until(lambda: run.clock.time > clocks[0])
        run.stop()
        wait_until(lambda: run.state in ("stopped", "failed"))
        assert run.error is None, run.error
        assert run.clock.time < scenario.duration
        run.close()
        assert run.physics.env is None, [e for e in run.telemetry.events if e["event"] == "cleanup_error"]
        assert run.backend.socket is None
    finally:
        if not run.telemetry.log.closed:
            run.close()
