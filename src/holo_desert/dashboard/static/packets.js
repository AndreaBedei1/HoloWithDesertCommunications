import {$,esc,number,fields,statusName} from './ui.js';
import {drone,typeName,eventLabel,eventTone,help,interfaceLabel,powerLabel} from './presentation.js';

export const packetTone=p=>p.status==='received'?'success':p.status==='timeout_unknown_cause'?'warning':p.status==='phy_tx_observed'?'info':'neutral';
export const stateHTML=p=>'<span class="state-text '+packetTone(p)+'"><span aria-hidden="true">'+({success:'✓',warning:'◷',info:'↗',neutral:'·'}[packetTone(p)])+'</span>'+esc(statusName(p.status))+'</span>';
export function eventTimeline(events){
  return '<ol class="timeline">'+events.map(e=>{const level=e.event.startsWith('phy_')?'PHY':e.event==='forward'?'Rete':'Applicazione',node=e.node_id||(typeof e.node==='string'?e.node:null);return '<li class="'+eventTone(e)+'"><b>'+esc(eventLabel(e))+'</b><span class="event-level">'+level+'</span><time>'+number(e.time,3)+' s'+(node?' · '+esc(drone(node)):'')+'</time>'+(e.next_hop_id?'<small>Prossimo nodo: '+esc(drone(e.next_hop_id))+'</small>':'')+(e.state?'<small>Stato: '+esc(e.state)+'</small>':'')+(e.interface_index!=null?'<small>Interfaccia: '+esc(interfaceLabel(e.interface_index))+'</small>':'')+(powerLabel(e)?'<small>Potenza applicata: '+esc(powerLabel(e))+'</small>':'')+'</li>'}).join('')+'</ol>';
}
function phyDetails(event){
  const power=value=>value==null?'N/D':Number(value).toExponential(5);
  const values={};
  for(const [key,label]of [['pt','Pt · trasmissione'],['pr','Pr · ricezione'],['pn','Pn · rumore'],['pi','Pi · interferenza']])if(event[key]!=null)values[label+' [u.a.]']=power(event[key]);
  for(const [key,label]of [['phy_bits','Dimensione PHY [bit]'],['phy_tx_time','TX PHY · tempo assoluto [s]'],['phy_rx_time','RX PHY · tempo assoluto [s]'],['duration_s','Durata PHY [s]'],['snr_db','SNR grezzo Pr/Pn [dB]'],['rx_snr_penalty_db','Penalità SNR configurata [dB]']])if(event[key]!=null)values[label]=number(event[key],key==='phy_bits'?0:6);
  if(event.snr_db!=null&&event.rx_snr_penalty_db!=null)values['SNR dopo penalità [dB] · calcolato']=number(event.snr_db+event.rx_snr_penalty_db,6);
  if(event.phy_patch_id!=null)values['Patch PHY']=event.phy_patch_id;
  if(!Object.keys(values).length)return '';
  return '<section class="phy-diagnostics"><h4>'+esc(eventLabel(event))+' · t = '+number(event.time,3)+' s</h4><p class="micro">Potenze lineari in unità acustiche normalizzate DESERT (u.a.). I tempi TX/RX sono assoluti, non latenze.</p>'+fields(values)+'</section>';
}
export function packetDetails(packet){
  if(!packet)return '<div class="context-placeholder"><div class="empty-symbol">↗</div><h3>Ogni messaggio ha una storia</h3><p>Seleziona una riga per vedere trasmissioni, eventuali relay e consegna, con i tempi osservati dalla rete.</p></div>';
  const p=packet,relays=[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id!==p.source).map(e=>e.node_id))];
  return '<h2>'+esc(drone(p.source))+' → '+esc(drone(p.destination))+'</h2><p class="micro" style="margin-top:7px">'+esc(typeName(p.type))+' · '+number(p.size,0)+' byte di payload</p><div style="margin-top:12px">'+stateHTML(p)+'</div>'+fields({'Generato a':number(p.creation_time,3)+' s','Ritardo':p.delay==null?'Non disponibile':number(p.delay,3)+' s','Relay osservati':relays.length?relays.map(drone).join(' → '):'Nessuno'})+(p.status==='timeout_unknown_cause'?'<p class="micro">Il TTL è scaduto. La causa della mancata consegna resta ignota. '+help('Scadenza')+'</p>':'')+'<h3>Il percorso del messaggio</h3>'+eventTimeline([{event:'generated',time:p.creation_time,node_id:p.source},...p.events])+(p.omitted_events?'<p class="micro">'+p.omitted_events+' eventi precedenti nella storia completa esportabile.</p>':'')+'<details><summary>Dettagli tecnici e dati originali</summary>'+fields({'ID':p.id,'MAC':p.protocol,'Payload / envelope':p.size+' / '+p.wire_size+' B','Prima trasmissione PHY':p.physical_tx_time==null?'N/D':number(p.physical_tx_time,3)+' s','Consegna finale':p.receive_time==null?'N/D':number(p.receive_time,3)+' s','Scadenza TTL':number(p.deadline,3)+' s','Scarto MAC individuale':'Non osservabile'})+p.events.filter(e=>e.event.startsWith('phy_')).map(phyDetails).join('')+'<pre>'+esc(JSON.stringify(p,null,2))+'</pre></details>';
}
export function renderPackets(s,selected,onSelect){
  const filter=$('#filter').value.toLowerCase(),node=$('#packet-node').value,status=$('#packet-status').value,event=$('#packet-event').value,destination=$('#packet-destination').value,type=$('#packet-type').value;
  const packets=(s.packets||[]).filter(p=>(!filter||[p.id,p.source,p.destination,p.type,p.payload_hex].join(' ').toLowerCase().includes(filter))&&(!node||p.source===node||p.destination===node||p.events.some(e=>e.node_id===node))&&(!status||p.status===status)&&(!event||p.events.some(e=>e.event===event))&&(!destination||p.destination===destination)&&(!type||p.type===type));
  $('#packet-count').textContent=packets.length+' messaggi';
  $('#packet-rows').innerHTML=packets.slice().reverse().map(p=>'<tr tabindex="0" data-id="'+esc(p.id)+'" class="'+(selected===p.id?'selected':'')+'" aria-selected="'+(selected===p.id)+'"><td>'+esc(drone(p.source)+' → '+drone(p.destination))+'<span class="message-id">'+esc(p.id.slice(0,8))+' · '+number(p.creation_time,2)+' s</span></td><td>'+esc(typeName(p.type))+'</td><td>'+stateHTML(p)+'</td><td>'+(p.delay==null?'—':number(p.delay,3)+' s')+'</td></tr>').join('')||'<tr><td colspan="4"><div class="empty-inline">'+((s.packets||[]).length?'Nessun messaggio corrisponde ai filtri.':'I messaggi compariranno dopo l’avvio della simulazione.')+'</div></td></tr>';
  $('#packet-rows').querySelectorAll('[data-id]').forEach(row=>{row.onclick=()=>onSelect(row.dataset.id);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(row.dataset.id)}}});
  $('#packet-details').innerHTML=packetDetails((s.packets||[]).find(p=>p.id===selected));
}
