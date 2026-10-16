import {$,esc,number,fields,statusName,timeline} from './ui.js';

export function renderPackets(s,selected,onSelect){
  const filter=$('#filter').value.toLowerCase(),node=$('#packet-node').value,status=$('#packet-status').value,event=$('#packet-event').value;
  const packets=(s.packets||[]).filter(p=>(!filter||JSON.stringify(p).toLowerCase().includes(filter))&&(!node||p.source===node||p.destination===node||p.events.some(e=>e.node_id===node))&&(!status||p.status===status)&&(!event||p.events.some(e=>e.event===event)));
  $('#packet-rows').innerHTML=packets.slice().reverse().map(p=>'<tr tabindex="0" data-id="'+esc(p.id)+'" class="'+(selected===p.id?'selected':'')+'"><td>'+number(p.creation_time)+'</td><td>'+esc(p.source+' → '+p.destination)+'</td><td>'+p.size+' / '+p.wire_size+'</td><td>'+esc(p.id.slice(0,10))+'…</td><td class="'+esc(p.status)+'">'+esc(statusName(p.status))+'</td><td>'+number(p.delay)+'</td><td>'+esc(p.protocol)+'</td></tr>').join('')||'<tr><td colspan="7">Nessun messaggio corrispondente.</td></tr>';
  $('#packet-rows').querySelectorAll('tr[data-id]').forEach(row=>{row.onclick=()=>onSelect(row.dataset.id);row.onkeydown=e=>{if(e.key==='Enter')onSelect(row.dataset.id)}});
  if(!selected)return;
  const p=(s.packets||[]).find(p=>p.id===selected);
  if(!p){$('#packet-details').textContent='Messaggio fuori dalla finestra recente. Esporta il JSONL per la storia completa.';return}
  const relays=[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id!==p.source).map(e=>e.node_id))];
  $('#packet-details').innerHTML='<h2>Messaggio '+esc(p.id)+'</h2>'+fields({'Mittente':p.source,'Destinazione finale':p.destination,'Tipo':p.type,'Payload / envelope [B]':p.size+' / '+p.wire_size,'MAC':p.protocol,'Generazione [s]':number(p.creation_time),'Inserimento stack [s]':number(p.network_tx_time),'Prima PHY TX [s]':number(p.physical_tx_time),'Consegna finale [s]':number(p.receive_time),'Latenza [s]':number(p.delay),'Scadenza TTL [s]':number(p.deadline),'Stato':statusName(p.status),'Relay osservati':relays.join(' → ')||'Nessuno osservato','Scarto MAC del singolo messaggio':'N/D'})+'<h3>Timeline · tempo originale DESERT [s]</h3><p class="note">'+(p.omitted_events?'Finestra troncata: '+p.omitted_events+' eventi precedenti nel JSONL esportabile.':'')+'</p><ol class="timeline">'+timeline([{event:'generated',time:p.creation_time,node_id:p.source},...p.events])+'</ol><details><summary>Payload hex e metadati originali</summary><pre>'+esc(JSON.stringify(p,null,2))+'</pre></details>';
}
