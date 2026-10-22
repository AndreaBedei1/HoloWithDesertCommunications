"""Whitelist-only stack construction, shared with the Python host and Docker.

No propagation, routing or packet delivery is implemented in this module.
It has no third-party dependency so direct TCP input receives the same checks.
"""
try:
    from .environment_config import validate_woss, validate_woss_position, validate_woss_separation
except ImportError:
    try:
        from holo_desert.resources.docker.environment_config import validate_woss, validate_woss_position, validate_woss_separation
    except ImportError:
        from environment_config import validate_woss, validate_woss_position, validate_woss_separation

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re

try:
    from .multiphy_config import effective_interfaces, render_multiphy
except ImportError:
    try:
        from holo_desert.resources.docker.multiphy_config import effective_interfaces, render_multiphy
    except ImportError:
        from multiphy_config import effective_interfaces, render_multiphy

try:
    from .medium_config import validate_media_stack
except ImportError:
    try:
        from holo_desert.resources.docker.medium_config import validate_media_stack
    except ImportError:
        from medium_config import validate_media_stack

try:
    from .application_config import native_flows, render_native_applications
except ImportError:
    try:
        from holo_desert.resources.docker.application_config import native_flows, render_native_applications
    except ImportError:
        from application_config import native_flows, render_native_applications

HERE=Path(__file__).parent
CATALOG_VERSION='desert-lab-v2'
MACS={'aloha':('aloha','Module/UW/ALOHA',['libuwaloha.so']),
      'csma_aloha':('aloha','Module/UW/CSMA_ALOHA',['libuwcsmaaloha.so']),
      'tdma':('tdma','Module/UW/TDMA',['libuwtdma.so']),
      'tdma_frame':('tdma_frame','Module/UW/TDMA_FRAME',['libuwtdma.so','libuwtdma_frame.so']),
      'csma_ca':('csma_ca','Module/UW/CSMA_CA',['libuwcsmaca.so']),
      'dacap':('dacap','Module/UW/DACAP',['libuwdacap.so']),
      'csburst':('csburst','Module/UW/CSBURST',['libuwcsburst.so']),
      'tokenbus':('tokenbus','Module/UW/TOKENBUS',['libuwcbr.so','libuwtokenbus.so']),
      'ranging_tokenbus':('ranging_tokenbus','Module/UW/RANGING_TOKENBUS',['libuwcbr.so','libuwtokenbus.so','libuwranging_tokenbus.so']),
      'ranging_tdma':('ranging_tdma','Module/UW/RANGING_TDMA',['libuwtdma.so','libuwranging_tdma.so'])}
PHYS={'bpsk_upstream':'Module/MPhy/BPSK/Underwater/HOLO',
      'bpsk_corrected':'Module/MPhy/BPSK/Underwater/HOLO/Corrected'}
ROUTING={'static':('Module/UW/StaticRouting','libuwstaticrouting.so'),
         'flooding':('Module/UW/FLOODING','libuwflooding.so'),
         'sun':('Module/UW/SUNNode','libsun.so')}


# Files copied into the engine image (see Dockerfile). Their digest, with the
# DESERT base image reference, identifies the build recipe, bridge, adapters and
# builder actually running, so a stale image that would silently ignore new
# options, or one built from another base, is rejected by the host client.
ENGINE_FILES=('Dockerfile','server.py','stack_builder.py','environment_config.py','medium_config.py','multiphy_config.py',
              'application_config.py','communication-catalog.json','desert-inventory.json','build-extension.sh','probe-sockets.py')


def pinned_base_image(docker_dir=HERE):
    """DESERT base image pinned by the Dockerfile (``ARG DESERT_IMAGE``)."""
    for line in (Path(docker_dir)/'Dockerfile').read_text(encoding='utf-8').splitlines():
        if line.startswith('ARG DESERT_IMAGE='):return line.split('=',1)[1].strip()
    raise ValueError('Dockerfile does not pin the DESERT base image')


def expected_base_image(docker_dir=HERE):
    """Base image of the Compose build: the ``DESERT_IMAGE`` override, else the pin."""
    return os.environ.get('DESERT_IMAGE') or pinned_base_image(docker_dir)


