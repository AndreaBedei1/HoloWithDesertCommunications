"""Build-only isolated EM patch em-power-lut-v1. Installed DESERT stays intact."""
from pathlib import Path


def patch_source(source):
    old='it == lut_map.end() && it->first != rx_power'
    if source.count(old)!=1 or source.count('return it->second;')!=1 or source.count('double rx_power = TxPower_ +')!=1 or 'UwElectroMagneticPhy' not in source:
        raise ValueError('EM upstream source does not match em-power-lut-v1')
    return source.replace(old,'it == lut_map.end()').replace('return it->second;','return it->second / 100.0;').replace('double rx_power = TxPower_ +','double rx_power = 10 * log10(ph->Pt) +').replace('UwElectroMagneticPhy','HoloSafeElectroMagneticPhy').replace('"uwem-phy.h"','"uwem-phy-safe.h"').replace('Module/UW/ElectroMagnetic/PHY','Module/UW/ElectroMagnetic/PHY/Safe')


if __name__=='__main__':
    source=Path('/home/DESERT_Underwater/DESERT_Framework/DESERT/physical/uwem_phy')
    dest=Path(__file__).parent
    (dest/'uwem-phy-safe.cpp').write_text(patch_source((source/'uwem-phy.cpp').read_text()))
    header=(source/'uwem-phy.h').read_text()
    if header.count('double getRxPower(Packet *p);')!=1:raise ValueError('Unknown EM header')
    header=header.replace('double getRxPower(Packet *p);','double getRxPower(Packet *p);\n\tdouble getTxPower(Packet*) override { return pow(10.0, TxPower_ / 10.0); }')
    (dest/'uwem-phy-safe.h').write_text(header.replace('UwElectroMagneticPhy','HoloSafeElectroMagneticPhy').replace('UWEM_PHY_H','HOLO_SAFE_UWEM_PHY_H'))
