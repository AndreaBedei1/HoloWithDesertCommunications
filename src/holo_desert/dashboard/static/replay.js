import {$,esc,number} from './ui.js';
import {drone,typeName,interfaceLabel} from './presentation.js';

// Replay of a run inside the browser: the map and the event feed are redrawn at a chosen simulated time t,
// using only what was recorded (timed HoloOcean poses and the DESERT events of each message). It never
// pauses or alters the simulation, and it covers the messages kept in the state (the most recent 500).
const replay={live:true,t:0,playing:false,speed:1,wall:0};
const RX_ERRORS=['noise_error','interference_error','not_synchronized'];
export const isLive=()=>replay.live;
export const resetReplay=()=>Object.assign(replay,{live:true,t:0,playing:false});
export const viewTime=s=>replay.live?(s.time||0):Math.min(replay.t,s.time||0);

const pose=([,x,y,z,yaw])=>({x,y,z,yaw});
// Linear interpolation between the recorded samples around t; the heading of the earlier sample.
function poseAt(samples,t){
  if(!samples?.length)return null;
  if(t<=samples[0][0])return pose(samples[0]);
  if(t>=samples.at(-1)[0])return pose(samples.at(-1));
  let lo=0,hi=samples.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(samples[mid][0]<=t)lo=mid;else hi=mid}
  const a=samples[lo],b=samples[hi],f=(t-a[0])/(b[0]-a[0]);
  return {x:a[1]+(b[1]-a[1])*f,y:a[2]+(b[2]-a[2])*f,z:a[3]+(b[3]-a[3])*f,yaw:a[4]};
}
// A message as it stood at time t: later events removed and its status recomputed from what remains.
function packetAt(p,t){
  const events=p.events.filter(e=>e.time<=t),has=name=>events.some(e=>e.event===name);
  const status=p.receive_time!=null&&p.receive_time<=t?'received':has('ttl_expired')?'timeout_unknown_cause':has('phy_tx_start')?'phy_tx_observed':has('app_tx')||has('forward')?'in_flight':'queued';
  return status==='received'?{...p,events,status}:{...p,events,status,receive_time:undefined,delay:null};
}
export function viewAt(s){
  if(replay.live||!s.configuration)return s;
  const t=viewTime(s),packets=(s.packets||[]).filter(p=>p.creation_time<=t).map(p=>packetAt(p,t));
  const fleet=Object.fromEntries(Object.entries(s.fleet||{}).map(([n,current])=>[n,poseAt(s.history?.[n],t)||current]));
  const trails=Object.fromEntries(Object.entries(s.history||{}).map(([n,h])=>[n,h.filter(p=>p[0]<=t).map(p=>[p[1],p[2]])]));
  const edges=new Map();for(const p of packets)if(p.status==='received')edges.set(p.source+'>'+p.destination,{source:p.source,destination:p.destination,last_receive:p.receive_time});
  const nodes=Object.keys(fleet),distances_m={};
  nodes.forEach((a,i)=>nodes.slice(i+1).forEach(b=>distances_m[a+'>'+b]=Math.hypot(fleet[a].x-fleet[b].x,fleet[a].y-fleet[b].y,fleet[a].z-fleet[b].z)));
  return {...s,time:t,fleet,trails,packets,recorded_packets:s.packets,edges:[...edges.values()],distances_m,
    observations:packets.flatMap(p=>p.events.filter(e=>['forward','phy_tx_start','phy_rx_start','phy_rx_end','rx'].includes(e.event)))};
}
// Frames on the air around time t, from the recorded events of each message. A frame is drawn from its
// observed PHY start to the observed end of reception at the receiver (transmission plus propagation);
// the dot only marks the elapsed fraction of that recorded interval, it is not a simulated wavefront.
export function transmissionsAt(s,t){
  const out=[];
  for(const p of s.recorded_packets||s.packets||[])for(const tx of p.events){
    if(tx.event!=='phy_tx_start'||tx.time>t||t-tx.time>60||!tx.node_id)continue;
    const rx=p.events.filter(r=>r.event==='phy_rx_end'&&r.transmitter_id===tx.node_id&&r.time>=tx.time&&(!tx.next_hop_id||r.node_id===tx.next_hop_id));
    const first=rx.length?Math.min(...rx.map(r=>r.time)):null,next=p.events.find(e=>e.event==='phy_tx_start'&&e.node_id===tx.node_id&&e.time>tx.time);
    const targets=tx.next_hop_id?[{to:tx.next_hop_id,r:rx[0]}]:rx.filter(r=>r.time<(next?.time??Infinity)).map(r=>({to:r.node_id,r}));
    for(const {to,r}of targets){
      const end=r?r.time:tx.time+(tx.duration_s||1);if(t>end+.8||to===tx.node_id)continue;
      const outcome=r&&r.time<=t?r.outcome:'in_flight';
      out.push({packet:p.id,type:p.type,from:tx.node_id,to,start:tx.time,end,outcome,interface:tx.interface_index,
        frac:Math.min(1,Math.max(0,(t-tx.time)/Math.max(1e-6,end-tx.time))),observedEnd:!!r});
    }
    if(!targets.length&&first===null&&t-tx.time<1.2)out.push({packet:p.id,type:p.type,from:tx.node_id,to:null,start:tx.time,outcome:'in_flight'});
  }
  return out;
}
const outcomeText=o=>({decoded:'decoded',in_flight:'on the air',noise_error:'not decoded (noise)',interference_error:'not decoded (interference branch)',not_synchronized:'not decoded (not synchronised)'}[o]||'outcome: '+o);
export const transmissionLabel=x=>typeName(x.type||'frame')+' · '+outcomeText(x.outcome);
export const transmissionTone=x=>x.outcome==='in_flight'?'info':x.outcome==='decoded'?'success':RX_ERRORS.includes(x.outcome)?'error':'neutral';

