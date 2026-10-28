import {$,esc,number,statusName,preserve} from './ui.js';
import {drone,typeName,eventLabel,eventTone,help,interfaceLabel,powerLabel} from './presentation.js';
import {moduleName} from './configuration.js';

const nodeOf=e=>e.node_id||(typeof e.node==='string'?e.node:null);
const RX_ERRORS=['noise_error','interference_error','not_synchronized'];
const rel=(t,t0)=>'+'+number(t-t0,3)+' s';
export const isNative=p=>p.size_kind==='native_packet';
// Hops seen by the network probes (forward events) and the interface of the first transmission.
export function observedPath(p){
  const hops=[p.source];for(const e of p.events)if(e.event==='forward'&&e.next_hop_id&&hops.at(-1)!==e.next_hop_id)hops.push(e.next_hop_id);
  const tx=p.events.find(e=>e.event==='phy_tx_start'&&e.interface_index>0);
  return {hops:hops.length>1?hops:[],interface:tx?interfaceLabel(tx.interface_index)+(tx.medium?' · '+tx.medium:''):null};
}
// One record per addressed hop (transmitter → next hop), built only from forward, PHY and delivery events.
// decoded/error: PHY outcome observed at the next hop; reached: the next hop later forwarded or delivered it (inferred).
export function messageHops(p){
  const hops=new Map(),hop=(from,to)=>{const k=from+'>'+to;if(!hops.has(k))hops.set(k,{from,to,tx:0,status:'routed',txTime:null,rxTime:null});return hops.get(k)};
  for(const e of p.events){
    if(e.event==='forward'&&e.node_id&&e.next_hop_id&&e.node_id!==e.next_hop_id)hop(e.node_id,e.next_hop_id);
    if(e.event==='phy_tx_start'&&e.node_id&&e.next_hop_id&&e.node_id!==e.next_hop_id){const h=hop(e.node_id,e.next_hop_id);h.tx++;h.txTime??=e.time;if(h.status==='routed')h.status='sent'}
    if(e.event==='phy_rx_end'&&e.transmitter_id&&e.node_id){const h=hops.get(e.transmitter_id+'>'+e.node_id);if(h&&e.outcome==='decoded'){h.status='decoded';h.rxTime??=e.time}else if(h&&RX_ERRORS.includes(e.outcome)&&h.status!=='decoded')h.status='error'}
  }
  for(const h of hops.values())if(h.status==='routed'&&p.events.some(e=>e.event==='phy_tx_start'&&nodeOf(e)===h.from&&!e.next_hop_id)){h.status='sent_unaddressed';h.txTime=p.events.find(e=>e.event==='phy_tx_start'&&nodeOf(e)===h.from).time}
  for(const h of hops.values())if(h.status!=='decoded'&&p.events.some(e=>nodeOf(e)===h.to&&['forward','rx','delivered','native_app_rx'].includes(e.event)&&e.time>=(h.txTime??-Infinity)))h.status='reached';
  return [...hops.values()];
}
export const HOP_STATUS={decoded:['Decoded at the next hop','success','observed'],reached:['Next hop forwarded or delivered it','success','inferred'],error:['PHY reception error at the next hop','error','observed'],sent:['Transmitted, no reception recorded','info','observed'],sent_unaddressed:['Transmitted by this drone; the PHY does not expose the next hop','info','inferred'],routed:['Routed, no PHY transmission recorded','neutral','observed']};
// Who took part in the message, and its final state, from the recorded events only.
export function lifecycle(p){
  const hops=messageHops(p),relays=[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id&&![p.source,p.destination].includes(e.node_id)).map(e=>e.node_id))];
  const intended=new Set([p.destination,...relays,...hops.map(h=>h.to)]),acquired=e=>e.event==='phy_rx_end'||(e.event==='phy_rx_start'&&!['below_acquisition_threshold','wrong_modulation'].includes(e.outcome));
  const receivers=[...new Set(p.events.filter(e=>e.event==='phy_rx_end'&&e.outcome==='decoded'&&intended.has(nodeOf(e))).map(nodeOf))];
  const overheard=[...new Set(p.events.filter(e=>acquired(e)&&nodeOf(e)&&!intended.has(nodeOf(e))).map(nodeOf))];
  const outcomes=p.events.some(e=>e.event==='phy_rx_end'&&e.outcome),errorOutcomes=new Set(p.events.filter(e=>e.event==='phy_rx_end'&&RX_ERRORS.includes(e.outcome)).map(e=>e.outcome));
  const late=p.events.find(e=>e.event==='late_receive'),phyError=p.status!=='received'&&hops.some(h=>h.status==='error');
  const final=p.status==='received'?'delivered':p.status==='timeout_unknown_cause'?'expired':'pending';
  const tx=p.events.find(e=>e.event==='phy_tx_start'),txEnd=tx&&p.events.find(e=>e.event==='phy_tx_end'&&nodeOf(e)===nodeOf(tx)&&e.time>=tx.time);
  return {hops,relays,receivers,overheard,late,phyError,final,tx,txEnd,outcomes,errorOutcomes,order:[...new Set([p.source,...relays,p.destination,...overheard,...p.events.map(nodeOf).filter(Boolean)])]};
}
export const packetTone=p=>p.status==='received'?'success':p.status==='timeout_unknown_cause'?'warning':p.status==='phy_tx_observed'?'info':'neutral';
export const stateHTML=p=>'<span class="state-text '+packetTone(p)+'"><span aria-hidden="true">'+({success:'✓',warning:'◷',info:'↗',neutral:'·'}[packetTone(p)])+'</span>'+esc(statusName(p.status))+'</span>';
export function eventTimeline(events,t0=null){
  return '<ol class="timeline">'+events.map(e=>{const level=e.event.startsWith('phy_control_')?'MAC control':e.event.startsWith('phy_')?'PHY':e.event==='forward'?'Network':'Application',node=nodeOf(e);return '<li class="'+eventTone(e)+'"><b>'+esc(eventLabel(e))+'</b><span class="event-level">'+level+'</span><time>'+(t0==null?'':esc(rel(e.time,t0))+' · ')+'t = '+number(e.time,3)+' s'+(node?' · '+esc(drone(node)):'')+'</time>'+(e.next_hop_id?'<small>Next hop: '+esc(drone(e.next_hop_id))+'</small>':'')+(e.transmitter_id&&e.event.startsWith('phy_rx')?'<small>From: '+esc(drone(e.transmitter_id))+'</small>':'')+(e.state?'<small>State: '+esc(e.state)+'</small>':'')+(e.interface_index>0?'<small>Interface: '+esc(interfaceLabel(e.interface_index))+'</small>':'')+(powerLabel(e)?'<small>Applied power: '+esc(powerLabel(e))+'</small>':'')+'</li>'}).join('')+'</ol>';
}
// Compact lanes: one row per drone, PHY transmissions as bars, every other event as a dot.
function lanes(p,events,order){
  const t0=p.creation_time,t1=Math.max(t0+1e-3,...events.map(e=>e.time)),span=t1-t0,x=t=>((t-t0)/span*100).toFixed(2)+'%';
  const tone=e=>e.event==='phy_rx_end'&&e.outcome==='decoded'?'success':eventTone(e);
  const mark=e=>'<i class="lane-mark '+tone(e)+'" style="left:'+x(e.time)+'" title="'+esc(eventLabel(e)+' · '+rel(e.time,t0))+'"></i>';
  const row=(label,own)=>'<div class="lane"><span>'+esc(label)+'</span><div class="lane-track">'+own.filter(e=>e.event==='phy_tx_start').map(s=>{const end=own.find(e=>e.event==='phy_tx_end'&&e.time>=s.time);return end?'<i class="lane-bar" style="left:'+x(s.time)+';width:'+Math.max(.5,(end.time-s.time)/span*100).toFixed(2)+'%"></i>':''}).join('')+own.map(mark).join('')+'</div></div>';
  const loose=events.filter(e=>!nodeOf(e));
  return '<div class="lanes" role="img" aria-label="Events per drone over time, from generation">'+order.map(n=>row(drone(n),events.filter(e=>nodeOf(e)===n))).join('')+(loose.length?row('Message',loose):'')+'<div class="lane-axis"><span>+0 s</span><span>'+esc(rel(t1,t0))+'</span></div></div>';
}
const MEDIUM={acoustic:'Acoustic',optical:'Optical',em:'Electromagnetic'};
const tag=kind=>'<span class="evidence '+kind+'">'+kind+'</span>';
const facts=rows=>'<dl>'+rows.filter(Boolean).map(([k,v,kind])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+(kind?' '+tag(kind):'')+'</dd>').join('')+'</dl>';
const FINAL={delivered:'Delivered to the application',expired:'Expired: the TTL ran out, cause unknown',pending:'Pending: no delivery or expiry yet'};
export function packetDetails(packet,s={}){
  if(!packet)return '<div class="context-placeholder"><div class="empty-symbol">↗</div><h3>Every message has a story</h3><p>Select a row to see its transmissions, any relays and the delivery, with the times observed by the network.</p></div>';
  const p=packet,t0=p.creation_time,l=lifecycle(p),native=isNative(p),config=s.configuration?.network,events=[{event:'generated',time:t0,node_id:p.source},...p.events];
  const medium=l.tx?.medium,iface=l.tx?.interface_index>0?interfaceLabel(l.tx.interface_index):null,list=nodes=>nodes.length?nodes.map(drone).join(', '):'None recorded';
  const technology=iface?[iface+(medium?' · '+(MEDIUM[medium]||medium):''),'observed']:medium?[MEDIUM[medium]||medium,'observed']:config?[config.multiphy?'Multi-PHY · interface not recorded':MEDIUM[config.medium||'acoustic']||config.medium,'configured']:null;
  const routing=config?{static:'Static',flooding:'Flooding',sun:'SUN',position_based:'Position-based'}[config.routing||'static']||config.routing:null;
  const hopRows=l.hops.map((h,i)=>{const [label,tone,kind]=HOP_STATUS[h.status];return '<li class="'+tone+'"><b>Hop '+(i+1)+' · '+esc(drone(h.from)+' → '+drone(h.to))+'</b><small>'+esc(label)+' '+'</small>'+tag(kind)+(h.tx>1?'<small>'+h.tx+' PHY transmissions (including retransmissions)</small>':'')+(h.txTime!=null&&h.rxTime!=null?'<small>TX start → decoded: '+number(h.rxTime-h.txTime,3)+' s </small>'+tag('inferred'):'')+'</li>'}).join('');
  return '<h2>'+esc(drone(p.source))+' → '+esc(drone(p.destination))+'</h2><p class="micro" style="margin-top:7px">'+esc(typeName(p.type))+' · '+number(p.size,0)+(native?' packet bytes · native DESERT traffic':' payload bytes · application message')+'</p>'
    +'<div class="final-state '+packetTone(p)+'">'+stateHTML(p)+'<span>'+esc(FINAL[l.final])+(l.late?' · a copy arrived after the TTL ('+rel(l.late.time,t0)+')':'')+'</span></div>'
    +(l.phyError?'<p class="micro final-note">A PHY reception error was recorded at a next hop. This is the PHY outcome of that frame, not a proven cause of the missed delivery. '+(l.errorOutcomes.has('interference_error')?help('Interferenza'):help('PHY'))+'</p>':'')
    +(p.status==='timeout_unknown_cause'?'<p class="micro">The cause of the missed delivery remains unknown. '+help('Scadenza')+'</p>':'')
    +(p.omitted_events?'<p class="micro final-note">Only the latest '+p.events.length+' events are kept on screen ('+p.omitted_events+' earlier ones are in the exportable history): first transmission, hops and retransmission counts below may be incomplete.</p>':'')+'<h3>Timeline</h3>'+lanes(p,events,l.order)+'<p class="micro lane-key"><i class="lane-bar"></i> PHY transmission <i class="lane-mark info"></i> TX / forwarding <i class="lane-mark success"></i> decoded / delivered <i class="lane-mark error"></i> PHY error <i class="lane-mark warning"></i> expiry</p>'
    +(hopRows?'<h3>Hops</h3><ol class="timeline hops">'+hopRows+'</ol>':'')
    +'<h3>Lifecycle '+help('Evidence')+'</h3>'+facts([['Message ID',p.id.slice(0,13),''],['Traffic',native?'Native DESERT '+String(p.generator||p.type).replace('desert_','').toUpperCase()+' (no Python TTL)':'Application (Python)',''],technology&&['Technology',...technology],['MAC',moduleName('mac',p.protocol),'configured'],routing&&['Routing',routing,'configured'],['Relays',list(l.relays),'observed'],l.outcomes||l.receivers.length?['Decoded by',list(l.receivers),'observed']:['Decoded by','Outcome not exposed by the PHY',''],['Overheard by',list(l.overheard),'observed']])
    +'<h3>Times</h3>'+facts([['Generated at','t = '+number(t0,3)+' s','observed'],p.physical_tx_time!=null&&['First PHY transmission',rel(p.physical_tx_time,t0),'observed'],l.txEnd?['First TX duration',number(l.txEnd.time-l.tx.time,3)+' s','observed']:l.tx?.duration_s!=null?['First TX duration (reported by the PHY at TX start)',number(l.tx.duration_s,3)+' s','observed']:null,p.delay!=null?['End-to-end latency',number(p.delay,3)+' s','observed']:['End-to-end latency',p.status==='received'?'Not available':'Not delivered',''],!native&&p.deadline!=null&&['TTL deadline','t = '+number(p.deadline,3)+' s','configured']])
    +'<h3>Event sequence</h3>'+eventTimeline(events,t0)+(p.omitted_events?'<p class="micro">'+p.omitted_events+' earlier events in the complete exportable history.</p>':'')
    +'<details><summary>Technical details and raw data</summary>'+facts([['Full ID',p.id,''],[native?'Packet size':'Payload / envelope',native?p.size+' B':p.size+' / '+p.wire_size+' B',''],['Final delivery',p.receive_time==null?'N/A':'t = '+number(p.receive_time,3)+' s',p.receive_time==null?'':'observed'],['Individual MAC discard','Not observable','']])+p.events.filter(e=>e.event.startsWith('phy_')).map(phyDetails).join('')+'<pre>'+esc(JSON.stringify(p,null,2))+'</pre></details>';
}
function phyDetails(event){
  const power=value=>value==null?'N/A':Number(value).toExponential(5),values=[];
  for(const [key,label]of [['pt','Pt · transmitted'],['pr','Pr · received'],['pn','Pn · noise'],['pi','Pi · interference']])if(event[key]!=null)values.push([label+' [a.u.]',power(event[key])]);
  for(const [key,label]of [['phy_bits','PHY size [bit]'],['phy_tx_time','PHY TX · absolute time [s]'],['phy_rx_time','PHY RX · absolute time [s]'],['duration_s','PHY duration [s]'],['snr_db','Raw SNR Pr/Pn [dB]'],['rx_snr_penalty_db','Configured SNR penalty [dB]']])if(event[key]!=null)values.push([label,number(event[key],key==='phy_bits'?0:6)]);
  if(event.snr_db!=null&&event.rx_snr_penalty_db!=null)values.push(['SNR after penalty [dB]',number(event.snr_db+event.rx_snr_penalty_db,6),'inferred']);
  if(event.phy_patch_id!=null)values.push(['Patch PHY',event.phy_patch_id]);
  if(!values.length)return '';
  return '<section class="phy-diagnostics"><h4>'+esc(eventLabel(event))+' · t = '+number(event.time,3)+' s</h4><p class="micro">Linear powers in DESERT normalised acoustic units (a.u.). TX/RX times are absolute, not latencies.</p>'+facts(values)+'</section>';
}
const interfacesOf=p=>new Set(p.events.filter(e=>e.event==='phy_tx_start'&&e.interface_index>0).map(e=>String(e.interface_index)));
const value=id=>$(id)?.value||'';
let lastRows='';
export function renderPackets(s,selected,onSelect){
  const filter=value('#filter').toLowerCase(),node=value('#packet-node'),status=value('#packet-status'),event=value('#packet-event'),destination=value('#packet-destination'),type=value('#packet-type'),iface=value('#packet-interface');
  const from=value('#packet-from')===''?-Infinity:Number(value('#packet-from')),to=value('#packet-to')===''?Infinity:Number(value('#packet-to'));
  const packets=(s.packets||[]).filter(p=>(!filter||[p.id,p.source,p.destination,p.type,p.payload_hex].join(' ').toLowerCase().includes(filter))&&(!node||p.source===node||p.destination===node||p.events.some(e=>e.node_id===node))&&(!status||p.status===status)&&(!event||p.events.some(e=>e.event===event))&&(!destination||p.destination===destination)&&(!type||p.type===type)&&(!iface||interfacesOf(p).has(iface))&&p.creation_time>=from&&p.creation_time<=to);
  $('#packet-count').textContent=packets.length+' of '+(s.packets||[]).length+' messages';
  const html=packets.slice().reverse().map(p=>'<tr tabindex="0" data-id="'+esc(p.id)+'" class="'+(selected===p.id?'selected':'')+'" aria-selected="'+(selected===p.id)+'"><td>'+esc(drone(p.source)+' → '+drone(p.destination))+'<span class="message-id">'+esc(p.id.slice(0,8))+' · '+number(p.creation_time,2)+' s</span></td><td>'+(path=>'<span class="path">'+(path.hops.length?esc(path.hops.map(drone).join(' → ')):'—')+'</span>'+(path.interface?'<span class="message-id">'+esc(path.interface)+'</span>':''))(observedPath(p))+'</td><td>'+esc(typeName(p.type))+(isNative(p)?'<span class="message-id">native DESERT</span>':'')+'</td><td>'+stateHTML(p)+'</td><td>'+(p.delay==null?'—':number(p.delay,3)+' s')+'</td></tr>').join('')||'<tr><td colspan="5"><div class="empty-inline">'+((s.packets||[]).length?'No messages match the filters.':'Messages will appear once the simulation starts.')+'</div></td></tr>';
  // Rows are replaced only when they change, so focus and scroll survive the periodic refresh.
  const body=$('#packet-rows');
  if(html!==lastRows||!body.firstElementChild){const focused=document.activeElement?.closest?.('#packet-rows [data-id]')?.dataset.id;body.innerHTML=html;lastRows=html;
    body.querySelectorAll('[data-id]').forEach(row=>{row.onclick=()=>onSelect(row.dataset.id);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(row.dataset.id)}}});
    if(focused)body.querySelector('[data-id="'+CSS.escape(focused)+'"]')?.focus()}
  preserve($('#packet-details'),packetDetails((s.packets||[]).find(p=>p.id===selected),s));
}
