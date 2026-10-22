"""Attach the public API to a HoloOcean environment owned by the caller."""
import pytest

from holo_desert import HoloOceanLink, ManagedSimulation, NetworkSession, load_scenario, pose_from_sensors
from holo_desert.holoocean_adapter.adapter import HoloOceanAdapter

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def test_link_follows_external_environment_without_second_instance(engine):
    scenario = load_scenario("e01_chat")
    # Stands in for the user's application: it creates and drives the environment.
    owner = HoloOceanAdapter(scenario, show_viewport=False)
    owner.start()
    env = owner.env
    try:
        net = NetworkSession(scenario, manage_engine=False)
        link = HoloOceanLink(net, ticks_per_sec=scenario.physics_hz)
        received = []
        with net:
            net.node("auv_02").on_receive(received.append)
            state = env.tick(publish=False)
            link.attach(state)
            net.node("auv_01").send_json("auv_02", {"seq": 1})
            last = None
            for tick in range(1, 6 * scenario.physics_hz):
                env.act("auv_01", [0, -15, -20, 0, 0, 0])   # caller keeps vehicle control
                env.act("auv_02", [30, 0, -20, 0, 0, 0])
                state = env.tick(publish=False)
                link.sync(state)
                last = state
            assert net.time == pytest.approx((6 * scenario.physics_hz - 1) / scenario.physics_hz)
            measured = pose_from_sensors(last["auv_01"])
            assert net.node("auv_01").pose == measured
            assert measured.y < -1          # movement came from HoloOcean physics
            assert [d.message.json() for d in received] == [{"seq": 1}]
    finally:
        owner.stop()


def test_managed_simulation_with_holoocean(engine):
    scenario = load_scenario("e01_chat")
    scenario = type(scenario).model_validate({**scenario.model_dump(), "duration": 8})
    with ManagedSimulation(scenario, realtime=False, manage_engine=False) as sim:
        summary = sim.run()
        assert sim.state == "finished" and summary["received"] >= 2
        assert sim.snapshot()["services"] == {"holoocean": "stopped", "desert": "stopped"}
