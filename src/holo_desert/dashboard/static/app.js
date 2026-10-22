import {$,esc,number,api,choices,fields} from './ui.js';
import {chart} from './charts.js';
import {drawMap,bindMap,resetMaps} from './maps.js';
import {bindConfiguration,setNetworkCatalog,moduleName} from './configuration.js';
import {renderPackets,packetDetails,packetTone,stateHTML,eventTimeline} from './packets.js';
import {SCENARIOS,scenarioInfo,drone,typeName,help,bindHelp,setInterfaceNames} from './presentation.js';
import {bindScenarioEditor} from './scenario-editor.js';

const activeStates=['starting','running','paused','stopping'];
const palette={blue:'#3165cf',green:'#237454',amber:'#ad741f',red:'#b44343',gray:'#8795a8'};
let latest={state:'idle'},configuration=null,selectedId='e01_chat',catalog=[],libraryTab='example',view='home',analysisGroup='delivery';
let selectedNode=null,selectedPacket=null,busy=false,executionMode='integrated',homeKey='',toastTimer;
let configuredRerun=null;
const active=()=>activeStates.includes(latest.state);
const byId=id=>catalog.find(s=>s.id===id);
const names={idle:'Nessuna simulazione',starting:'Avvio in corso',running:'Simulazione attiva',paused:'In pausa',stopping:'Arresto dei motori',finished:'Simulazione completata',stopped:'Simulazione interrotta',failed:'La simulazione richiede attenzione'};
const serviceNames={not_started:'Non avviato',starting:'Inizializzazione',running:'Attivo',stopped:'Arrestato',standalone_fixture:'Posizioni fisse',cleanup_failed:'Errore di arresto'};
const nodeStatsLabels={app_sent:'Inviati nello stack applicativo',app_received:'Ricevuti nello stack applicativo',mac_queue:'Pacchetti in coda MAC',mac_data_tx:'Frame dati trasmessi dal MAC',mac_data_rx:'Frame dati ricevuti dal MAC',mac_discarded_tx:'Scarti MAC aggregati',mac_error_rx:'Errori MAC aggregati',phy_noise_errors:'Errori dovuti al rumore',phy_interference_errors:'Esiti errore nel ramo PHY interferenza'};

