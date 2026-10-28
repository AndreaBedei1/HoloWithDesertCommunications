import importlib.util
from pathlib import Path
import pytest
from holo_desert.scenarios.config import RESOURCE_ROOT, Scenario, ScenarioManager


def builder():
    path=RESOURCE_ROOT/'docker/stack_builder.py'
    spec=importlib.util.spec_from_file_location('stack_builder',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_old_examples_keep_original_protocols_and_explicit_phy_version():
    manager=ScenarioManager()
    # E01-E06 only: the demonstrations use other protocols on purpose.
    for name in [n for n in manager.list() if manager.group(n)=='reference']:
        scenario=manager.load(name)
        assert scenario.network.acoustic.phy=='bpsk_upstream'
        text=builder().render(scenario.model_dump())
        assert 'set mac_adapter aloha' in text
        assert 'set routing_adapter static' in text


def test_original_wire_config_defaults_to_upstream_without_new_fields():
    data=ScenarioManager().load('e01_chat').model_dump()
    acoustic=data['network']['acoustic']
    for key in list(acoustic):
        if key not in ('bitrate_bps','tx_power_db','frequency_hz','bandwidth_hz','propagation','interference'):
            acoustic.pop(key)
    assert 'Module/MPhy/BPSK/Underwater/HOLO/Corrected' not in builder().render(data)


def test_csma_queue_mode_is_explicit_and_legacy_defaults_remain_reproducible():
    data=ScenarioManager().load('e01_chat').model_dump()
    assert data['network']['mac']['queue_mode']=='legacy'
    data['network']['mac'].update(queue_mode='bounded',buffer_packets=2)
    scenario=Scenario.model_validate(data)
    assert 'set bounded_queue 1' in builder().render(scenario.model_dump())
    data['network']['mac']['queue_mode']='evil; exec calc'
    with pytest.raises(ValueError):builder().render(data)


def test_slot_bound_includes_fractional_timestamps_and_reply_envelope():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']='tdma'
    data['network']['mac']['tdma']['frame_duration_s']=.95
    data['flows'][0].update(start=1/30,stop=.5,payload_bytes=32,reply=True)
    with pytest.raises(ValueError,match='fit'):builder().render(data)


def test_slot_bound_checks_reply_interfaces_and_heartbeat_traffic():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']='tdma'
    data['nodes'][1]['communication']={'acoustic':{'bitrate_bps':1000}}
    with pytest.raises(ValueError,match='fit'):builder().render(data)
    data=ScenarioManager().load('e06_coordination').model_dump()
    data['network']['mac']['protocol']='tdma'
    assert 'mac_adapter tdma' in builder().render(data)
    data['network']['mac']['tdma']['frame_duration_s']=.5
    with pytest.raises(ValueError,match='fit'):builder().render(data)


def test_tdma_assignments_and_flooding_are_validated_before_rendering():
    data=ScenarioManager().load('e02_multi_node').model_dump()
    data['network']['mac']['protocol']='tdma'
    data['network']['routing']='flooding'
    scenario=Scenario.model_validate(data)
    assert 'set mac_adapter tdma' in builder().render(scenario.model_dump())
    data=scenario.model_dump()
    data['network']['mac']['tdma']['slot_assignment']={'auv_01':0,'auv_02':0}
    with pytest.raises(ValueError,match='slot'):
        Scenario.model_validate(data)


def test_instance_overrides_do_not_change_other_nodes():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['nodes'][0]['communication']={'acoustic':{'tx_power_db':105,'frequency_hz':24000}}
    scenario=Scenario.model_validate(data)
    effective=builder().effective_nodes(scenario.model_dump())
    assert effective[0]['acoustic']['tx_power_db']==105
    assert effective[1]['acoustic']['tx_power_db']==135
    assert effective[1]['acoustic']['frequency_hz']==25000


@pytest.mark.parametrize('path,value', [('protocol','evil; exec calc'),('protocol','unknown')])
def test_direct_docker_input_cannot_inject_tcl(path,value):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac'][path]=value
    with pytest.raises(ValueError):builder().render(data)


def test_nonfinite_override_and_unsupported_interface_rejected():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['nodes'][0]['communication']={'acoustic':{'tx_power_db':float('nan')}}
    with pytest.raises(ValueError):Scenario.model_validate(data)
    data['nodes'][0].pop('communication')
    data['flows'][0]['interface']='optical'
    with pytest.raises(ValueError):Scenario.model_validate(data)


def test_direct_tcp_route_cycles_and_invalid_native_integers_rejected():
    data=ScenarioManager().load('e05_multihop').model_dump()
    data['network']['routes']={'auv_01':{'auv_03':'auv_02'},'auv_02':{'auv_03':'auv_01'}}
    with pytest.raises(ValueError,match='loop'):builder().render(data)
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']='csma_ca';data['network']['acoustic']['bitrate_bps']=.5
    with pytest.raises(ValueError):Scenario.model_validate(data)


@pytest.mark.parametrize('protocol',['csma_ca','dacap'])
def test_handshake_macs_reject_flooding_broadcast(protocol):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']=protocol;data['network']['routing']='flooding'
    with pytest.raises(ValueError,match='Flooding'):builder().render(data)
    with pytest.raises(ValueError,match='Flooding'):Scenario.model_validate(data)
