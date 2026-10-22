import importlib.util
from pathlib import Path
import pytest

def test_em_patch_refuses_unknown_source_and_removes_end_dereference():
    path=Path(__file__).parents[2]/'src/holo_desert/resources/desert/extensions/prepare-em-safe.py'
    assert path.is_file(), 'Missing isolated native EM safety patch'
    spec=importlib.util.spec_from_file_location('em_patch',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with pytest.raises(ValueError):module.patch_source('unrecognized upstream source')
    source='"uwem-phy.h" UwElectroMagneticPhy Module/UW/ElectroMagnetic/PHY it == lut_map.end() && it->first != rx_power return it->second; double rx_power = TxPower_ +'
    result=module.patch_source(source)
    assert 'it == lut_map.end() &&' not in result
    assert 'HoloSafeElectroMagneticPhy' in result
    assert 'return it->second / 100.0;' in result
    assert 'double rx_power = 10 * log10(ph->Pt) +' in result
