import {$,esc,number,api,choices,fields,timeline} from './ui.js';
import {chart} from './charts.js';
import {drawMap,bindMap,resetMaps} from './maps.js';
import {bindConfiguration} from './configuration.js';
import {renderPackets} from './packets.js';

let latest={}, config=null, view='fleet', selectedNode=null, selectedPacket=null, busy=false;
const activeStates=['starting','running','paused','stopping'];
const colors=['#54d8ba','#69adff','#f5be6d','#ff7e88'];
function showError(error){$('#error').hidden=!error;$('#error').textContent=error||''}
function setConfig(value){config=value;$('#quick-mac').value=config.network.mac.protocol;$('#description').textContent=config.description}
async function loadConfig(){setConfig(await api('/api/scenarios/'+$('#scenario').value))}
async function action(task){busy=true;showError('');render();try{await task();latest=await api('/api/state')}catch(e){showError(e.message)}finally{busy=false;render()}}

document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  view=b.dataset.view;document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==view);$('#view-title').textContent=b.querySelector('span').textContent;
  if(view==='compare')loadComparisons().catch(e=>showError(e.message));render();
});
$('#scenario').onchange=()=>action(loadConfig);
$('#quick-mac').onchange=()=>{if(config)config.network.mac.protocol=$('#quick-mac').value};
bindConfiguration(()=>config,setConfig);
$('#start').onclick=()=>action(()=>api('/api/start',{scenario:$('#scenario').value,standalone:$('#mode').value==='standalone',configuration:config}));
for(const name of ['stop','reset'])$('#'+name).onclick=()=>action(async()=>{await api('/api/'+name,{});if(name==='reset'){selectedPacket=null;selectedNode=null;resetMaps()}});
$('#pause').onclick=()=>action(()=>api('/api/'+(latest.state==='paused'?'resume':'pause'),{}));
$('#retain').onclick=()=>action(async()=>{await api('/api/comparison',{});await loadComparisons()});
for(const id of ['trails','route-layer','phy-layer','delivery-layer','topology-packet','packet-node','packet-status','packet-event','metric-group','metric-window','metric-node','metric-pair','fleet-pair'])$('#'+id).onchange=render;
$('#filter').oninput=render;
$('#node-select').onchange=()=>{selectedNode=$('#node-select').value;render()};
for(const [id,button]of [['#fleet-canvas','#fit-fleet'],['#network-canvas','#fit-network']])bindMap(id,button,node=>{selectedNode=node},render);