function describe(p,e){
  const who=drone(e.node_id),iface=e.interface_index>0?' on '+interfaceLabel(e.interface_index):'';
  switch(e.event){
    case 'app_tx':return who+' hands the message to the network stack';
    case 'forward':return who+' routes it to '+drone(e.next_hop_id);
    case 'phy_tx_start':return who+' starts transmitting'+iface+(e.next_hop_id?' to '+drone(e.next_hop_id):'');
    case 'phy_rx_end':return e.outcome==='decoded'?who+' decodes the frame from '+drone(e.transmitter_id):who+' does not decode the frame from '+drone(e.transmitter_id)+' ('+esc(e.outcome||'no outcome recorded')+')';
    case 'delivered':return 'Delivered to '+who+' · end-to-end latency '+number(e.time-p.creation_time,3)+' s';
    case 'native_app_rx':return 'Delivered to '+who+' by the native application';
    case 'ttl_expired':return 'Expired at its TTL · cause not recorded by DESERT';
    default:return null;
  }
}
// The last recorded events up to time t, newest first; each one opens its message.
export function replayFeed(s,t){
  const rows=[];
  for(const p of s.recorded_packets||s.packets||[]){
    if(p.creation_time<=t&&t-p.creation_time<=6)rows.push({time:p.creation_time,p,text:drone(p.source)+' creates a '+typeName(p.type).toLowerCase()+' message for '+drone(p.destination)});
    for(const e of p.events){if(e.time>t||t-e.time>6)continue;const text=describe(p,e);if(text)rows.push({time:e.time,p,text})}
  }
  rows.sort((a,b)=>b.time-a.time);
  if(!rows.length)return '<li class="replay-empty">No message events in the 6 s before this instant.</li>';
  return rows.slice(0,6).map(r=>'<li><button type="button" class="text-button" data-packet="'+esc(r.p.id)+'"><time>'+number(r.time,2)+' s</time> '+esc(r.text)+' <span class="micro">· '+esc(typeName(r.p.type))+' '+esc(r.p.id.slice(0,8))+'</span></button></li>').join('');
}

export function renderReplay(s){
  const end=s.time||0,t=viewTime(s),has=!!s.configuration&&end>0;
  $('#replay').hidden=!has;if(!has)return;
  const range=$('#replay-time');range.max=String(end);if(document.activeElement!==range)range.value=String(t);
  $('#replay-live').setAttribute('aria-pressed',String(replay.live));$('#replay-live').textContent=replay.live?'● Live':'Go live';
  $('#replay-play').textContent=replay.playing?'Ⅱ Pause replay':'▶ Play replay';
  $('#replay-clock').textContent=(replay.live?'Live · ':'Replay · ')+'t = '+number(t,2)+' s of '+number(end,2)+' s';
  $('#replay-note').hidden=replay.live;
}
export function bindReplay(frame,getState){
  const seek=t=>{const end=getState().time||0;replay.t=Math.max(0,Math.min(end,t));replay.live=false;frame()};
  const loop=now=>{if(!replay.playing)return;const s=getState(),dt=(now-replay.wall)/1000;replay.wall=now;
    replay.t+=dt*replay.speed;if(replay.t>=(s.time||0)){replay.playing=false;replay.live=true}frame();if(replay.playing)requestAnimationFrame(loop)};
  $('#replay-play').onclick=()=>{if(replay.playing){replay.playing=false;frame();return}
    if(replay.live){replay.live=false;replay.t=0}replay.playing=true;replay.wall=performance.now();requestAnimationFrame(loop);frame()};
  $('#replay-live').onclick=()=>{replay.live=true;replay.playing=false;frame()};
  $('#replay-start').onclick=()=>{replay.playing=false;seek(0)};
  $('#replay-back').onclick=()=>{replay.playing=false;seek(viewTime(getState())-1)};
  $('#replay-forward').onclick=()=>{replay.playing=false;seek(viewTime(getState())+1)};
  $('#replay-time').oninput=e=>{replay.playing=false;seek(Number(e.target.value))};
  $('#replay-speed').onchange=e=>{replay.speed=Number(e.target.value)};
}
