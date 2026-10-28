import {$,esc,number,fields,statusName,preserve} from './ui.js';
import {drone,typeName,eventLabel,eventTone,help,interfaceLabel,powerLabel} from './presentation.js';

// Hops seen by the network probes (forward events) and the interface of the first transmission.
export function observedPath(p){
  const hops=[p.source];for(const e of p.events)if(e.event==='forward'&&e.next_hop_id&&hops.at(-1)!==e.next_hop_id)hops.push(e.next_hop_id);
  const tx=p.events.find(e=>e.event==='phy_tx_start'&&e.interface_index>0);
  return {hops:hops.length>1?hops:[],interface:tx?interfaceLabel(tx.interface_index)+(tx.medium?' · '+(tx.medium==='optical'?'optical':tx.medium):''):null};
}
export const packetTone=p=>p.status==='received'?'success':p.status==='timeout_unknown_cause'?'warning':p.status==='phy_tx_observed'?'info':'neutral';
export const stateHTML=p=>'<span class="state-text '+packetTone(p)+'"><span aria-hidden="true">'+({success:'✓',warning:'◷',info:'↗',neutral:'·'}[packetTone(p)])+'</span>'+esc(statusName(p.status))+'</span>';
export function eventTimeline(events){
  return '<ol class="timeline">'+events.map(e=>{const level=e.event.startsWith('phy_')?'PHY':e.event==='forward'?'Network':'Application',node=e.node_id||(typeof e.node==='string'?e.node:null);return '<li class="'+eventTone(e)+'"><b>'+esc(eventLabel(e))+'</b><span class="event-level">'+level+'</span><time>'+number(e.time,3)+' s'+(node?' · '+esc(drone(node)):'')+'</time>'+(e.next_hop_id?'<small>Next hop: '+esc(drone(e.next_hop_id))+'</small>':'')+(e.state?'<small>State: '+esc(e.state)+'</small>':'')+(e.interface_index>0?'<small>Interface: '+esc(interfaceLabel(e.interface_index))+'</small>':'')+(powerLabel(e)?'<small>Applied power: '+esc(powerLabel(e))+'</small>':'')+'</li>'}).join('')+'</ol>';
}
function phyDetails(event){
  const power=value=>value==null?'N/A':Number(value).toExponential(5);
  const values={};
  for(const [key,label]of [['pt','Pt · transmitted'],['pr','Pr · received'],['pn','Pn · noise'],['pi','Pi · interference']])if(event[key]!=null)values[label+' [a.u.]']=power(event[key]);
  for(const [key,label]of [['phy_bits','PHY size [bit]'],['phy_tx_time','PHY TX · absolute time [s]'],['phy_rx_time','PHY RX · absolute time [s]'],['duration_s','PHY duration [s]'],['snr_db','Raw SNR Pr/Pn [dB]'],['rx_snr_penalty_db','Configured SNR penalty [dB]']])if(event[key]!=null)values[label]=number(event[key],key==='phy_bits'?0:6);
  if(event.snr_db!=null&&event.rx_snr_penalty_db!=null)values['SNR after penalty [dB] · computed']=number(event.snr_db+event.rx_snr_penalty_db,6);
  if(event.phy_patch_id!=null)values['Patch PHY']=event.phy_patch_id;
  if(!Object.keys(values).length)return '';
  return '<section class="phy-diagnostics"><h4>'+esc(eventLabel(event))+' · t = '+number(event.time,3)+' s</h4><p class="micro">Linear powers in DESERT normalised acoustic units (a.u.). TX/RX times are absolute, not latencies.</p>'+fields(values)+'</section>';
}
export function packetDetails(packet){
  if(!packet)return '<div class="context-placeholder"><div class="empty-symbol">↗</div><h3>Every message has a story</h3><p>Select a row to see its transmissions, any relays and the delivery, with the times observed by the network.</p></div>';
  const p=packet,relays=[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id!==p.source).map(e=>e.node_id))];
  return '<h2>'+esc(drone(p.source))+' → '+esc(drone(p.destination))+'</h2><p class="micro" style="margin-top:7px">'+esc(typeName(p.type))+' · '+number(p.size,0)+' payload bytes</p><div style="margin-top:12px">'+stateHTML(p)+'</div>'+fields({'Generated at':number(p.creation_time,3)+' s','Delay':p.delay==null?'Not available':number(p.delay,3)+' s','Observed relays':relays.length?relays.map(drone).join(' → '):'None'})+(p.status==='timeout_unknown_cause'?'<p class="micro">The TTL expired. The cause of the missed delivery remains unknown. '+help('Scadenza')+'</p>':'')+'<h3>The message path</h3>'+eventTimeline([{event:'generated',time:p.creation_time,node_id:p.source},...p.events])+(p.omitted_events?'<p class="micro">'+p.omitted_events+' earlier events in the complete exportable history.</p>':'')+'<details><summary>Technical details and raw data</summary>'+fields({'ID':p.id,'MAC':p.protocol,'Payload / envelope':p.size+' / '+p.wire_size+' B','First PHY transmission':p.physical_tx_time==null?'N/A':number(p.physical_tx_time,3)+' s','Final delivery':p.receive_time==null?'N/A':number(p.receive_time,3)+' s','TTL deadline':number(p.deadline,3)+' s','Individual MAC discard':'Not observable'})+p.events.filter(e=>e.event.startsWith('phy_')).map(phyDetails).join('')+'<pre>'+esc(JSON.stringify(p,null,2))+'</pre></details>';
}
export function renderPackets(s,selected,onSelect){
  const filter=$('#filter').value.toLowerCase(),node=$('#packet-node').value,status=$('#packet-status').value,event=$('#packet-event').value,destination=$('#packet-destination').value,type=$('#packet-type').value;
  const packets=(s.packets||[]).filter(p=>(!filter||[p.id,p.source,p.destination,p.type,p.payload_hex].join(' ').toLowerCase().includes(filter))&&(!node||p.source===node||p.destination===node||p.events.some(e=>e.node_id===node))&&(!status||p.status===status)&&(!event||p.events.some(e=>e.event===event))&&(!destination||p.destination===destination)&&(!type||p.type===type));
  $('#packet-count').textContent=packets.length+' messages';
  $('#packet-rows').innerHTML=packets.slice().reverse().map(p=>'<tr tabindex="0" data-id="'+esc(p.id)+'" class="'+(selected===p.id?'selected':'')+'" aria-selected="'+(selected===p.id)+'"><td>'+esc(drone(p.source)+' → '+drone(p.destination))+'<span class="message-id">'+esc(p.id.slice(0,8))+' · '+number(p.creation_time,2)+' s</span></td><td>'+(path=>'<span class="path">'+(path.hops.length?esc(path.hops.map(drone).join(' → ')):'—')+'</span>'+(path.interface?'<span class="message-id">'+esc(path.interface)+'</span>':''))(observedPath(p))+'</td><td>'+esc(typeName(p.type))+'</td><td>'+stateHTML(p)+'</td><td>'+(p.delay==null?'—':number(p.delay,3)+' s')+'</td></tr>').join('')||'<tr><td colspan="5"><div class="empty-inline">'+((s.packets||[]).length?'No messages match the filters.':'Messages will appear once the simulation starts.')+'</div></td></tr>';
  $('#packet-rows').querySelectorAll('[data-id]').forEach(row=>{row.onclick=()=>onSelect(row.dataset.id);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(row.dataset.id)}}});
  preserve($('#packet-details'),packetDetails((s.packets||[]).find(p=>p.id===selected)));
}