function line(key,color=colors[0]){return {value:p=>p[key],color}}
function metrics(s){
  const group=$('#metric-group').value, node=$('#metric-node').value,pair=$('#metric-pair').value, opts={window:Number($('#metric-window').value)},series=s.series||[];
  $('#metric-node').disabled=group!=='channel';$('#metric-pair').disabled=group!=='geometry';
  document.querySelectorAll('.metric-panel').forEach(el=>el.hidden=el.dataset.group!==group);
  if(group==='delivery'){
    chart('#throughput-chart',series,[line('goodput_bps'),line('application_wire_throughput_bps',colors[1])],opts);
    chart('#pdr-chart',series,[line('pdr_resolved')],{...opts,max:1});chart('#latency-chart',series,[line('mean_latency_s',colors[1])],opts);
    chart('#traffic-chart',series,[line('generated',colors[1]),line('received'),line('timed_out',colors[2])],opts);
  }else if(group==='channel'){
    chart('#phy-chart',series,['noise_error','interference_error','not_synchronized'].map((key,i)=>({value:p=>p.nodes?.[node]?.phy?.[key]??(p.nodes?.[node]?0:null),color:colors[[2,3,1][i]]})),opts);
    chart('#queue-chart',series,[{value:p=>p.nodes?.[node]?.mac_queue,color:colors[0]}],{...opts,step:true});
  }else{
    chart('#distance-chart',series,[{value:p=>p.distances_m?.[pair],color:colors[0]}],opts);chart('#drift-chart',series,[line('wall_drift_s',colors[2])],opts);
  }
  const keys=['time','mac_queue','app_sent','app_received','mac_data_tx','mac_data_rx','mac_error_rx','mac_discarded_tx','phy_noise_errors','phy_interference_errors'];
  $('#mac-stats').innerHTML='<table><thead><tr><th>Nodo</th>'+keys.map(k=>'<th>'+esc(k+(k==='time'?' [s]':''))+'</th>').join('')+'</tr></thead><tbody>'+Object.entries(s.stats||{}).map(([n,values])=>'<tr><td>'+esc(n)+'</td>'+keys.map(k=>'<td>'+number(values[k],k==='time'?1:0)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
}
function fleet(s){
  drawMap('#fleet-canvas',s,selectedNode);
  const pose=s.fleet?.[selectedNode];
  $('#node-details').innerHTML=pose?fields({'ID':selectedNode,'X [m]':number(pose.x),'Y [m]':number(pose.y),'Z [m]':number(pose.z),'Profondità [m]':number(-pose.z),'Yaw [°]':number(pose.yaw,1)})+'<details open><summary>Interfaccia acustica DESERT</summary>'+fields(s.stats?.[selectedNode]||{'Statistiche':'N/D'})+'</details>':'Attesa delle posizioni misurate.';
  $('#distances').innerHTML=Object.entries(s.distances_m||{}).map(([pair,value])=>'<div class="distance-row"><span>'+esc(pair.replace('>',' ↔ '))+'</span><b>'+number(value,1)+' m</b></div>').join('');
  const pair=$('#fleet-pair').value;
  chart('#mobility-chart',s.series||[],[{value:p=>p.distances_m?.[pair],color:colors[0]},{value:p=>p.pdr_resolved,color:colors[1],right:true}],{dual:true});
  $('#coordination').innerHTML=Object.entries(s.applications||{}).map(([node,a])=>'<h3>'+esc(node+' · '+a.role+' · '+a.state)+'</h3>'+fields({'Ultimo heartbeat RX [s]':number(a.last_heartbeat_s),'Età [s]':number(a.heartbeat_age_s),'Freschezza massima [s]':number(a.freshness_s)})).join('')||'<p class="note">Applicazione senza stato heartbeat.</p>';
  $('#transitions').innerHTML=timeline(s.transitions||[]);
}
function topology(s){
  choices('#topology-packet',(s.packets||[]).slice(-100).map(p=>p.id),'Tutti i messaggi / ultime osservazioni');
  const packet=(s.packets||[]).find(p=>p.id===$('#topology-packet').value);
  const observed=packet?{...s,observations:packet.events,edges:packet.status==='received'?[{source:packet.source,destination:packet.destination,last_receive:packet.receive_time}]:[]}:s;
  drawMap('#network-canvas',observed,selectedNode,true);
  $('#edge-details').innerHTML=timeline((observed.observations||[]).filter(e=>e.event!=='phy_rx_start').slice(-30).reverse())||'<li>Nessuna osservazione.</li>';
  $('#route-details').innerHTML=(s.configured_routes||[]).map(r=>'<p>'+esc(r.source+' → '+r.destination+' via '+r.next_hop)+' <small>'+(r.explicit?'override':'diretto')+'</small></p>').join('');
}
async function loadComparisons(){
  const data=await api('/api/comparisons'),runs=data.runs;
  if(!runs.length){$('#comparison').textContent='Nessun riepilogo conservato.';return}
  const rows=[['Generati',x=>x.generated],['Consegnati',x=>x.received],['TTL scaduti',x=>x.timed_out],['In attesa',x=>x.pending],['PDR risolti [0–1]',x=>number(x.pdr_resolved)],['RX / generati [0–1]',x=>number(x.pdr_generated)],['Goodput medio [bit/s]',x=>number(x.goodput_bps)],['Throughput envelope medio [bit/s]',x=>number(x.application_wire_throughput_bps)],['Latenza media [s]',x=>number(x.mean_latency_s)],['PHY rumore [osservazioni]',x=>x.phy_observations.noise_error],['PHY interferenza [osservazioni]',x=>x.phy_observations.interference_error],['PHY non sincronizzato [osservazioni]',x=>x.phy_observations.not_synchronized],['Picco coda MAC campionato [pacchetti]',x=>x.mac_queue_peak??'N/D']];
  $('#comparison').innerHTML='<p class="'+(data.equivalent?'received':'warning')+'">'+(data.equivalent?'Configurazioni equivalenti: cambia solo il MAC.':runs.length===1?'Conserva una seconda esecuzione.':'Configurazioni non equivalenti o stesso MAC: confronto non controllato.')+'</p><div class="table-scroll"><table><thead><tr><th>Metrica</th>'+runs.map(r=>'<th>'+esc(r.mac)+'<br><small>'+esc(r.run_id.slice(0,8))+'</small></th>').join('')+'</tr></thead><tbody>'+rows.map(([label,read])=>'<tr><td>'+label+'</td>'+runs.map(r=>'<td>'+esc(read(r.summary))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
}
function render(){
  const s=latest,active=activeStates.includes(s.state);
  $('#state').textContent=(s.state||'idle').toUpperCase()+(s.standalone?' · POSIZIONI FISSE':'');$('#time').innerHTML=number(s.time||0,2)+' <small>s</small>';
  $('#holo-status').textContent=s.services?.holoocean||'—';$('#desert-status').textContent=s.services?.desert||'—';
  $('#position-source').textContent=s.standalone?'Posizioni: fixture fissa YAML':'Posizioni: sensori HoloOcean';
  for(const k of ['generated','received','pending','timed_out'])$('#'+k).textContent=s.counts?.[k]||0;
  for(const id of ['start','scenario','mode','configure','quick-mac'])$('#'+id).disabled=busy||active||!config;
  $('#stop').disabled=busy||!['starting','running','paused'].includes(s.state);$('#reset').disabled=busy||active||s.state==='idle';
  $('#pause').disabled=busy||!['running','paused'].includes(s.state)||!s.pause_supported;$('#pause').textContent=s.state==='paused'?'▶ Riprendi':'Ⅱ Pausa';
  $('#retain').disabled=busy||s.state!=='finished'||s.standalone||s.configuration?.name!=='e04_congestion';
  $('#export').setAttribute('aria-disabled',s.state==='idle'?'true':'false');if(s.error)showError(s.error);
  const nodes=Object.keys(s.fleet||{}),pairs=Object.keys(s.distances_m||{});
  choices('#node-select',nodes);choices('#metric-node',nodes);choices('#packet-node',nodes,'Tutti i nodi');choices('#metric-pair',pairs);choices('#fleet-pair',pairs);
  if(!nodes.includes(selectedNode))selectedNode=nodes[0];if(selectedNode)$('#node-select').value=selectedNode;
  if(view==='fleet')fleet(s);if(view==='topology')topology(s);if(view==='packets')renderPackets(s,selectedPacket,id=>{selectedPacket=id;render()});if(view==='metrics')metrics(s);
}
$('#export').onclick=e=>{if($('#export').getAttribute('aria-disabled')==='true')e.preventDefault()};
async function poll(){try{const s=await api('/api/state');if(s.run_id!==latest.run_id){selectedPacket=null;selectedNode=null;resetMaps()}latest=s;render();$('#updated').textContent='Aggiornato '+new Date().toLocaleTimeString()}catch(e){showError('Servizio dashboard non raggiungibile: '+e.message)}setTimeout(poll,500)}
window.onresize=render;
api('/api/scenarios').then(async list=>{choices('#scenario',list.map(x=>x.id));await loadConfig();latest=await api('/api/state');if(latest.configuration){setConfig(latest.configuration);$('#scenario').value=config.name;if(latest.standalone)$('#mode').value='standalone'}poll()}).catch(e=>showError(e.message));
