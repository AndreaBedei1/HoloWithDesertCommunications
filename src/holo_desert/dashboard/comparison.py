"""Describe actual experimental differences without asserting model equivalence."""
import copy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def experiment(configuration):
    value=copy.deepcopy(configuration)
    value['network']={'seed':value['network']['seed']}
    for node in value['nodes']:node.pop('communication',None)
    for flow in value['flows']:flow.pop('interface',None)
    return digest(value)


def fields(value,path=''):
    if isinstance(value,dict):
        return {p:v for key,item in value.items() for p,v in fields(item,path+'.'+key if path else key).items()}
    if isinstance(value,(list,tuple)):
        return {path+'.length':len(value),**{p:v for i,item in enumerate(value) for p,v in fields(item,path+'.'+str(i)).items()}}
    return {path:value}


def differences(configurations):
    if len(configurations)<2:return [],[]
    maps=[fields(c) for c in configurations]
    paths=sorted(p for p in set().union(*maps) if p!='network.profile_id' and any(m.get(p)!=maps[0].get(p) for m in maps[1:]))
    def section(path):
        if path.startswith('network.mac.'):return 'mac'
        if path in ('network.routing',) or path.startswith(('network.routes.','network.flooding.','network.sun.')):return 'routing'
        if path.startswith('network.woss.') or path in ('network.acoustic.propagation','network.acoustic.sound_speed_mps'):return 'propagation'
        if path.startswith('network.acoustic.'):return 'phy'
        if '.communication.' in path or path.endswith('.interface'):return 'interfaces'
        return 'experiment'
    return paths,sorted({section(p) for p in paths})
