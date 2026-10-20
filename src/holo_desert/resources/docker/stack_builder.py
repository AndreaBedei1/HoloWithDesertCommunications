"""Whitelist-only stack construction, shared with the Python host and Docker.

No propagation, routing or packet delivery is implemented in this module.
It has no third-party dependency so direct TCP input receives the same checks.
"""
import copy
import json
import math
from pathlib import Path
import re

HERE=Path(__file__).parent
CATALOG_VERSION='desert-lab-v2'
MACS={'aloha':('aloha','Module/UW/ALOHA',['libuwaloha.so']),
      'csma_aloha':('aloha','Module/UW/CSMA_ALOHA',['libuwcsmaaloha.so']),
      'tdma':('tdma','Module/UW/TDMA',['libuwtdma.so']),
      'tdma_frame':('tdma_frame','Module/UW/TDMA_FRAME',['libuwtdma.so','libuwtdma_frame.so']),
      'csma_ca':('csma_ca','Module/UW/CSMA_CA',['libuwcsmaca.so']),
      'dacap':('dacap','Module/UW/DACAP',['libuwdacap.so'])}
PHYS={'bpsk_upstream':'Module/MPhy/BPSK/Underwater/HOLO',
      'bpsk_corrected':'Module/MPhy/BPSK/Underwater/HOLO/Corrected'}
ROUTING={'static':('Module/UW/StaticRouting','libuwstaticrouting.so'),
         'flooding':('Module/UW/FLOODING','libuwflooding.so')}


def catalog():
    return json.loads((HERE/'communication-catalog.json').read_text(encoding='utf-8'))


