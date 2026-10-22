"""Whitelist native application configuration; native timers generate all packets."""
import math


def native_flows(config):
    result=[]
    if len(config.get('flows',[]))>64:raise ValueError('At most 64 application flows are supported')
    for index,flow in enumerate(config.get('flows',[])):
        generator=flow.get('generator','python')
        if generator not in ('python','desert_cbr','desert_vbr'):raise ValueError('Unknown native application generator')
        if generator=='python':continue
        if flow.get('reply',False) or flow.get('message_type','data')!='data' or flow.get('pattern','periodic') not in ('periodic','poisson') or flow.get('final_interval') is not None:
            raise ValueError('Native generators require data, native timing, and no Python reply')
        values={key:flow.get(key,default) for key,default in [('interval',3),('native_period2_s',2),('native_duration1_s',5),('native_duration2_s',5),('native_packet_bytes',125)]}
        for key,value in values.items():
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid native '+key)
        size=values['native_packet_bytes']
        if size!=int(size) or not 16<=size<=2048:raise ValueError('Native packet length must be 16..2048 bytes')
        result.append((index,flow,values))
    return result


def render_native_applications(config,number):
    ids={node['id']:i+1 for i,node in enumerate(config['nodes'])}
    rows=[]
    for index,flow,values in native_flows(config):
        cls='Module/UW/CBR/HOLO' if flow['generator']=='desert_cbr' else 'Module/UW/VBR/HOLO'
        start=flow.get('start',1);stop=flow.get('stop') or config['duration']
        rows.append('{'+' '.join([str(index),cls,str(ids[flow['source']]),str(ids[flow['destination']]),number(start),number(stop),str(int(flow.get('pattern')=='poisson'))]+[number(values[k]) for k in ('interval','native_packet_bytes','native_period2_s','native_duration1_s','native_duration2_s')])+'}')
    return 'set native_flows {'+' '.join(rows)+'}\n'
