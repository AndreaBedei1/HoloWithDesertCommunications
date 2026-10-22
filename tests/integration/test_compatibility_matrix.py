"""Cross-layer combinations the Network Designer offers, each delivering through real DESERT."""
import pytest

from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark = pytest.mark.desert

MACS = ['aloha', 'csma_aloha', 'tdma', 'tdma_frame', 'csma_ca', 'dacap', 'csburst', 'tokenbus', 'ranging_tokenbus', 'ranging_tdma']


def scenario(mac='csma_aloha', routing='static', generator='python', pattern='periodic', medium='acoustic', woss=False, multiphy=False):
    data = ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=12, realtime=False)
    data['network']['mac']['protocol'] = mac
    data['network']['routing'] = routing
    flow = {'source': 'auv_01', 'destination': 'auv_02', 'start': 1, 'stop': 9, 'interval': 2, 'payload_bytes': 16, 'ttl': 10}
    if generator != 'python':
        flow.update(generator=generator, pattern=pattern, native_packet_bytes=32)
    data['flows'] = [flow]
    if routing == 'sun':
        data['network']['sun']['sink'] = 'auv_02'
    if medium != 'acoustic':
        data['network']['medium'] = medium
        for i, node in enumerate(data['nodes']):
            node['position'] = [i, 0, -10]
    if woss:
        data['network']['acoustic'].update(propagation='woss', tx_power_db=150)
    if multiphy:
        data['network']['multiphy'] = {'interfaces': [
            {'id': 'long', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'bitrate_bps': 4800}},
            {'id': 'short', 'acoustic': {'frequency_hz': 50000, 'bandwidth_hz': 9000, 'bitrate_bps': 8800}}],
            'initial_interface': 'long'}
    return data


def delivered(data):
    run = SimulationOrchestrator(Scenario.model_validate(data), standalone=True, manage_docker=False)
    try:
        run.run()
        state = run.snapshot()
        assert run.state == 'finished', run.error
        return state['counts']
    finally:
        run.close()


@pytest.mark.parametrize('mac', [m for m in MACS if m != 'csma_aloha'])
def test_woss_with_each_mac(engine, mac):
    counts = delivered(scenario(mac, woss=True))
    assert counts['received'] >= 1, counts


@pytest.mark.parametrize('routing', ['flooding', 'sun'])
def test_woss_with_dynamic_routing(engine, routing):
    counts = delivered(scenario(routing=routing, woss=True))
    assert counts['received'] >= 1, counts


@pytest.mark.parametrize('generator', ['desert_cbr', 'desert_vbr'])
@pytest.mark.parametrize('mac', [m for m in MACS if m != 'csma_aloha'])
def test_native_generators_with_each_mac(engine, generator, mac):
    counts = delivered(scenario(mac, generator=generator))
    assert counts['received'] >= 1, counts


@pytest.mark.parametrize('generator', ['desert_cbr', 'desert_vbr'])
@pytest.mark.parametrize('case', [dict(medium='optical'), dict(medium='em'), dict(woss=True), dict(multiphy=True),
                                  dict(routing='flooding'), dict(pattern='poisson')])
def test_native_generators_across_media_and_stacks(engine, generator, case):
    counts = delivered(scenario(generator=generator, **case))
    assert counts['received'] >= 1, counts
