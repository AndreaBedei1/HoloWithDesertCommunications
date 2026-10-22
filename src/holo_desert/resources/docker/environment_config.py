"""Validated WOSS environment data; propagation stays entirely native."""
import math

WOSS_DEFAULTS = {
    'origin_latitude_deg':42.59, 'origin_longitude_deg':10.125, 'x_bearing_deg':90.0,
    'water_depth_m':100.0,
    'ssp':[{'depth_m':0.0,'speed_mps':1500.0},{'depth_m':100.0,'speed_mps':1500.0}],
    'sediment_speed_mps':1560.0, 'sediment_density_g_cm3':1.5,
    'sediment_attenuation_db_lambda':0.9,
}


def validate_woss_position(position, water_depth):
    if len(position)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in position):
        raise ValueError('WOSS position requires finite local coordinates')
    x,y,z=position
    if not -water_depth+.1<z<-.1 or math.hypot(x,y)>100000:
        raise ValueError('WOSS position needs 0.1 m clearance from surface/seabed and must be within 100 km of the geographic origin')


def validate_woss_separation(positions):
    positions=list(positions)
    for i,(x,y,_) in enumerate(positions):
        if any(math.hypot(x-p[0],y-p[1])<1 for p in positions[i+1:]):
            raise ValueError('WOSS Bellhop requires at least 1 m horizontal separation between nodes')


def validate_woss(values):
    if not isinstance(values,dict) or set(values)-set(WOSS_DEFAULTS):
        raise ValueError('Unsupported WOSS environment parameter')
    result={**WOSS_DEFAULTS,**values}
    bounds={'origin_latitude_deg':(-85,85),'origin_longitude_deg':(-180,180),'x_bearing_deg':(0,360),
            'water_depth_m':(1,11000),'sediment_speed_mps':(100,10000),
            'sediment_density_g_cm3':(.1,20),'sediment_attenuation_db_lambda':(0,100)}
    for key,(low,high) in bounds.items():
        v=result[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Invalid WOSS '+key)
    points=result['ssp']
    if not isinstance(points,list) or not 2<=len(points)<=256:
        raise ValueError('WOSS SSP requires 2..256 depth/speed samples')
    previous=-1
    for p in points:
        if not isinstance(p,dict) or set(p)!={'depth_m','speed_mps'}:
            raise ValueError('WOSS SSP requires depth_m and speed_mps')
        d,s=p['depth_m'],p['speed_mps']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (d,s)) or not previous<d<=result['water_depth_m'] or not 1000<=s<=2000:
            raise ValueError('WOSS SSP depths must increase and sound speeds must be within 1000..2000 m/s')
        previous=d
    if points[0]['depth_m']!=0 or points[-1]['depth_m']!=result['water_depth_m']:
        raise ValueError('WOSS SSP must cover surface through water_depth_m')
    return result