def engine_fingerprint(docker_dir=HERE,desert_dir=None,base_image=None):
    docker_dir=Path(docker_dir)
    desert_dir=Path(desert_dir) if desert_dir else (docker_dir/'desert' if (docker_dir/'desert').is_dir() else docker_dir.parent/'desert')
    entries=[(name,docker_dir/name) for name in ENGINE_FILES]
    entries+=[('desert/'+p.relative_to(desert_dir).as_posix(),p) for p in desert_dir.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    digest=hashlib.sha256()
    digest.update(b'base-image\x00'+(base_image or expected_base_image(docker_dir)).encode()+b'\x00')
    for name,path in sorted(entries):
        digest.update(name.encode()+b'\x00'+path.read_bytes().replace(b'\r\n',b'\n')+b'\x00')
    return digest.hexdigest()[:16]


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
        medium=config['network'].get('medium','acoustic')
        entry={'id':node['id'],'interface':medium,'acoustic':acoustic}
        if medium!='acoustic':entry[medium]=dict(config['network'][medium])
        result.append(entry)
    return result


def defaults(config):
    config=copy.deepcopy(config)
    net=config['network'];net.setdefault('flooding',{})
    validate_media_stack(config)
    net.setdefault('routing','static');net.setdefault('seed',1);net.setdefault('routes',{})
    sun=net.setdefault('sun',{})
    for key,value in {'sink':'auv_02','probe_interval_s':2,'buffer_interval_s':1,'data_interval_s':1,'status_interval_s':1,'poisson_timing':True,'max_ack_errors':3,'max_retransmissions':3,'buffer_packets':5,'probe_min_snr_db':0}.items():sun.setdefault(key,value)
    net['acoustic'].setdefault('phy','bpsk_upstream')
    net['woss']=validate_woss(net.get('woss',{}))
    net['mac'].setdefault('queue_mode','legacy')
    for protocol,parameters in {'csburst':{'max_packets_per_burst':3,'fixed_sensing_s':.1,'random_sensing_s':.1},'tokenbus':{'slot_time_s':10,'min_token_hold_s':.1,'max_token_hold_s':10},'ranging_tokenbus':{'slot_time_s':10,'min_token_hold_s':.1,'max_token_hold_s':10}}.items():
        for key,value in parameters.items():net['mac'].setdefault(protocol,{}).setdefault(key,value)
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
        if net['routing']=='sun':
            if net['mac']['protocol']!='csma_aloha' or net['mac']['ack']:raise ValueError('SUN requires the verified CSMA-ALOHA stack without MAC ACK')
            sun=net['sun']
            if set(sun)-{'sink','probe_interval_s','buffer_interval_s','data_interval_s','status_interval_s','poisson_timing','max_ack_errors','max_retransmissions','buffer_packets','probe_min_snr_db'}:raise ValueError('Unsupported SUN parameter')
            if sun['sink'] not in ids:raise ValueError('SUN sink must be a configured node')
            for key in ('probe_interval_s','buffer_interval_s','data_interval_s','status_interval_s'):number(sun[key],1e-12)
            if not isinstance(sun['poisson_timing'],bool):raise ValueError('Expected boolean SUN timing parameter')
            number(sun['max_ack_errors'],1,100,True);number(sun['buffer_packets'],1,10000,True);number(sun['probe_min_snr_db'])
            number(sun['max_retransmissions'],0,100,True)
            if any(f['destination']!=sun['sink'] or f['source']==sun['sink'] or f.get('reply') for f in c.get('flows',[])) or c.get('coordination'):
                raise ValueError('SUN supports convergecast flows to the designated sink without replies')
        native_flows(c)
        if net['mac']['queue_mode'] not in ('legacy','bounded'):raise ValueError('Unsupported MAC queue mode')
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
        if net['mac']['protocol'] in ('csburst','tokenbus','ranging_tokenbus','ranging_tdma'):
            if net['mac']['ack']:raise ValueError('This native MAC has no ALOHA ACK option')
            if net['routing']!='static':raise ValueError('Additional MACs currently require verified StaticRouting')
        if net['mac']['protocol']=='ranging_tdma':
            slots=net['mac']['ranging_tdma']
            if set(slots)-{'frame_duration_s','guard_time_s','max_packets_per_slot'}:raise ValueError('Unsupported module parameter')
            number(slots['frame_duration_s'],1e-12);number(slots['guard_time_s'],0)
            # The native ranging frame always uses one transmission of the slot.
            number(slots['max_packets_per_slot'],2,10000,True)
        if net['mac']['protocol'] in ('csburst','tokenbus','ranging_tokenbus'):
            protocol=net['mac']['protocol'];parameters=net['mac'][protocol]
            allowed={'max_packets_per_burst','fixed_sensing_s','random_sensing_s'} if protocol=='csburst' else {'slot_time_s','min_token_hold_s','max_token_hold_s'}
            if set(parameters)-allowed:raise ValueError('Unsupported module parameter')
            for key,value in parameters.items():number(value,0 if key=='random_sensing_s' else 1e-12,10000 if key=='max_packets_per_burst' else None,key=='max_packets_per_burst')
            if protocol!='csburst' and parameters['max_token_hold_s']<parameters['min_token_hold_s']:raise ValueError('Maximum token holding time must cover minimum holding time')
        effective=effective_nodes(c)
        if net['mac']['protocol'] in ('tokenbus','ranging_tokenbus'):
            token=net['mac'][net['mac']['protocol']]
            holding=token['max_token_hold_s']
            for flow in c.get('flows',[]):
                if flow.get('generator','python')!='python':
                    size=flow['native_packet_bytes']
                else:
                    payload=flow.get('payload_bytes',32)+(4 if flow.get('reply') or flow.get('message_type')=='request' else 0)
                    wire={'source':flow['source'],'destination':flow['destination'],'payload':'A'*(4*((payload+2)//3)),
                          'creation_time':1.7976931348623157e308,'id':'0'*32,'message_type':flow.get('message_type','data'),
                          'priority':0,'ttl':flow.get('ttl',20),'version':1}
                    size=len(json.dumps(wire,separators=(',',':')))
                # UDP adds four bytes and the compiled TokenBus header adds two.
                airtime=(size+6)*8/min(n['acoustic']['bitrate_bps'] for n in effective)
                if airtime>=holding:
                    raise ValueError('Frame does not fit its token holding time: increase maximum token holding time or reduce payload')
                if airtime>=3*(token['slot_time_s']+token['min_token_hold_s']):
                    raise ValueError('Frame exceeds the native token startup timeout: increase slot time or reduce payload')
        for node in effective:
            a=node['acoustic']
            if a['phy'] not in PHYS or a.get('propagation','underwater') not in ('underwater','woss') or a.get('interference','miv')!='miv':
                raise ValueError('Unsupported PHY/channel combination')
            for name in ('bitrate_bps','frequency_hz','bandwidth_hz','sound_speed_mps'):number(a[name],1e-12)
            number(a['tx_power_db'],0,200);number(a['spreading'],1e-12,3);number(a['shipping'],0,1);number(a['wind_speed_mps'],0)
            number(a['rx_snr_penalty_db']);number(a['acquisition_threshold_db'])
            if a['bandwidth_hz']>=2*a['frequency_hz']:raise ValueError('Acoustic band must stay above zero Hz')
        if net['acoustic'].get('propagation')=='woss':
            if any(n['acoustic']['phy']!='bpsk_upstream' for n in effective):raise ValueError('WOSS requires the original WOSS BPSK PHY')
            validate_woss_separation(n['position'] for n in c['nodes'])
            for node in c['nodes']:
                validate_woss_position(node['position'],net['woss']['water_depth_m'])
                for waypoint in node.get('waypoints',[]):validate_woss_position(waypoint[1:],net['woss']['water_depth_m'])
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
        if net['mac']['protocol'] in ('tdma','tdma_frame','ranging_tdma'):
            if net['mac']['ack']:raise ValueError('TDMA does not support the ALOHA ACK option')
            ranging=net['mac']['protocol']=='ranging_tdma'
            # Ranging-TDMA slots follow the native creation order, so there is no assignment.
            tdma=net['mac']['ranging_tdma' if ranging else 'tdma'];slots={} if ranging else tdma.get('slot_assignment',{})
            if slots and set(slots)!=set(ids):raise ValueError('Assign one slot to every node')
            if not slots and not ranging:
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
                frame_bytes=flow.get('native_packet_bytes',125) if flow.get('generator','python')!='python' else len(json.dumps(wire,separators=(',',':')))
                # Ranging-TDMA sends its ranging frame (4 bytes per peer plus 2) first in every own slot.
                duration=(frame_bytes+overhead)*8/bitrate+((4*(len(ids)-1)+2)*8/bitrate if ranging else 0)
                if duration>slot-tdma['guard_time_s']:raise ValueError('Frame does not fit its TDMA slot: increase frame duration or reduce payload')
        for f in c.get('flows',[]):
            if f.get('final_interval') is not None and f.get('stop') is None:
                raise ValueError('Variable interval requires flow stop')
            if f.get('interface','inherit') not in ('inherit',net['medium']):raise ValueError('Flow interface differs from the configured medium')
            if f.get('pattern','periodic') not in ('periodic','poisson','burst','events'):raise ValueError('Unsupported traffic pattern')
            if f.get('pattern')=='events' and (not f.get('events') or sorted(set(f['events']))!=f['events'] or any(t<f.get('start',1) or f.get('stop') is not None and t>=f['stop'] for t in f['events'])):
                raise ValueError('Traffic events must be unique, increasing and within the flow window')
            if f.get('pattern')=='burst' and (f.get('burst_count',3)-1)*f.get('burst_interval_s',.25)>=f.get('burst_period_s',5):
                raise ValueError('Burst duration must be shorter than its period')
        effective_interfaces(c)
        return c
    except (KeyError,TypeError,IndexError) as exc:
        raise ValueError('Invalid stack configuration: '+str(exc)) from exc


def render(config):
    c=validate(config);net=c['network'];mac=net['mac'];a=net['acoustic'];ids={n['id']:i+1 for i,n in enumerate(c['nodes'])}
    adapter,macclass,libs=MACS[mac['protocol']];routingclass,routinglib=ROUTING[net['routing']]
    values={'count':len(ids),'seed':net['seed'],'frequency':a['frequency_hz'],'bandwidth':a['bandwidth_hz'], 'bitrate':a['bitrate_bps'],'power':a['tx_power_db'],'ack':int(mac['ack']),'max_tries':mac['max_tx_tries'],'buffer_packets':mac['buffer_packets']}
    lines=['set '+k+' '+number(v) for k,v in values.items()]
    lines+=render_multiphy(c,number,PHYS)
    multi=effective_interfaces(c)
    if multi:libs=libs+['libuwmulti_stack_controller.so']
    environment=a.get('propagation','underwater') if net['medium']=='acoustic' else net['medium']
    lines.append('set environment_adapter '+environment)
    if environment in ('optical','em'):
        lines.append('set medium_parameters {'+' '.join(k+' '+number(int(v) if isinstance(v,bool) else v) for k,v in net[environment].items())+'}')
    if environment=='woss':
        w=net['woss'];lines.append('set woss_parameters {'+' '.join(k+' '+number(v) for k,v in w.items() if k!='ssp')+'}')
        lines.append('set woss_ssp {'+' '.join('{'+number(p['depth_m'])+' '+number(p['speed_mps'])+'}' for p in w['ssp'])+'}')
    lines.append('set bounded_queue '+str(int(mac['queue_mode']=='bounded')))
    lines+=['set mac_adapter '+adapter,'set mac_class '+macclass,'set routing_adapter '+net['routing'],'set routing_class '+routingclass,
            'set extra_libraries {'+' '.join(libs+(['libuwcbr.so'] if net['routing']=='sun' else [])+[routinglib])+'}',
            'set sound_speed '+number(a['sound_speed_mps'])]
    if net['routing']=='sun':
        lines.append('set sun_parameters {'+' '.join(k+' '+number(ids[v] if k=='sink' else int(v) if isinstance(v,bool) else v) for k,v in net['sun'].items())+'}')
    params=mac.get('tdma' if adapter=='tdma_frame' else adapter,{}) if adapter!='aloha' else {}
    allowed={'tdma':{'frame_duration_s','guard_time_s','max_packets_per_slot','slot_assignment'},'tdma_frame':{'frame_duration_s','guard_time_s','max_packets_per_slot','slot_assignment'},'csma_ca':{'queue_size','backoff_delta_s','backoff_max','cts_wait_s','data_wait_s','ack_wait_s'},'dacap':{'wait_costant_s','delta_d','t_min','tw_min','max_prop_delay_s'},'aloha':set(),'csburst':{'max_packets_per_burst','fixed_sensing_s','random_sensing_s'},'tokenbus':{'slot_time_s','min_token_hold_s','max_token_hold_s'},'ranging_tokenbus':{'slot_time_s','min_token_hold_s','max_token_hold_s'},'ranging_tdma':{'frame_duration_s','guard_time_s','max_packets_per_slot'}}
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
        if environment=='woss':lines.append('set initial_position('+str(i)+') {'+' '.join(number(v) for v in c['nodes'][i-1]['position'])+'}')
        ac=multi[i-1]['interfaces'][0]['acoustic'] if multi else node['acoustic'];lines.append('set phy_class('+str(i)+') '+({'woss':'WOSS/Module/MPhy/BPSK/HOLO','optical':'Module/UW/OPTICAL/PHY/HOLO','em':'Module/UW/ElectroMagnetic/PHY/HOLO'}.get(environment,PHYS[ac['phy']])))
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
    return '\n'.join(lines)+'\n'+render_native_applications(c,number)


if __name__=='__main__':
    import sys
    # Image build: python3 stack_builder.py --base-image "$DESERT_IMAGE"
    arguments=sys.argv[1:]
    print(engine_fingerprint(base_image=arguments[1] if arguments[:1]==['--base-image'] else None))