function notify(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,4500)}
function showError(error){
  $('#error').hidden=!error;if(!error)return;
  const raw=error.message||String(error);let title='Non è stato possibile completare l’operazione',message='Controlla i dettagli e riprova.';
  if(/Docker|docker/.test(raw)){title='DESERT non è pronto';message='Verifica che Docker Desktop sia attivo in modalità container Linux. Il comando holo-desert doctor aiuta a controllare l’installazione.'}
  else if(/HoloOcean|Ocean package|holoocean/.test(raw)){title='HoloOcean non è pronto';message='Controlla l’installazione di HoloOcean e del pacchetto Ocean con holo-desert doctor.'}
  else if(/valid|route|node|Flow|Waypoint|loop|scenario|Scenario|nome|cambiato|riferiment|occupied|busy|Unknown/i.test(raw)){title='Controlla la configurazione';message=raw.length<240?raw:'Alcuni parametri non sono validi. Apri i dettagli per individuare i campi da correggere.'}
  else if(/fetch|unavailable|network/i.test(raw)){title='Collegamento al laboratorio interrotto';message='Il server locale non risponde. Verifica che il comando holo-desert dashboard sia ancora in esecuzione.'}
  $('#error-title').textContent=title;$('#error-message').textContent=message;$('#error-detail').textContent=raw;
}
function preserve(root,html){
  if(root.innerHTML===html)return;
  const opened=new Set([...root.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent)),scroll=root.scrollTop;
  root.innerHTML=html;root.querySelectorAll('details').forEach(d=>{if(opened.has(d.querySelector('summary')?.textContent))d.open=true});root.scrollTop=scroll;
}
function confirm(title,text,accept='Conferma'){
  const dialog=$('#confirm-dialog');$('#confirm-title').textContent=title;$('#confirm-text').textContent=text;$('#confirm-accept').textContent=accept;dialog.showModal();
  return new Promise(resolve=>{let settled=false;const done=result=>{if(settled)return;settled=true;dialog.close();resolve(result)};$('#confirm-cancel').onclick=()=>done(false);$('#confirm-accept').onclick=()=>done(true);dialog.oncancel=e=>{e.preventDefault();done(false)}});
}
async function action(task){busy=true;showError(null);render();try{return await task()}catch(e){showError(e)}finally{busy=false;render()}}
function showView(next){view=next;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==next);$('#workspace').hidden=['home','editor'].includes(next);document.querySelectorAll('.app-header [data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next);b.setAttribute('aria-current',b.dataset.view===next?'page':'false')});if(next==='analysis'&&analysisGroup==='compare')loadComparisons().catch(showError);render()}
function setConfiguration(value,mode=executionMode){configuration=structuredClone(value);executionMode=mode;homeKey='';render()}
async function loadCatalog(){const [examples,personal]=await Promise.all([api('/api/scenarios'),api('/api/user-scenarios')]);catalog=[...examples.map(x=>({...x,kind:'example'})),...personal];homeKey='';$('#personal-count').textContent=personal.length}
async function selectScenario(id){selectedId=id;configuration=await api('/api/scenarios/'+encodeURIComponent(id));executionMode='integrated';homeKey='';render()}
function uniqueName(base){const taken=new Set(catalog.map(x=>(x.name||x.id).normalize('NFKC').toLocaleLowerCase('it')));let name=base,index=2;while(taken.has(name.normalize('NFKC').toLocaleLowerCase('it')))name=base+' ('+index+++')';return name}
async function startRun(config=configuration,id=selectedId){
  configuredRerun=null;
  selectedNode=null;selectedPacket=null;resetMaps();
  await api('/api/start',{scenario:id,configuration:config,standalone:executionMode==='standalone'});
  latest=await api('/api/state');showView('simulation');
}
bindConfiguration(()=>configuration,(value,mode)=>{if(view!=='home'&&latest.run_id)configuredRerun={run_id:latest.run_id,configuration:value,scenario_id:latest.scenario_id||selectedId};setConfiguration(value,mode);notify('Impostazioni applicate alla prossima simulazione.')},()=>executionMode);
const editor=bindScenarioEditor({onOpen:()=>showView('editor'),onClose:()=>showView('home'),confirm,notify,onStart:async(config,id)=>action(()=>startRun(config,id)),onSaved:async record=>{await loadCatalog();libraryTab='user';selectedId=record.id;setConfiguration(record.configuration);showView('home');notify('Scenario salvato nella tua libreria.')}});

function renderHome(){
  if(!configuration)return;
  const key=JSON.stringify([selectedId,configuration,libraryTab,active(),busy,catalog.map(x=>[x.id,x.name])]);if(key===homeKey)return;homeKey=key;
  $('#examples-tab').classList.toggle('active',libraryTab==='example');$('#personal-tab').classList.toggle('active',libraryTab==='user');
  const list=catalog.filter(x=>x.kind===libraryTab);
  $('#scenario-card').hidden=!list.length;$('.library-layout').classList.toggle('is-empty',!list.length);
  $('#scenario-list').innerHTML=list.map((s,i)=>{const info=scenarioInfo(s.id,{name:s.name,description:s.description});return '<button class="scenario-option '+(s.id===selectedId?'active':'')+'" data-scenario="'+esc(s.id)+'" '+(active()?'disabled title="Arresta la simulazione prima di cambiare scenario"':'')+' aria-pressed="'+(s.id===selectedId)+'"><span class="scenario-icon" aria-hidden="true">'+(['↔','⋮','⇆','≋','↗','⌁'][s.kind==='example'?Object.keys(SCENARIOS).indexOf(s.id):i%6])+'</span><span class="scenario-label">'+esc(info.title)+'</span><span class="scenario-number">'+esc(info.code==='Personale'?'↗':info.code)+'</span></button>'}).join('')||'<div class="library-empty"><h3>La tua prossima idea parte da qui</h3><p>Crea uno scenario oppure duplica uno degli esempi. Lo ritroverai anche al prossimo avvio.</p></div>';
  $('#scenario-list').querySelectorAll('[data-scenario]').forEach(b=>b.onclick=()=>action(()=>selectScenario(b.dataset.scenario)));
  const item=byId(selectedId),info=scenarioInfo(selectedId,configuration);
  $('#scenario-code').textContent=info.code;$('#scenario-kind').textContent=item?.kind==='user'?'Scenario personale':'Esempio protetto';
  $('#scenario-title').textContent=info.title;$('#description').textContent=info.description;$('#scenario-observe').textContent=info.observe;
  const diagram=info.diagram.length?info.diagram:configuration.nodes.slice(0,5).map(n=>drone(n.id));
  $('#scenario-diagram').innerHTML=diagram.map(x=>/[→←]/.test(x)?'<span class="diagram-arrow" aria-hidden="true">'+esc(x)+'</span>':'<span class="diagram-node '+(x.length>2?'wide':'')+'">'+esc(x)+'</span>').join('');
  $('#scenario-meta').innerHTML='<span><strong>'+configuration.nodes.length+'</strong> droni</span><span><strong>'+number(configuration.duration,0)+' s</strong> di simulazione</span><span>'+esc(moduleName('mac',configuration.network.mac.protocol))+'</span>';
  $('#start').disabled=busy||active();$('#start').title=active()?'Una simulazione è già in corso: apri Simulazione per seguirla.':'';
  $('#edit-scenario').hidden=item?.kind!=='user';$('#delete-scenario').hidden=item?.kind!=='user';
  for(const id of ['edit-scenario','duplicate-scenario','new-scenario','import-scenario','delete-scenario']){$('#'+id).disabled=busy||active();$('#'+id).title=active()?'Arresta la simulazione prima di modificare gli scenari':''}
  $('#export-scenario').href='/api/scenarios/'+encodeURIComponent(selectedId)+'/yaml';
  $('#setup-note').textContent=active()?'Una simulazione è in corso. Seguila dalla scheda Simulazione.':'I parametri predefiniti sono pronti. Puoi modificarli in Impostazioni.';
}
function renderServices(){
  const config=latest.configuration,base=config?.network?.acoustic?.phy||'bpsk_upstream',models=(config?.nodes||[]).map(n=>({node:n.id,phy:n.communication?.acoustic?.phy||base})),mixed=new Set(models.map(n=>n.phy)).size>1,patch=latest.engine_info?.phy_patch;
  const phy=config?' · '+(mixed?'PHY misto: '+models.map(n=>drone(n.node)+' = '+n.phy).join('; '):'PHY: '+moduleName('phy',models[0]?.phy||base)+' ('+(models[0]?.phy||base)+')')+(patch?' · Patch motore: '+patch:''):'';
  for(const [name,prefix]of [['holoocean','holo'],['desert','desert']]){const state=latest.services?.[name]||'not_started';$('#'+prefix+'-status').textContent=serviceNames[state]||state;$('#'+prefix+'-dot').className='status-dot '+(state==='running'?'success':state==='starting'?'info':state==='cleanup_failed'?'error':'')}
  $('#run-services').textContent='HoloOcean: '+(serviceNames[latest.services?.holoocean]||'non avviato')+' · DESERT: '+(serviceNames[latest.services?.desert]||'non avviato')+(latest.standalone?' · Modalità solo rete, posizioni fisse':'')+phy;
}
function context(){
  const s=latest,packet=(s.packets||[]).find(p=>p.id===selectedPacket),pose=s.fleet?.[selectedNode];
  $('#context-panel').classList.toggle('has-selection',!!packet||!!pose);$('#clear-selection').hidden=!packet&&!pose;
  if(packet){$('#context-title').textContent='Dettaglio del messaggio';preserve($('#context-content'),packetDetails(packet));return}
  if(pose){const stats=s.stats?.[selectedNode]||{},app=s.applications?.[selectedNode];$('#context-title').textContent=drone(selectedNode);
    const positions='<div class="position-values">'+['x','y','z'].map(k=>'<div><span>'+k.toUpperCase()+' [m]</span><b>'+number(pose[k],1)+'</b></div>').join('')+'</div>';
    const distances=Object.entries(s.distances_m||{}).filter(([p])=>p.split('>').includes(selectedNode)).map(([p,v])=>'<div class="distance-row"><span>Da '+esc(drone(p.split('>').find(n=>n!==selectedNode)))+'</span><b>'+number(v,1)+' m</b></div>').join('');
    preserve($('#context-content'),positions+fields({'Profondità':number(-pose.z,1)+' m','Orientamento':number(pose.yaw,1)+'°','Messaggi in coda MAC':stats.mac_queue??'N/D'})+(app?'<h3>'+esc(app.role==='leader'?'Leader':'Follower')+' · '+esc(app.state==='HOLD'?'In attesa':app.state==='PROCEED'?'In movimento':'Invio heartbeat')+'</h3>'+fields({'Ultimo heartbeat ricevuto':app.last_heartbeat_s==null?'N/D':number(app.last_heartbeat_s,2)+' s','Età dell’informazione':app.heartbeat_age_s==null?'N/D':number(app.heartbeat_age_s,2)+' s'}):'')+'<h3>Distanze misurate</h3>'+distances+'<details><summary>Statistiche complete dell’interfaccia</summary>'+fields(Object.fromEntries(Object.entries(nodeStatsLabels).map(([key,label])=>[label,stats[key]])))+'<p class="micro">Contatori DESERT prima del controllo TTL dell’applicazione. Gli scarti sono aggregati, non per singolo messaggio.</p><pre>'+esc(JSON.stringify({pose,stats},null,2))+'</pre></details>');return;
  }
  $('#context-title').textContent='Esplora l’esperimento';
  const nodes=Object.keys(s.fleet||{}),distance=Object.values(s.distances_m||{})[0];
  preserve($('#context-content'),'<div class="context-placeholder"><div class="empty-symbol">⌁</div><h3>Ogni collegamento racconta un evento</h3><p>Seleziona un drone sulla mappa per conoscerne posizione e stato. Scegli un messaggio qui sotto per seguirne il percorso.</p></div>'+ (nodes.length?'<h3>Scegli un drone</h3><select data-node-choice aria-label="Drone da osservare"><option value="">Seleziona un drone</option>'+nodes.map(n=>'<option value="'+esc(n)+'">'+esc(drone(n))+'</option>').join('')+'</select>':'')+(nodes.length===2?fields({'Distanza misurata':number(distance,1)+' m'}):'')+'<details><summary>Come leggere i collegamenti</summary><p class="micro">Le linee blu seguono trasmissioni e ricezioni PHY osservate. Le linee verdi tratteggiate indicano una consegna finale, anche attraverso relay. Le route grigie sono solo configurazione. Nessuna linea garantisce la disponibilità futura del collegamento.</p></details>');
}
function recentMessages(){
  const packets=(latest.packets||[]).slice(-4).reverse();
  $('#pending-note').textContent=(latest.counts?.pending||0)+' in attesa · '+(latest.counts?.timed_out||0)+' scaduti';
  $('#recent-messages').innerHTML=packets.map(p=>'<button data-packet="'+esc(p.id)+'" class="message-item"><span class="message-icon '+packetTone(p)+'" aria-hidden="true">'+(p.status==='received'?'✓':p.status==='timeout_unknown_cause'?'◷':'↗')+'</span><span class="message-route">'+esc(drone(p.source)+' → '+drone(p.destination))+'<small>'+esc(typeName(p.type))+'</small></span>'+stateHTML(p)+'<span class="message-time">'+number(p.creation_time,1)+' s</span></button>').join('')||'<div class="empty-inline">I primi messaggi compariranno qui dopo l’avvio.</div>';
}
function insight(){
  const s=latest,c=s.configuration,distance=Object.values(s.distances_m||{})[0],series=s.series||[],last=series.at(-1);let html='';
  if(c?.name==='e03_mobility'){html='<p>I droni sono a <strong>'+number(distance,1)+' m</strong> di distanza. Confronta il movimento con le consegne osservate.</p><canvas id="insight-chart" class="chart"></canvas><p class="micro">Distanza misurata nel tempo [m].</p>'}
  else if(c?.name==='e04_congestion'){const queues=Object.values(s.stats||{}).map(v=>v.mac_queue).filter(v=>v!=null),max=queues.length?Math.max(...queues):null;html='<p>Coda più lunga osservata: <strong>'+number(max,0)+' pacchetti</strong>.</p><p style="margin-top:8px">Esiti errore nel ramo PHY interferenza: <strong>'+number(last?.phy_interference_observations,0)+'</strong> '+help('Interferenza')+'</p><p class="micro" style="margin-top:8px">Le scadenze restano distinte dagli errori del canale.</p>'}
  else if(c?.name==='e05_multihop'){const p=(s.packets||[]).at(-1),relays=p?[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id!==p.source).map(e=>e.node_id))]:[];html='<p>Il messaggio è destinato a C tramite B. '+help('Relay')+'</p><p style="margin-top:10px">Relay osservati nell’ultimo messaggio: <strong>'+esc(relays.map(drone).join(', ')||'in attesa del primo inoltro')+'</strong>.</p><p class="micro" style="margin-top:9px">Seleziona il messaggio per isolare le due tratte sulla mappa.</p>'}
  else if(c?.coordination){html=Object.entries(s.applications||{}).map(([node,a])=>'<div class="heartbeat-row"><span>'+esc(a.role==='leader'?'Leader':'Follower')+' · '+esc(drone(node))+'</span><b>'+esc(a.state==='HOLD'?'In attesa':a.state==='PROCEED'?'Procede':'Invia heartbeat')+'</b></div>').join('');const follower=Object.values(s.applications||{}).find(a=>a.role==='follower');html+='<p class="micro" style="margin-top:7px">Età dell’ultimo heartbeat: '+number(follower?.heartbeat_age_s,2)+' s.</p>'}
  else html='<p>'+esc(scenarioInfo(c?.name,c).observe)+'</p><p class="micro" style="margin-top:10px">I messaggi in attesa non sono ancora inclusi nella percentuale di consegna.</p>';
  $('#insight-content').innerHTML=html;
  if($('#insight-chart'))chart('#insight-chart',series,[{value:p=>Object.values(p.distances_m||{})[0],color:palette.blue}]);
}
function metrics(){
  const accounting=latest.network_metrics;preserve($('#network-accounting'),accounting?'<h3>Contabilità della rete osservata</h3>'+fields(Object.fromEntries([['data_tx_frames','Frame dati TX',0],['control_tx_frames','Frame controllo TX',0],['data_tx_bits','Bit dati TX',0],['control_tx_bits','Bit controllo TX',0],['data_airtime_s','Tempo dati sul mezzo [s]',6],['control_airtime_s','Tempo controllo sul mezzo [s]',6],['late_received','Ricevuti dopo TTL',0]].map(([key,label,digits])=>[label,number(accounting[key],digits)])))+'<p class="micro">Totali dagli eventi PHY osservati, incluse le ritrasmissioni. I messaggi ricevuti dopo TTL restano separati dalle consegne valide.</p>':'');
  const s=latest,series=s.series||[],node=$('#metric-node').value,pair=$('#metric-pair').value,opts={window:Number($('#metric-window').value)};
  $('#analysis-empty').hidden=series.length>0||analysisGroup==='compare';$('#analysis-charts').hidden=!series.length||analysisGroup==='compare';$('#compare-panel').hidden=analysisGroup!=='compare';
  $('#metric-window').disabled=analysisGroup==='compare';$('#node-filter-label').hidden=analysisGroup!=='channel';$('#pair-filter-label').hidden=!['geometry','ranging'].includes(analysisGroup);
  document.querySelectorAll('.metric-panel').forEach(p=>p.hidden=p.dataset.group!==analysisGroup);
  if(analysisGroup==='compare'){const allowed=s.state==='finished'&&!s.standalone&&!!s.configuration;$('#retain').disabled=!allowed||busy;$('#retain').title=allowed?'':'Completa una corsa integrata per conservarne il riepilogo.';$('#compare-note').textContent=allowed?'Puoi conservare il riepilogo di questa corsa.':'Il riepilogo si può conservare dopo una corsa integrata e completata. Nessun confronto parte automaticamente.';return}
  if(!series.length)return;
  const line=(key,color)=>({value:p=>p[key],color});
  if(analysisGroup==='delivery'){
    chart('#pdr-chart',series,[{value:p=>p.pdr_resolved==null?null:p.pdr_resolved*100,color:palette.green}],{...opts,max:100});
    chart('#latency-chart',series,[line('mean_latency_s',palette.blue)],opts);
    chart('#throughput-chart',series,[line('goodput_bps',palette.blue),line('application_wire_throughput_bps',palette.green)],opts);
    chart('#traffic-chart',series,[line('generated',palette.blue),line('received',palette.green),line('timed_out',palette.amber)],opts);
  }else if(analysisGroup==='channel'){
    chart('#queue-chart',series,[{value:p=>p.nodes?.[node]?.mac_queue,color:palette.blue}],{...opts,step:true});
    chart('#phy-chart',series,['noise_error','interference_error','not_synchronized'].map((key,i)=>({value:p=>p.nodes?.[node]?.phy?.[key]??(p.nodes?.[node]?0:null),color:[palette.amber,palette.red,palette.gray][i]})),opts);
  }else if(analysisGroup==='ranging')ranging(s,pair,opts);
  else{chart('#distance-chart',series,[{value:p=>p.distances_m?.[pair],color:palette.blue}],opts);chart('#drift-chart',series,[line('wall_drift_s',palette.gray)],opts)}
  const keys=Object.keys(nodeStatsLabels);$('#mac-stats').innerHTML='<table><thead><tr><th>Drone</th>'+keys.map(k=>'<th>'+esc(nodeStatsLabels[k])+'</th>').join('')+'</tr></thead><tbody>'+Object.entries(s.stats||{}).map(([n,values])=>'<tr><td>'+esc(drone(n))+'</td>'+keys.map(k=>'<td>'+number(values[k],0)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
  $('#mac-stats').insertAdjacentHTML('beforeend',Object.entries(s.mac_specific_stats||{}).filter(([node,values])=>Object.keys(values).length).map(([node,values])=>'<details><summary>Contatori nativi '+esc(drone(node))+'</summary>'+fields(values)+'</details>').join(''));
  $('#application-history').hidden=!(s.transitions||[]).length;
  preserve($('#application-events'),eventTimeline(s.transitions||[]));
  $('#configured-route-details').previousElementSibling.textContent=s.configuration?.network?.routing==='flooding'?'Flooding nativo: nessuna tabella statica':'Route configurate (default diretto)';
  $('#configured-route-details').innerHTML=(s.configured_routes||[]).map(r=>'<div class="distance-row"><span>'+esc(drone(r.source)+' → '+drone(r.destination))+'</span><b>via '+esc(drone(r.next_hop))+'</b></div>').join('');
  preserve($('#channel-events'),eventTimeline((s.observations||[]).slice(-25).reverse()).replace(/^<ol[^>]*>|<\/ol>$/g,''));
}
// Native ranging estimates against the HoloOcean geometry; never mixed into one value.
function ranging(s,pair,opts){
  const data=s.ranging||{series:{},latest:[]},points=data.series?.[pair]||[],observers=[...new Set(points.flatMap(p=>Object.keys(p.estimates)))],colors=[palette.blue,palette.green,palette.amber,palette.red];
  const empty=!data.latest?.length;$('#ranging-empty').hidden=!empty;['#ranging-chart','#ranging-key','#ranging-table','#ranging-note'].forEach(id=>$(id).hidden=empty);
  if(empty){$('#ranging-empty').textContent='Nessuna stima di distanza in questa corsa. Le stime native arrivano con un MAC di ranging (Ranging-TokenBus o Ranging-TDMA), una volta al secondo di tempo simulato.';return}
  chart('#ranging-chart',points,[{value:p=>p.geometric_distance_m,color:palette.gray},...observers.map((o,i)=>({value:p=>p.estimates[o],color:colors[i%colors.length]}))],opts);
  $('#ranging-key').innerHTML='<i class="line-key gray"></i>Distanza geometrica HoloOcean · riferimento'+observers.map((o,i)=>'<i class="line-key" style="background:'+colors[i%colors.length]+'"></i>Stima DESERT misurata da '+esc(drone(o))).join('');
  const protocol=data.latest[0]?.protocol||'',sound=s.configuration?.network?.acoustic?.sound_speed_mps;
  $('#ranging-table').innerHTML='<table><thead><tr><th>Coppia</th><th>Osservatore</th><th>Stima DESERT [m]</th><th>Tempo di volo [s]</th><th>Distanza geometrica [m]</th><th>Differenza [m]</th><th>Lettura [s]</th></tr></thead><tbody>'+data.latest.map(r=>'<tr><td>'+esc(drone(r.peer_a)+' ↔ '+drone(r.peer_b))+'</td><td>'+esc(drone(r.observer))+'</td><td>'+(r.valid?number(r.distance_m,2):'Non ancora misurata')+'</td><td>'+(r.valid?number(r.travel_time_s,6):'N/D')+'</td><td>'+number(r.geometric_distance_m,2)+'</td><td>'+number(r.error_m,2)+'</td><td>'+number(r.time,1)+'</td></tr>').join('')+'</tbody></table>';
  $('#ranging-note').textContent='Stima: tempo di volo misurato dal MAC '+protocol+' × velocità del suono configurata ('+number(sound,0)+' m/s). Il modulo non espone l’istante della misura: la distanza geometrica è l’ultimo campione HoloOcean al momento della lettura e un valore non aggiornato resta invariato. La differenza è stima meno riferimento.';
}
async function loadComparisons(){
  const data=await api('/api/comparisons'),runs=data.runs;if(!runs.length){$('#comparison').innerHTML='<p>Nessun riepilogo conservato. Completa una corsa integrata per iniziare il confronto.</p>';return}
  const rows=[['Messaggi generati',x=>x.generated],['Messaggi consegnati',x=>x.received],['Messaggi scaduti',x=>x.timed_out],['In attesa',x=>x.pending],['Consegna riuscita',x=>x.pdr_resolved==null?'N/D':number(x.pdr_resolved*100,1)+'%'],['Goodput medio [bit/s]',x=>number(x.goodput_bps,1)],['Throughput envelope [bit/s]',x=>number(x.application_wire_throughput_bps,1)],['Latenza media [s]',x=>number(x.mean_latency_s,3)],['Esiti del ramo PHY interferenza',x=>x.phy_observations.interference_error],['Errori PHY di rumore',x=>x.phy_observations.noise_error],['PHY non sincronizzati',x=>x.phy_observations.not_synchronized],['Picco coda MAC campionato',x=>x.mac_queue_peak??'N/D']];
  rows.push(['Frame dati PHY TX',x=>x.network_metrics?.data_tx_frames??'N/D'],['Frame controllo PHY TX',x=>x.network_metrics?.control_tx_frames??'N/D'],['Bit dati PHY TX',x=>x.network_metrics?.data_tx_bits??'N/D'],['Bit controllo PHY TX',x=>x.network_metrics?.control_tx_bits??'N/D'],['Tempo dati sul mezzo [s]',x=>number(x.network_metrics?.data_airtime_s,6)],['Tempo controllo sul mezzo [s]',x=>number(x.network_metrics?.control_airtime_s,6)],['Arrivi dopo TTL',x=>x.network_metrics?.late_received??'N/D'],['Scarti MAC aggregati',x=>{const values=Object.values(x.mac_stats||{}).map(n=>n.mac_discarded_tx);return values.length&&values.every(Number.isFinite)?values.reduce((a,b)=>a+b,0):'N/D'}]);
  $('#comparison').innerHTML='<p>'+esc(data.equivalent?'I parametri comuni coincidono: cambia il MAC.':runs.length===1?'Primo riepilogo conservato. Esegui un’altra corsa cambiando solo MAC.':'I parametri comuni differiscono o il MAC coincide: il confronto non è controllato.')+'</p><div class="table-scroll"><table><thead><tr><th>Metrica</th>'+runs.map(r=>'<th>'+esc(moduleName('mac',r.mac))+'</th>').join('')+'</tr></thead><tbody>'+rows.map(([name,read])=>'<tr><td>'+name+'</td>'+runs.map(r=>'<td>'+esc(read(r.summary))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><p class="micro">Al massimo sei riepiloghi in memoria. I risultati negativi restano visibili. Geometria configurata e seed uguali non garantiscono traiettorie misurate identiche.</p>';
}
function render(){
  const s=latest,hasRun=s.state!=='idle'&&!!s.configuration;renderServices();setInterfaceNames(s.configuration);
  $('#configure').disabled=busy||active()||!configuration||view==='editor'||(view==='home'&&libraryTab==='user'&&!catalog.some(s=>s.kind==='user'));$('#configure').title=active()?'Le impostazioni si possono cambiare dopo l’arresto.':'Parametri della prossima simulazione';
  renderHome();if(view==='editor'){editor.resize();return}
  $('#run-status').textContent=names[s.state]||s.state;$('#run-status').className='status-label '+s.state+(s.state==='starting'?' loading-dot':'');
  $('#run-time').textContent=number(s.time||0,1)+' / '+number(s.configuration?.duration||configuration?.duration||0,0)+' s';
  $('#run-title').textContent=hasRun?scenarioInfo(s.configuration.name,s.configuration).title:'La tua simulazione';
  $('#scenario-hint').textContent=hasRun?scenarioInfo(s.configuration.name,s.configuration).observe:'Scegli uno scenario per iniziare il tuo esperimento.';
  $('#metrics-summary').hidden=!hasRun;
  for(const id of ['pause','stop','export','rerun','reset'])$('#'+id).hidden=!hasRun;
  $('#pause').hidden=!['running','paused'].includes(s.state);$('#pause').disabled=busy||!s.pause_supported;$('#pause').textContent=s.state==='paused'?'▶ Riprendi':'Ⅱ Pausa';
  $('#stop').hidden=!['starting','running','paused'].includes(s.state);$('#stop').disabled=busy;
  $('#rerun').hidden=!['finished','stopped','failed'].includes(s.state);$('#rerun').disabled=busy;
  $('#reset').hidden=!['finished','stopped','failed'].includes(s.state);$('#reset').disabled=busy;
  const counts=s.counts||{},resolved=(counts.received||0)+(counts.timed_out||0),last=s.series?.at(-1);
  $('#generated').textContent=hasRun?number(counts.generated||0,0):'—';$('#received').textContent=hasRun?number(counts.received||0,0):'—';$('#delivery-rate').textContent=resolved?number(counts.received/resolved*100,1)+'%':'—';$('#mean-latency').textContent=last?.mean_latency_s==null?'—':number(last.mean_latency_s,3)+' s';
  const nodes=Object.keys(s.fleet||{}),pairs=Object.keys(s.distances_m||{});
  choices('#metric-node',nodes,null,drone);choices('#metric-pair',pairs,null,p=>p.split('>').map(drone).join(' ↔ '));choices('#packet-node',nodes,'Tutti i droni',drone);choices('#packet-destination',nodes,'Tutti i destinatari',drone);choices('#packet-type',[...new Set((s.packets||[]).map(p=>p.type))],'Tutti i tipi',typeName);
  if(selectedNode&&!nodes.includes(selectedNode))selectedNode=null;
  if(view==='simulation'){
    $('#map-empty').hidden=nodes.length>0;$('#map-empty-title').textContent=s.state==='starting'?'Preparazione dei simulatori':s.state==='failed'?'L’esperimento non è partito':'Il tuo esperimento apparirà qui';
    $('#map-empty-text').textContent=s.state==='starting'?'Stiamo inizializzando HoloOcean e DESERT. Il primo avvio Docker può richiedere qualche minuto.':s.state==='failed'?'Consulta il messaggio di errore e i dettagli per la diagnosi.':'Seleziona uno scenario e avvia la simulazione.';
    $('#position-source').textContent=s.standalone?'Posizioni configurate fisse · nessuna fisica HoloOcean':'Posizioni misurate da HoloOcean';
    drawMap('#fleet-canvas',s,selectedNode,selectedPacket);context();recentMessages();insight();
  }
  if(view==='messages')renderPackets(s,selectedPacket,id=>{selectedPacket=id;selectedNode=null;render()});
  if(view==='analysis')metrics();
}
document.addEventListener('click',async e=>{const nav=e.target.closest('[data-view]');if(nav){if(view==='editor'&&!await editor.close())return;showView(nav.dataset.view);return}if(e.target.closest('[data-home]'))showView('home');const packet=e.target.closest('[data-packet]');if(packet){selectedPacket=packet.dataset.packet;selectedNode=null;render()}});
document.addEventListener('change',e=>{if(e.target.matches('[data-node-choice]')){selectedNode=e.target.value||null;selectedPacket=null;render()}});
$('.brand').onclick=async e=>{e.preventDefault();if(view==='editor'&&!await editor.close())return;showView('home')};
function switchLibrary(kind){return action(async()=>{libraryTab=kind;const first=catalog.find(s=>s.kind===kind);if(first&&byId(selectedId)?.kind!==kind)await selectScenario(first.id);homeKey='';render()})}
$('#examples-tab').onclick=()=>switchLibrary('example');$('#personal-tab').onclick=()=>switchLibrary('user');
$('#start').onclick=()=>action(()=>startRun());$('#rerun').onclick=()=>action(()=>{const next=configuredRerun?.run_id===latest.run_id?configuredRerun:null;return startRun(next?.configuration||latest.configuration,next?.scenario_id||latest.scenario_id||selectedId)});
$('#pause').onclick=()=>action(async()=>{await api('/api/'+(latest.state==='paused'?'resume':'pause'),{});latest=await api('/api/state')});
$('#stop').onclick=()=>action(()=>api('/api/stop',{}));
$('#reset').onclick=()=>action(async()=>{await api('/api/reset',{});latest=await api('/api/state');selectedNode=null;selectedPacket=null;resetMaps();showView('home')});
$('#clear-selection').onclick=()=>{selectedNode=null;selectedPacket=null;render()};
bindMap('#fleet-canvas','#fit-map',node=>{selectedNode=node;selectedPacket=null},render);
for(const id of ['trails','route-layer','phy-layer','delivery-layer','packet-node','packet-status','packet-event','packet-destination','packet-type','metric-window','metric-node','metric-pair'])$('#'+id).onchange=render;
$('#filter').oninput=render;
$('#analysis-tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{analysisGroup=b.dataset.group;$('#analysis-tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));if(analysisGroup==='compare')loadComparisons().catch(showError);render()});
$('#retain').onclick=()=>action(async()=>{await api('/api/comparison',{});await loadComparisons();notify('Riepilogo conservato in memoria.')});
$('#guide-open').onclick=()=>$('#guide-dialog').showModal();$('#about-open').onclick=()=>$('#about-dialog').showModal();document.querySelectorAll('[data-close-dialog]').forEach(b=>b.onclick=()=>b.closest('dialog').close());$('#dismiss-error').onclick=()=>showError(null);bindHelp();
$('#duplicate-scenario').onclick=()=>action(async()=>{const copy=structuredClone(configuration);copy.name=uniqueName(scenarioInfo(selectedId,configuration).title+' · copia');if(SCENARIOS[selectedId])copy.description=SCENARIOS[selectedId].description;await editor.open(copy)});
$('#edit-scenario').onclick=()=>action(async()=>{const record=await api('/api/user-scenarios/'+encodeURIComponent(selectedId));await editor.open(record.configuration,record)});
$('#new-scenario').onclick=()=>action(async()=>{const config=await api('/api/scenarios/e01_chat');config.name='';config.description='';config.duration=30;config.flows[0].reply=false;config.flows[0].stop=null;config.flows[0].interval=3;await editor.open(config)});
$('#delete-scenario').onclick=()=>action(async()=>{if(!await confirm('Eliminare questo scenario?','Lo scenario personale “'+configuration.name+'” verrà eliminato dalla libreria. Gli esempi non vengono modificati.','Elimina scenario'))return;await api('/api/user-scenarios/'+selectedId+'?revision='+encodeURIComponent(byId(selectedId).revision),undefined,'DELETE');await loadCatalog();libraryTab='user';await selectScenario(catalog.find(x=>x.kind==='user')?.id||'e01_chat');notify('Scenario personale eliminato.')});
$('#import-scenario').onclick=()=>$('#import-file').click();$('#import-file').onchange=()=>action(async()=>{const file=$('#import-file').files[0];if(!file)return;try{const config=await api('/api/user-scenarios/import',{yaml:await file.text()});if(SCENARIOS[config.name])config.name=uniqueName(SCENARIOS[config.name].title+' · importato');await editor.open(config);notify('YAML importato nell’editor. Controlla i dati prima di salvare.')}finally{$('#import-file').value=''}});
window.addEventListener('resize',()=>{if(view==='editor')editor.resize();else render()});
async function poll(){try{const state=await api('/api/state');if(state.run_id!==latest.run_id){selectedNode=null;selectedPacket=null;resetMaps()}latest=state;if(state.error)showError(state.error);render();$('#updated').textContent='Aggiornato alle '+new Date().toLocaleTimeString('it-IT')}catch(e){showError(e)}setTimeout(poll,500)}
// Keep controls inert until bootstrap has chosen the initial view.
(async()=>{setNetworkCatalog(await api('/api/network-catalog'));await loadCatalog();await selectScenario('e01_chat');latest=await api('/api/state');if(latest.configuration&&latest.state!=='idle'){const known=catalog.find(x=>x.id===latest.configuration.name||x.name===latest.configuration.name);selectedId=known?.id||'e01_chat';configuration=latest.configuration;executionMode=latest.standalone?'standalone':'integrated';showView('simulation')}else showView('home');poll()})().catch(showError).finally(()=>{document.body.inert=false});
