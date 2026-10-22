"""Whitelist configuration for the installed native PHY master/slave controller."""
import math
import re

ACOUSTIC_FIELDS={'tx_power_db','bitrate_bps','frequency_hz','bandwidth_hz','phy','spreading','shipping','wind_speed_mps','rx_snr_penalty_db','acquisition_threshold_db'}


def effective_interfaces(config):
    net=config['network'];multi=net.get('multiphy')
    if multi is None:return []
    if not isinstance(multi,dict) or set(multi)-{'interfaces','policy','initial_interface','master','thresholds','alpha'}:raise ValueError('Unsupported multiPHY configuration')
    multi.setdefault('policy','manual');multi.setdefault('master','auv_01');multi.setdefault('thresholds',[]);multi.setdefault('alpha',.5)
    interfaces=multi.get('interfaces',[])
    if not isinstance(interfaces,list) or not 2<=len(interfaces)<=3:raise ValueError('MultiPHY requires two or three acoustic interfaces')
    ids=[]
    for interface in interfaces:
        if not isinstance(interface,dict) or set(interface)-{'id','acoustic'} or not isinstance(interface.get('id'),str) or not re.fullmatch('[a-z][a-z0-9_]{0,15}',interface['id']):raise ValueError('Invalid multiPHY interface ID')
        ids.append(interface['id'])
    if len(set(ids))!=len(ids) or multi.get('initial_interface') not in ids:raise ValueError('MultiPHY interface IDs must be unique and initial_interface must exist')
    if net.get('medium','acoustic')!='acoustic' or net['acoustic'].get('propagation','underwater')!='underwater' or net['mac']['protocol']!='csma_aloha' or net.get('routing','static')!='static' or net['mac'].get('ack',False):raise ValueError('MultiPHY requires analytic acoustic BPSK, CSMA-ALOHA without ACK and StaticRouting')
    if multi['policy'] not in ('manual','received_power'):raise ValueError('Unsupported multiPHY controller policy')
    alpha=multi['alpha']
    if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not math.isfinite(alpha) or not 0<=alpha<=1:raise ValueError('MultiPHY alpha must be within 0..1')
    thresholds=multi['thresholds'];edges=set()
    if not isinstance(thresholds,list):raise ValueError('Invalid multiPHY thresholds')
    for threshold in thresholds:
        if not isinstance(threshold,dict) or set(threshold)!={'from_interface','to_interface','power_linear'}:raise ValueError('Invalid multiPHY threshold')
        a,b,p=threshold['from_interface'],threshold['to_interface'],threshold['power_linear']
        if a not in ids or b not in ids or abs(ids.index(a)-ids.index(b))!=1 or (a,b) in edges or isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or p<=0:raise ValueError('MultiPHY thresholds require unique adjacent interfaces and positive native linear power')
        edges.add((a,b))
    if multi['policy']=='received_power':
        expected={(a,b) for a,b in zip(ids,ids[1:])}|{(b,a) for a,b in zip(ids,ids[1:])}
        if edges!=expected:raise ValueError('Automatic multiPHY needs thresholds for both directions between adjacent interfaces')
        if multi['master'] not in [n['id'] for n in config['nodes']]:raise ValueError('Unknown multiPHY master node')
    elif thresholds:raise ValueError('Manual multiPHY does not consume switching thresholds')
    result=[]
    for node in config['nodes']:
        communication=node.get('communication') or {}
        available=communication.get('interfaces')
        if available is None:available=ids
        overrides=communication.get('interface_overrides') or {}
        if not isinstance(available,list) or not available or len(set(available))!=len(available) or set(available)-set(ids) or not isinstance(overrides,dict) or set(overrides)-set(available):raise ValueError('Unknown or duplicate per-node multiPHY interface')
        if multi['initial_interface'] not in available:raise ValueError('Every node must provide the initial multiPHY interface')
        if multi['policy']=='received_power' and set(available)!=set(ids):raise ValueError('Automatic multiPHY requires all interfaces at every node')
        effective=[]
        for index,interface in enumerate(interfaces,1):
            if interface['id'] not in available:continue
            acoustic=dict(net['acoustic'])
            for override in (communication.get('acoustic') or {},interface.get('acoustic') or {},overrides.get(interface['id']) or {}):
                if not isinstance(override,dict) or set(override)-ACOUSTIC_FIELDS:raise ValueError('Unsupported multiPHY acoustic override')
                acoustic.update({k:v for k,v in override.items() if v is not None})
            bounds={'tx_power_db':(0,200),'bitrate_bps':(1e-12,1e9),'frequency_hz':(1e-12,1e12),'bandwidth_hz':(1e-12,1e12),'spreading':(1e-12,3),'shipping':(0,1),'wind_speed_mps':(0,1e6),'rx_snr_penalty_db':(-1e6,1e6),'acquisition_threshold_db':(-1e6,1e6)}
            for key,(low,high) in bounds.items():
                v=acoustic[key]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError('Invalid multiPHY '+key)
            if acoustic['phy'] not in ('bpsk_upstream','bpsk_corrected') or acoustic['bandwidth_hz']>=2*acoustic['frequency_hz']:raise ValueError('Invalid multiPHY acoustic band/PHY')
            effective.append({'id':interface['id'],'index':index,'acoustic':acoustic})
        for i,a in enumerate(effective):
            for b in effective[i+1:]:
                x,y=a['acoustic'],b['acoustic']
                if abs(x['frequency_hz']-y['frequency_hz'])<=(x['bandwidth_hz']+y['bandwidth_hz'])/2:raise ValueError('MultiPHY interfaces require disjoint frequency bands')
        result.append({'id':node['id'],'interfaces':effective})
    return result


def render_multiphy(config,number,phys):
    effective=effective_interfaces(config)
    lines=['set multiphy_enabled '+str(int(bool(effective)))]
    if not effective:return lines
    multi=config['network']['multiphy'];ids=[i['id'] for i in multi['interfaces']]
    lines+=['set multi_interface_ids {'+' '.join(ids)+'}','set multi_initial '+str(ids.index(multi['initial_interface'])+1),
            'set multi_policy '+multi['policy'],'set multi_master '+str(next((i for i,n in enumerate(config['nodes'],1) if n['id']==multi['master']),1)),
            'set multi_alpha '+number(multi['alpha'])]
    lines.append('set multi_thresholds {'+' '.join('{%d %d %s}'%(ids.index(t['from_interface'])+1,ids.index(t['to_interface'])+1,number(t['power_linear'])) for t in multi['thresholds'])+'}')
    for i,node in enumerate(effective,1):
        lines.append('set multi_indices(%d) {'%i+' '.join(str(x['index']) for x in node['interfaces'])+'}')
        for interface in node['interfaces']:
            a=interface['acoustic'];key='%d,%d'%(i,interface['index'])
            lines+=['set multi_phy_class('+key+') '+phys[a['phy']],
                    'set multi_settings('+key+') {'+' '.join(k+' '+number(a[k]) for k in ('tx_power_db','bitrate_bps','frequency_hz','bandwidth_hz','spreading','shipping','wind_speed_mps','rx_snr_penalty_db','acquisition_threshold_db'))+'}']
    return lines