def number(value,minimum=None,maximum=None,integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Expected a finite numeric parameter')
    if minimum is not None and value<minimum or maximum is not None and value>maximum:
        raise ValueError('Parameter outside supported bounds')
    if integer and value!=int(value):raise ValueError('Expected integer parameter')
    return str(int(value)) if integer else format(value,'.15g')


def effective_nodes(config):
    result=[]
    for node in config['nodes']:
        acoustic=dict(config['network']['acoustic'])
        override=(node.get('communication') or {}).get('acoustic') or {}
        allowed={'bitrate_bps','tx_power_db','frequency_hz','bandwidth_hz','phy','spreading','shipping','wind_speed_mps','rx_snr_penalty_db','acquisition_threshold_db'}
        if set(override)-allowed:raise ValueError('Unsupported per-node interface override')
        acoustic.update({k:v for k,v in override.items() if v is not None})
        result.append({'id':node['id'],'interface':'acoustic','acoustic':acoustic})
    return result


def defaults(config):
    config=copy.deepcopy(config)
    net=config['network'];net.setdefault('flooding',{})
    net.setdefault('routing','static');net.setdefault('seed',1);net.setdefault('routes',{})
    net['acoustic'].setdefault('phy','bpsk_upstream')
    net['mac'].setdefault('tdma',{}).setdefault('slot_assignment',{});net['mac'].setdefault('csma_ca',{});net['mac'].setdefault('dacap',{})
    for module in catalog()['modules']:
        for field in module.get('parameters',[]):
            keys=field['path'].split('.')[1:];current=net
            for key in keys[:-1]:current=current.setdefault(key,{})
            current.setdefault(keys[-1],field['default'])
    return config


def validate(config):
    try:
        net=config['network'];nodes=config['nodes'];ids=[n['id'] for n in nodes]
        if len(ids)!=len(set(ids)) or not 2<=len(ids)<=32 or any(not re.fullmatch(r'auv_[0-9]{2}',x) for x in ids):
            raise ValueError('Expected 2..32 unique auv_NN nodes')
        if net['mac']['protocol'] not in MACS or net.get('routing','static') not in ROUTING:
            raise ValueError('Unsupported DESERT protocol')
        number(net.get('seed',1),1,100000,True)
        c=defaults(config);net=c['network']
        if net['routing']=='flooding' and net['mac']['protocol'] in ('csma_ca','dacap'):
            raise ValueError('Flooding broadcast is not supported by the verified CSMA/CA or DACAP handshake stack')
        # Only data from explicitly registered controls can enter generated Tcl.
        for module in catalog()['modules']:
            for field in module.get('parameters',[]):
                keys=field['path'].split('.')[1:];value=net
                for key in keys:value=value[key]
                if field['type'] in ('number','integer'):
                    number(value,field.get('min'),field.get('max'),field['type']=='integer')
                elif field['type']=='checkbox':
                    if not isinstance(value,bool):raise ValueError('Expected boolean parameter')
        effective=effective_nodes(c)
        for node in effective:
            a=node['acoustic']
            if a['phy'] not in PHYS or a.get('propagation','underwater')!='underwater' or a.get('interference','miv')!='miv':
                raise ValueError('Unsupported PHY/channel combination')
            for name in ('bitrate_bps','frequency_hz','bandwidth_hz','sound_speed_mps'):number(a[name],1e-12)
            number(a['tx_power_db'],0,200);number(a['spreading'],1e-12,3);number(a['shipping'],0,1);number(a['wind_speed_mps'],0)
            number(a['rx_snr_penalty_db']);number(a['acquisition_threshold_db'])
            if a['bandwidth_hz']>=2*a['frequency_hz']:raise ValueError('Acoustic band must stay above zero Hz')
        if net['mac']['protocol']=='csma_ca':
            for node in effective:number(node['acoustic']['bitrate_bps'],1,2147483647,True)
        if net['routing']!='static' and net.get('routes'):raise ValueError('Static routes cannot be used with Flooding')
        for src,routes in net.get('routes',{}).items():
            if src not in ids or any(dst not in ids or hop not in ids or src==hop or src==dst for dst,hop in routes.items()):
                raise ValueError('Invalid static route reference')
        for source in ids:
            for destination in ids:
                current=source;visited=set()
                while current!=destination:
                    if current in visited:raise ValueError('Static route loop')
                    visited.add(current)
                    current=net.get('routes',{}).get(current,{}).get(destination,destination)
        if net['mac']['protocol'] in ('tdma','tdma_frame'):
            if net['mac']['ack']:raise ValueError('TDMA does not support the ALOHA ACK option')
            tdma=net['mac']['tdma'];slots=tdma.get('slot_assignment',{})
            if slots and set(slots)!=set(ids):raise ValueError('Assign one slot to every node')
            if not slots:
                tdma['slot_assignment']={node:i for i,node in enumerate(ids)}
            values=list(slots.values()) if slots else list(range(len(ids)))
            if sorted(values)!=list(range(len(ids))):raise ValueError('TDMA slot assignments must be unique in 0..N-1')
            slot=tdma['frame_duration_s']/len(ids)
            if tdma['guard_time_s']>=slot:raise ValueError('TDMA guard time must be shorter than a slot')
            flows=c.get('flows',[])
            if c.get('coordination'):
                flows=[{'source':ids[0],'destination':ids[1],'payload_bytes':5,'message_type':'heartbeat','ttl':3.0}]
            for flow in flows:
                # Envelope length is not payload length; conservative upper bound
                # includes a long floating timestamp and the same JSON/base64 format.
                request=flow.get('reply',False) or flow.get('message_type')=='request'
                payload=flow.get('payload_bytes',32)+(4 if request else 0)
                wire={'source':flow['source'],'destination':flow['destination'],'payload':'A'*(4*((payload+2)//3)),
                      'creation_time':1.7976931348623157e308,'id':'0'*32,
                      'message_type':'request' if request else flow.get('message_type','data'),
                      'priority':0,'ttl':flow.get('ttl',20),'version':1}
                # Four UDP bytes, one Flooding byte; TDMA header is explicitly zero.
                overhead=4+(1 if net['routing']=='flooding' else 0)
                # Conservatively include slower interfaces that may forward/reply.
                bitrate=min(node['acoustic']['bitrate_bps'] for node in effective)
                duration=(len(json.dumps(wire,separators=(',',':')))+overhead)*8/bitrate
                if duration>slot-tdma['guard_time_s']:raise ValueError('Frame does not fit its TDMA slot: increase frame duration or reduce payload')
        for f in c.get('flows',[]):
            if f.get('final_interval') is not None and f.get('stop') is None:
                raise ValueError('Variable interval requires flow stop')
            if f.get('interface','acoustic')!='acoustic':raise ValueError('Only the verified acoustic interface is supported')
            if f.get('pattern','periodic') not in ('periodic','poisson','burst','events'):raise ValueError('Unsupported traffic pattern')
            if f.get('pattern')=='events' and (not f.get('events') or sorted(set(f['events']))!=f['events'] or any(t<f.get('start',1) or f.get('stop') is not None and t>=f['stop'] for t in f['events'])):
                raise ValueError('Traffic events must be unique, increasing and within the flow window')
            if f.get('pattern')=='burst' and (f.get('burst_count',3)-1)*f.get('burst_interval_s',.25)>=f.get('burst_period_s',5):
                raise ValueError('Burst duration must be shorter than its period')
        return c
    except (KeyError,TypeError,IndexError) as exc:
        raise ValueError('Invalid stack configuration: '+str(exc)) from exc


def render(config):
    c=validate(config);net=c['network'];mac=net['mac'];a=net['acoustic'];ids={n['id']:i+1 for i,n in enumerate(c['nodes'])}
    adapter,macclass,libs=MACS[mac['protocol']];routingclass,routinglib=ROUTING[net['routing']]
    values={'count':len(ids),'seed':net['seed'],'frequency':a['frequency_hz'],'bandwidth':a['bandwidth_hz'], 'bitrate':a['bitrate_bps'],'power':a['tx_power_db'],'ack':int(mac['ack']),'max_tries':mac['max_tx_tries'],'buffer_packets':mac['buffer_packets']}
    lines=['set '+k+' '+number(v) for k,v in values.items()]
    lines+=['set mac_adapter '+adapter,'set mac_class '+macclass,'set routing_adapter '+net['routing'],'set routing_class '+routingclass,
            'set extra_libraries {'+' '.join(libs+[routinglib])+'}',
            'set sound_speed '+number(a['sound_speed_mps'])]
    params=mac.get('tdma' if adapter=='tdma_frame' else adapter,{}) if adapter!='aloha' else {}
    allowed={'tdma':{'frame_duration_s','guard_time_s','max_packets_per_slot','slot_assignment'},'tdma_frame':{'frame_duration_s','guard_time_s','max_packets_per_slot','slot_assignment'},'csma_ca':{'queue_size','backoff_delta_s','backoff_max','cts_wait_s','data_wait_s','ack_wait_s'},'dacap':{'wait_costant_s','delta_d','t_min','tw_min','max_prop_delay_s'},'aloha':set()}
    if set(params)-allowed[adapter]:raise ValueError('Unsupported module parameter')
    if set(net['flooding'])-{'ttl','maximum_cache_time_s','optimize'}:raise ValueError('Unsupported flooding parameter')
    parts=[]
    for key,value in params.items():
        if key=='slot_assignment':
            assignment=value or {n:i for i,n in enumerate(ids)}
            parts+=[key,'{'+' '.join(str(ids[n])+' '+number(slot,0,len(ids)-1,True) for n,slot in assignment.items())+'}']
        else:parts += [key,number(value)]
    lines.append('set mac_parameters {'+' '.join(parts)+'}')
    for i,node in enumerate(effective_nodes(c),1):
        ac=node['acoustic'];lines.append('set phy_class('+str(i)+') '+PHYS[ac['phy']])
        lines.append('set acoustic('+str(i)+') {'+' '.join(k+' '+number(ac[k]) for k in ('tx_power_db','bitrate_bps','frequency_hz','bandwidth_hz','spreading','shipping','wind_speed_mps','rx_snr_penalty_db','acquisition_threshold_db'))+'}')
    lines.append('set flooding_parameters {'+' '.join(k+' '+number(int(v) if isinstance(v,bool) else v) for k,v in net['flooding'].items())+'}')
    routes=[]
    for src,sid in ids.items():
        for dst,did in ids.items():
            if src!=dst:routes.append('{%d %d %d}'%(sid,did,ids[net.get('routes',{}).get(src,{}).get(dst,dst)]))
    lines.append('set routes {'+' '.join(routes)+'}')
    if adapter=='tdma_frame':
        slots=params.get('slot_assignment') or {n:i for i,n in enumerate(ids)}
        # Numeric matrix in the session temp directory, never a user path.
        matrix='\n'.join(' '.join('1' if col==slots[n] else '0' for col in range(len(ids))) for n in ids)+'\n'
        lines+=['set frame_matrix [file join [pwd] tdma_matrix.txt]','set matrix_file [open $frame_matrix w]','puts -nonewline $matrix_file {'+matrix+'}','close $matrix_file']
    return '\n'.join(lines)+'\n'
