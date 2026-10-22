"""Validated single native optical/EM interface inputs, never link decisions."""
import math

OPTICAL_DEFAULTS={'tx_power_w':50.,'bitrate_bps':1000000.,'frequency_hz':10000000.,'bandwidth_hz':100000.,
    'attenuation_per_m':.043,'temperature_k':293.15,'receiver_area_m2':.0000011,
    'transmitter_area_m2':.00001,'beam_angle_rad':1.,'dark_current_a':1e-9,
    'shunt_resistance_ohm':1.49e9,'responsivity_a_w':.26,'acquisition_threshold_db':10.,'directional':False,
    'mount_yaw_deg':0.,'mount_pitch_deg':0.,'mount_roll_deg':0.,'offset_x_m':0.,'offset_y_m':0.,'offset_z_m':0.}
EM_DEFAULTS={'tx_power_dbm':14.,'bitrate_bps':27000.,'frequency_hz':868000000.,'bandwidth_hz':125000.,
    'temperature_c':20.,'salinity_ppt':0.,'antenna_gain_db':2.}


def validate_medium(medium,values):
    defaults=OPTICAL_DEFAULTS if medium=='optical' else EM_DEFAULTS
    if not isinstance(values,dict) or set(values)-set(defaults):raise ValueError('Unsupported '+medium+' parameter')
    result={**defaults,**values}
    bounds={'tx_power_w':(1e-15,10000),'bitrate_bps':(1,1e9),'frequency_hz':(1,1e15),'bandwidth_hz':(1,1e12),
        'attenuation_per_m':(0,100),'temperature_k':(250,350),'receiver_area_m2':(1e-12,10),
        'transmitter_area_m2':(1e-12,10),'beam_angle_rad':(0,1.56),'dark_current_a':(0,1),
        'shunt_resistance_ohm':(1,1e15),'responsivity_a_w':(1e-12,100),'acquisition_threshold_db':(-100,100),
        'tx_power_dbm':(-100,100),'temperature_c':(0,40),'salinity_ppt':(0,40),'antenna_gain_db':(-100,100)}
    for key,value in result.items():
        if key=='directional':
            if not isinstance(value,bool):raise ValueError('Optical directional must be boolean')
            continue
        low,high=(-360,360) if key.startswith('mount_') else (-100,100) if key.startswith('offset_') else bounds[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Invalid '+medium+' '+key)
    if result['bandwidth_hz']>=2*result['frequency_hz']:raise ValueError('Medium band must stay above zero Hz')
    return result


def validate_media_stack(config):
    net=config['network'];medium=net.setdefault('medium','acoustic')
    if medium not in ('acoustic','optical','em'):raise ValueError('Unsupported medium')
    for name in ('optical','em'):net[name]=validate_medium(name,net.get(name,{}))
    if medium!='acoustic':
        if net['mac']['protocol']!='csma_aloha' or net.get('routing','static')!='static':
            raise ValueError('This medium currently requires verified CSMA-ALOHA and StaticRouting')
        if net['acoustic'].get('propagation','underwater')!='underwater':raise ValueError('Nonacoustic medium cannot use WOSS')
        if any(any(v is not None for v in ((n.get('communication') or {}).get('acoustic') or {}).values()) for n in config['nodes']):
            raise ValueError('Acoustic node overrides cannot configure a nonacoustic medium')
        if medium=='optical':
            for node in config['nodes']:
                for point in [node['position']]+[w[1:] for w in node.get('waypoints',[])]:
                    if not -20<=point[2]<0:raise ValueError('Optical noise LUT covers underwater depths through 20 m')
    return medium
