import {$,esc,number,api,choices,fields,preserve} from './ui.js';
import {chart,strips} from './charts.js';
import {drawMap,bindMap,resetMaps} from './maps.js';
import {bindConfiguration,setNetworkCatalog,moduleName} from './configuration.js';
import {renderPackets,packetDetails,packetTone,stateHTML,eventTimeline} from './packets.js';
import {SCENARIOS,scenarioInfo,drone,typeName,help,bindHelp,setInterfaceNames,interfaceLabel} from './presentation.js';
import {bindScenarioEditor} from './scenario-editor.js';

const activeStates=['starting','running','paused','stopping'];
const palette={blue:'#3165cf',green:'#237454',amber:'#ad741f',red:'#b44343',gray:'#8795a8'};
let latest={state:'idle'},configuration=null,selectedId='e01_chat',catalog=[],libraryTab='example',view='home',analysisGroup='delivery';
let selectedNode=null,selectedPacket=null,busy=false,executionMode='integrated',homeKey='',toastTimer;
let configuredRerun=null;
const active=()=>activeStates.includes(latest.state);
const byId=id=>catalog.find(s=>s.id===id);
const GROUPS=[['reference','Reference Scenarios','E01–E06 · one communication concept each, on the analytical acoustic channel.'],['demonstration','Advanced Demonstrations','E07–E09 · native DESERT ranging, Bellhop propagation and dynamic routing.']];
const names={idle:'No simulation',starting:'Starting',running:'Simulation running',paused:'Paused',stopping:'Stopping the engines',finished:'Simulation completed',stopped:'Simulation stopped',failed:'The simulation needs attention'};
const serviceNames={not_started:'Not started',starting:'Initialising',running:'Running',stopped:'Stopped',standalone_fixture:'Fixed positions',cleanup_failed:'Shutdown error'};
const nodeStatsLabels={app_sent:'Sent by the application stack',app_received:'Received by the application stack',mac_queue:'Packets in the MAC queue',mac_data_tx:'Data frames transmitted by the MAC',mac_data_rx:'Data frames received by the MAC',mac_discarded_tx:'Aggregated MAC discards',mac_error_rx:'Aggregated MAC errors',phy_noise_errors:'Errors due to noise',phy_interference_errors:'Error outcomes in the PHY interference branch'};

function notify(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,4500)}
function showError(error){
  $('#error').hidden=!error;if(!error)return;
  const raw=error.message||String(error);let title='The operation could not be completed',message='Check the details and try again.';
  if(/Docker|docker/.test(raw)){title='DESERT is not ready';message='Check that Docker Desktop is running in Linux container mode. The holo-desert doctor command helps you check the installation.'}
  else if(/HoloOcean|Ocean package|holoocean/.test(raw)){title='HoloOcean is not ready';message='Check the HoloOcean and Ocean package installation with holo-desert doctor.'}
  else if(/valid|route|node|Flow|Waypoint|loop|scenario|Scenario|name|changed|referenc|occupied|busy|Unknown/i.test(raw)){title='Check the configuration';message=raw.length<240?raw:'Some parameters are not valid. Open the details to find the fields to correct.'}
  else if(/fetch|unavailable|network/i.test(raw)){title='Connection to the laboratory lost';message='The local server is not responding. Check that the holo-desert dashboard command is still running.'}
  $('#error-title').textContent=title;$('#error-message').textContent=message;$('#error-detail').textContent=raw;
}
function confirm(title,text,accept='Confirm'){
  const dialog=$('#confirm-dialog');$('#confirm-title').textContent=title;$('#confirm-text').textContent=text;$('#confirm-accept').textContent=accept;dialog.showModal();
  return new Promise(resolve=>{let settled=false;const done=result=>{if(settled)return;settled=true;dialog.close();resolve(result)};$('#confirm-cancel').onclick=()=>done(false);$('#confirm-accept').onclick=()=>done(true);dialog.oncancel=e=>{e.preventDefault();done(false)}});
}
async function action(task){busy=true;showError(null);render();try{return await task()}catch(e){showError(e)}finally{busy=false;render()}}
function showView(next){view=next;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==next);$('#workspace').hidden=['home','editor'].includes(next);document.querySelectorAll('.app-header [data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next);b.setAttribute('aria-current',b.dataset.view===next?'page':'false')});if(next==='analysis'&&analysisGroup==='compare')loadComparisons().catch(showError);render()}
function setConfiguration(value,mode=executionMode){configuration=structuredClone(value);executionMode=mode;homeKey='';render()}
async function loadCatalog(){const [examples,personal]=await Promise.all([api('/api/scenarios'),api('/api/user-scenarios')]);catalog=[...examples.map(x=>({...x,kind:'example'})),...personal];homeKey='';$('#personal-count').textContent=personal.length}
async function selectScenario(id){selectedId=id;configuration=await api('/api/scenarios/'+encodeURIComponent(id));executionMode='integrated';homeKey='';render()}
function uniqueName(base){const taken=new Set(catalog.map(x=>(x.name||x.id).normalize('NFKC').toLocaleLowerCase('en')));let name=base,index=2;while(taken.has(name.normalize('NFKC').toLocaleLowerCase('en')))name=base+' ('+index+++')';return name}
async function startRun(config=configuration,id=selectedId){
  configuredRerun=null;
  selectedNode=null;selectedPacket=null;resetMaps();
  await api('/api/start',{scenario:id,configuration:config,standalone:executionMode==='standalone'});
  latest=await api('/api/state');showView('simulation');
}
bindConfiguration(()=>configuration,(value,mode)=>{if(view!=='home'&&latest.run_id)configuredRerun={run_id:latest.run_id,configuration:value,scenario_id:latest.scenario_id||selectedId};setConfiguration(value,mode);notify('Settings applied to the next simulation.')},()=>executionMode);
const editor=bindScenarioEditor({onOpen:()=>showView('editor'),onClose:()=>showView('home'),confirm,notify,onStart:async(config,id)=>action(()=>startRun(config,id)),onSaved:async record=>{await loadCatalog();libraryTab='user';selectedId=record.id;setConfiguration(record.configuration);showView('home');notify('Scenario saved to your library.')}});

function renderHome(){
  if(!configuration)return;
  const key=JSON.stringify([selectedId,configuration,libraryTab,active(),busy,catalog.map(x=>[x.id,x.name])]);if(key===homeKey)return;homeKey=key;
  $('#examples-tab').classList.toggle('active',libraryTab==='example');$('#personal-tab').classList.toggle('active',libraryTab==='user');
  const list=catalog.filter(x=>x.kind===libraryTab);
  $('#scenario-card').hidden=!list.length;$('.library-layout').classList.toggle('is-empty',!list.length);
  const option=(s,i)=>{const info=scenarioInfo(s.id,{name:s.name,description:s.description});return '<button class="scenario-option '+(s.id===selectedId?'active':'')+'" data-scenario="'+esc(s.id)+'" '+(active()?'disabled title="Stop the simulation before changing scenario"':'title="'+esc(info.description)+'"')+' aria-pressed="'+(s.id===selectedId)+'"><span class="scenario-icon" aria-hidden="true">'+(['↔','⋮','⇆','≋','↗','⌁','◎','≈','⇶'][s.kind==='example'?Object.keys(SCENARIOS).indexOf(s.id):i%6])+'</span><span class="scenario-label">'+esc(info.title)+'</span><span class="scenario-number">'+esc(info.code==='Custom'?'↗':info.code)+'</span></button>'};
  // Bundled scenarios in their two groups; anything without a known group stays with the references.
  const grouped=libraryTab==='example'?GROUPS.map(([group,title,text])=>{const items=list.filter(s=>(s.group==='demonstration'?'demonstration':'reference')===group);return items.length?'<section class="scenario-group" aria-labelledby="group-'+group+'"><h3 id="group-'+group+'">'+title+'</h3><p class="micro">'+text+'</p>'+items.map(option).join('')+'</section>':''}).join(''):list.map(option).join('');
  $('#scenario-list').innerHTML=grouped||'<div class="library-empty"><h3>Your next idea starts here</h3><p>Create a scenario or duplicate one of the examples. It will still be here the next time you start the dashboard.</p></div>';
  $('#scenario-list').querySelectorAll('[data-scenario]').forEach(b=>b.onclick=()=>action(()=>selectScenario(b.dataset.scenario)));
  const item=byId(selectedId),info=scenarioInfo(selectedId,configuration);
  $('#scenario-code').textContent=info.code;$('#scenario-kind').textContent=item?.kind==='user'?'Custom scenario':'Protected example';
  $('#scenario-title').textContent=info.title;$('#description').textContent=info.description;$('#scenario-observe').textContent=info.observe;
  const diagram=info.diagram.length?info.diagram:configuration.nodes.slice(0,5).map(n=>drone(n.id));
  $('#scenario-diagram').innerHTML=diagram.map(x=>/[→←]/.test(x)?'<span class="diagram-arrow" aria-hidden="true">'+esc(x)+'</span>':'<span class="diagram-node '+(x.length>2?'wide':'')+'">'+esc(x)+'</span>').join('');
  $('#scenario-meta').innerHTML='<span><strong>'+configuration.nodes.length+'</strong> drones</span><span><strong>'+number(configuration.duration,0)+' s</strong> of simulation</span><span>'+esc(moduleName('mac',configuration.network.mac.protocol))+'</span>';
  $('#start').disabled=busy||active();$('#start').title=active()?'A simulation is already running: open Simulation to follow it.':'';
  $('#edit-scenario').hidden=item?.kind!=='user';$('#delete-scenario').hidden=item?.kind!=='user';
  for(const id of ['edit-scenario','duplicate-scenario','new-scenario','import-scenario','delete-scenario']){$('#'+id).disabled=busy||active();$('#'+id).title=active()?'Stop the simulation before editing scenarios':''}
  $('#export-scenario').href='/api/scenarios/'+encodeURIComponent(selectedId)+'/yaml';
  $('#setup-note').textContent=active()?'A simulation is running. Follow it from the Simulation tab.':'The default parameters are ready. You can change them in Settings.';
}
function renderServices(){
  const config=latest.configuration,base=config?.network?.acoustic?.phy||'bpsk_upstream',models=(config?.nodes||[]).map(n=>({node:n.id,phy:n.communication?.acoustic?.phy||base})),mixed=new Set(models.map(n=>n.phy)).size>1,patch=latest.engine_info?.phy_patch;
  // The physical layer as configured: multi-PHY interfaces, a nonacoustic medium, or the acoustic PHY per drone.
  const multi=config?.network?.multiphy,medium=config?.network?.medium||'acoustic';
  const layer=multi?'Interfaces: '+multi.interfaces.map(i=>i.id+' ('+((i.medium||'acoustic')==='optical'?'optical':'acoustic')+')').join(', '):medium!=='acoustic'?'PHY: '+moduleName('phy',medium):mixed?'Mixed PHY: '+models.map(n=>drone(n.node)+' = '+n.phy).join('; '):'PHY: '+moduleName('phy',models[0]?.phy||base)+' ('+(models[0]?.phy||base)+')';
  const phy=config?' · '+layer+(patch?' · Engine patch: '+patch:''):'';
  for(const [name,prefix]of [['holoocean','holo'],['desert','desert']]){const state=latest.services?.[name]||'not_started';$('#'+prefix+'-status').textContent=serviceNames[state]||state;$('#'+prefix+'-dot').className='status-dot '+(state==='running'?'success':state==='starting'?'info':state==='cleanup_failed'?'error':'')}
  $('#run-services').textContent='HoloOcean: '+(serviceNames[latest.services?.holoocean]||'not started')+' · DESERT: '+(serviceNames[latest.services?.desert]||'not started')+(latest.standalone?' · Network-only mode, fixed positions':'')+phy;
}
function context(){
  const s=latest,packet=(s.packets||[]).find(p=>p.id===selectedPacket),pose=s.fleet?.[selectedNode];
  $('#context-panel').classList.toggle('has-selection',!!packet||!!pose);$('#clear-selection').hidden=!packet&&!pose;
  if(packet){$('#context-title').textContent='Message details';preserve($('#context-content'),packetDetails(packet,s));return}
  if(pose){const stats=s.stats?.[selectedNode]||{},app=s.applications?.[selectedNode];$('#context-title').textContent=drone(selectedNode);
    const positions='<div class="position-values">'+['x','y','z'].map(k=>'<div><span>'+k.toUpperCase()+' [m]</span><b>'+number(pose[k],1)+'</b></div>').join('')+'</div>';
    const distances=Object.entries(s.distances_m||{}).filter(([p])=>p.split('>').includes(selectedNode)).map(([p,v])=>'<div class="distance-row"><span>From '+esc(drone(p.split('>').find(n=>n!==selectedNode)))+'</span><b>'+number(v,1)+' m</b></div>').join('');
    preserve($('#context-content'),positions+fields({'Depth':number(-pose.z,1)+' m','Heading':number(pose.yaw,1)+'°','Messages in the MAC queue':stats.mac_queue??'N/A'})+(app?'<h3>'+esc(app.role==='leader'?'Leader':'Follower')+' · '+esc(app.state==='HOLD'?'Holding':app.state==='PROCEED'?'Moving':'Sending heartbeats')+'</h3>'+fields({'Last heartbeat received':app.last_heartbeat_s==null?'N/A':number(app.last_heartbeat_s,2)+' s','Information age':app.heartbeat_age_s==null?'N/A':number(app.heartbeat_age_s,2)+' s'}):'')+'<h3>Measured distances</h3>'+distances+'<details><summary>Complete interface statistics</summary>'+fields(Object.fromEntries(Object.entries(nodeStatsLabels).map(([key,label])=>[label,stats[key]])))+'<p class="micro">DESERT counters before the application TTL check. Discards are aggregated, not per message.</p><pre>'+esc(JSON.stringify({pose,stats},null,2))+'</pre></details>');return;
  }
  $('#context-title').textContent='Explore the experiment';
  const nodes=Object.keys(s.fleet||{}),distance=Object.values(s.distances_m||{})[0];
  preserve($('#context-content'),'<div class="context-placeholder"><div class="empty-symbol">⌁</div><h3>Every link tells of an event</h3><p>Select a drone on the map to see its position and state. Choose a message below to follow its path.</p></div>'+ (nodes.length?'<h3>Choose a drone</h3><select data-node-choice aria-label="Drone to observe"><option value="">Select a drone</option>'+nodes.map(n=>'<option value="'+esc(n)+'">'+esc(drone(n))+'</option>').join('')+'</select>':'')+(nodes.length===2?fields({'Measured distance':number(distance,1)+' m'}):'')+'<details><summary>How to read the links</summary><p class="micro">Blue lines follow observed PHY transmissions and receptions. Dashed green lines mark a final delivery, possibly through relays. Grey routes are configuration only. No line guarantees that the link will remain available.</p></details>');
}
function recentMessages(){
  const packets=(latest.packets||[]).slice(-4).reverse();
  $('#pending-note').textContent=(latest.counts?.pending||0)+' pending · '+(latest.counts?.timed_out||0)+' expired';
  $('#recent-messages').innerHTML=packets.map(p=>'<button data-packet="'+esc(p.id)+'" class="message-item"><span class="message-icon '+packetTone(p)+'" aria-hidden="true">'+(p.status==='received'?'✓':p.status==='timeout_unknown_cause'?'◷':'↗')+'</span><span class="message-route">'+esc(drone(p.source)+' → '+drone(p.destination))+'<small>'+esc(typeName(p.type))+'</small></span>'+stateHTML(p)+'<span class="message-time">'+number(p.creation_time,1)+' s</span></button>').join('')||'<div class="empty-inline">The first messages will appear here after the start.</div>';
}
function insight(){
  const s=latest,c=s.configuration,distance=Object.values(s.distances_m||{})[0],series=s.series||[],last=series.at(-1);let html='';
  if(c?.name==='e03_mobility'){html='<p>The drones are <strong>'+number(distance,1)+' m</strong> apart. Compare the motion with the observed deliveries.</p><canvas id="insight-chart" class="chart"></canvas><p class="micro">Measured distance over time [m].</p>'}
  else if(c?.name==='e04_congestion'){const queues=Object.values(s.stats||{}).map(v=>v.mac_queue).filter(v=>v!=null),max=queues.length?Math.max(...queues):null;html='<p>Longest observed queue: <strong>'+number(max,0)+' packets</strong>.</p><p style="margin-top:8px">Error outcomes in the PHY interference branch: <strong>'+number(last?.phy_interference_observations,0)+'</strong> '+help('Interferenza')+'</p><p class="micro" style="margin-top:8px">Expiries are kept separate from channel errors.</p>'}
  else if(c?.name==='e05_multihop'){const p=(s.packets||[]).at(-1),relays=p?[...new Set(p.events.filter(e=>e.event==='forward'&&e.node_id!==p.source).map(e=>e.node_id))]:[];html='<p>The message is addressed to C through B. '+help('Relay')+'</p><p style="margin-top:10px">Relays observed in the latest message: <strong>'+esc(relays.map(drone).join(', ')||'waiting for the first forwarding')+'</strong>.</p><p class="micro" style="margin-top:9px">Select the message to isolate the two hops on the map.</p>'}
  else if(c?.coordination){html=Object.entries(s.applications||{}).map(([node,a])=>'<div class="heartbeat-row"><span>'+esc(a.role==='leader'?'Leader':'Follower')+' · '+esc(drone(node))+'</span><b>'+esc(a.state==='HOLD'?'Holding':a.state==='PROCEED'?'Proceeding':'Sending heartbeats')+'</b></div>').join('');const follower=Object.values(s.applications||{}).find(a=>a.role==='follower');html+='<p class="micro" style="margin-top:7px">Age of the last heartbeat: '+number(follower?.heartbeat_age_s,2)+' s.</p>'}
  else html='<p>'+esc(scenarioInfo(c?.name,c).observe)+'</p><p class="micro" style="margin-top:10px">Pending messages are not yet included in the delivery ratio.</p>';
  $('#insight-content').innerHTML=html;
  if($('#insight-chart'))chart('#insight-chart',series,[{value:p=>Object.values(p.distances_m||{})[0],color:palette.blue}]);
}
function metrics(){
  const accounting=latest.network_metrics;preserve($('#network-accounting'),accounting?'<h3>Observed network accounting</h3>'+fields(Object.fromEntries([['data_tx_frames','Data frames TX',0],['control_tx_frames','Control frames TX',0],['data_tx_bits','Data bits TX',0],['control_tx_bits','Control bits TX',0],['data_airtime_s','Data airtime [s]',6],['control_airtime_s','Control airtime [s]',6],['late_received','Received after TTL',0]].map(([key,label,digits])=>[label,number(accounting[key],digits)])))+'<p class="micro">Totals from the observed PHY events, including retransmissions. Messages received after the TTL are kept separate from valid deliveries.</p>':'');
  const s=latest,series=s.series||[],node=$('#metric-node').value,pair=$('#metric-pair').value,opts={window:Number($('#metric-window').value)};
  $('#analysis-empty').hidden=series.length>0||analysisGroup==='compare';$('#analysis-charts').hidden=!series.length||analysisGroup==='compare';$('#compare-panel').hidden=analysisGroup!=='compare';
  const multiphy=!!s.configuration?.network?.multiphy;$('#interfaces-tab').hidden=!multiphy;
  if(!multiphy&&analysisGroup==='interfaces'){analysisGroup='delivery';$('#analysis-tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.group==='delivery'))}
  $('#metric-window').disabled=analysisGroup==='compare';$('#node-filter-label').hidden=analysisGroup!=='channel';$('#pair-filter-label').hidden=!['geometry','ranging'].includes(analysisGroup);
  document.querySelectorAll('.metric-panel').forEach(p=>p.hidden=p.dataset.group!==analysisGroup);
  if(analysisGroup==='compare'){const allowed=s.state==='finished'&&!s.standalone&&!!s.configuration;$('#retain').disabled=!allowed||busy;$('#retain').title=allowed?'':'Complete an integrated run to keep its summary.';$('#compare-note').textContent=allowed?'You can keep the summary of this run.':'A summary can be kept after a completed integrated run. No comparison starts automatically.';return}
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
  else if(analysisGroup==='interfaces')interfaces(s,opts);
  else{chart('#distance-chart',series,[{value:p=>p.distances_m?.[pair],color:palette.blue}],opts);chart('#drift-chart',series,[line('wall_drift_s',palette.gray)],opts)}
  const keys=Object.keys(nodeStatsLabels);$('#mac-stats').innerHTML='<table><thead><tr><th>Drone</th>'+keys.map(k=>'<th>'+esc(nodeStatsLabels[k])+'</th>').join('')+'</tr></thead><tbody>'+Object.entries(s.stats||{}).map(([n,values])=>'<tr><td>'+esc(drone(n))+'</td>'+keys.map(k=>'<td>'+number(values[k],0)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
  $('#mac-stats').insertAdjacentHTML('beforeend',Object.entries(s.mac_specific_stats||{}).filter(([node,values])=>Object.keys(values).length).map(([node,values])=>'<details><summary>Native counters '+esc(drone(node))+'</summary>'+fields(values)+'</details>').join(''));
  $('#application-history').hidden=!(s.transitions||[]).length;
  preserve($('#application-events'),eventTimeline(s.transitions||[]));
  $('#configured-route-details').previousElementSibling.textContent={flooding:'Native Flooding: no static table',sun:'SUN: routes discovered by the native protocol',position_based:'Anchor tables (direct by default; a vehicle estimated within range receives directly)'}[s.configuration?.network?.routing]||'Configured routes (direct by default)';
  const applied=Object.entries(s.applied_configuration||{});
  preserve($('#applied-configuration'),applied.length?'<table><thead><tr><th>Drone</th><th>Module</th><th>DESERT class</th><th>Values</th></tr></thead><tbody>'+applied.flatMap(([node,records])=>records.map(r=>'<tr><td>'+esc(node==='shared'?'Shared':drone(node))+'</td><td>'+esc(r.module+(r.interface_index!=null?' · interface '+r.interface_index:'')+(r.flow_index!=null?' · flow '+r.flow_index:''))+'</td><td>'+esc(r.class)+'</td><td>'+esc(Object.entries(r.values).map(([k,v])=>k+' = '+(v==null?'N/A':v)).join(', '))+'</td></tr>')).join('')+'</tbody></table>':'<p class="micro">Available once a run has started.</p>');
  $('#configured-route-details').innerHTML=(s.configured_routes||[]).map(r=>'<div class="distance-row"><span>'+esc(drone(r.source)+' → '+drone(r.destination))+'</span><b>via '+esc(drone(r.next_hop))+'</b></div>').join('');
  preserve($('#channel-events'),eventTimeline((s.observations||[]).slice(-25).reverse()).replace(/^<ol[^>]*>|<\/ol>$/g,''));
}
// Observed multi-PHY usage: interface of every application transmission and decoded receptions.
function interfaces(s,opts){
  const names=(s.configuration?.network?.multiphy?.interfaces||[]).map(i=>i.id),colors=[palette.blue,palette.green,palette.amber];
  const events=(s.packets||[]).flatMap(p=>p.events).filter(e=>e.interface_index>0&&e.node_id);
  const end=(s.series||[]).at(-1)?.time||s.time||1,start=opts.window?Math.max(0,end-opts.window):0;
  const tx=events.filter(e=>e.event==='phy_tx_start'&&e.time>=start),nodes=(s.configuration?.nodes||[]).map(n=>n.id);
  strips('#interface-chart',nodes.map(id=>({id,label:drone(id)})),tx.map(e=>({row:e.node_id,time:e.time,key:e.interface_index})),Object.fromEntries(names.map((n,i)=>[i+1,colors[i%colors.length]])),{start,end});
  $('#interface-key').innerHTML=names.map((n,i)=>'<i class="dot-key" style="background:'+colors[i%colors.length]+'"></i>'+esc(interfaceLabel(i+1))).join(' ');
  const count=(node,index,event,outcome)=>events.filter(e=>e.node_id===node&&e.interface_index===index&&e.event===event&&(!outcome||e.outcome===outcome)).length;
  const switches=node=>{const seq=tx.filter(e=>e.node_id===node).map(e=>e.interface_index);return seq.filter((v,i)=>i&&v!==seq[i-1]).length};
  $('#interface-table').innerHTML='<table><thead><tr><th>Drone</th>'+names.map((n,i)=>'<th>'+esc(interfaceLabel(i+1))+' · TX / RX decoded</th>').join('')+'<th>Interface switches in TX</th></tr></thead><tbody>'+nodes.map(node=>'<tr><td>'+esc(drone(node))+'</td>'+names.map((n,i)=>'<td>'+count(node,i+1,'phy_tx_start')+' / '+count(node,i+1,'phy_rx_end','decoded')+'</td>').join('')+'<td>'+switches(node)+'</td></tr>').join('')+'</tbody></table>';
}
// Native ranging estimates against the HoloOcean geometry; never mixed into one value.
function ranging(s,pair,opts){
  const data=s.ranging||{series:{},latest:[]},points=data.series?.[pair]||[],observers=[...new Set(points.flatMap(p=>Object.keys(p.estimates)))],colors=[palette.blue,palette.green,palette.amber,palette.red];
  const empty=!data.latest?.length;$('#ranging-empty').hidden=!empty;['#ranging-chart','#ranging-key','#ranging-table','#ranging-note'].forEach(id=>$(id).hidden=empty);
  if(empty){$('#ranging-empty').textContent='No distance estimates in this run. Native estimates come with a ranging MAC (Ranging-TokenBus or Ranging-TDMA), once per second of simulated time.';return}
  chart('#ranging-chart',points,[{value:p=>p.geometric_distance_m,color:palette.gray},...observers.map((o,i)=>({value:p=>p.estimates[o],color:colors[i%colors.length]}))],opts);
  $('#ranging-key').innerHTML='<i class="line-key gray"></i>HoloOcean geometric distance · reference'+observers.map((o,i)=>'<i class="line-key" style="background:'+colors[i%colors.length]+'"></i>DESERT estimate measured by '+esc(drone(o))).join('');
  const protocol=data.latest[0]?.protocol||'',sound=s.configuration?.network?.acoustic?.sound_speed_mps;
  $('#ranging-table').innerHTML='<table><thead><tr><th>Pair</th><th>Observer</th><th>DESERT estimate [m]</th><th>Time of flight [s]</th><th>Geometric distance [m]</th><th>Difference [m]</th><th>Reading [s]</th><th>Last change [s]</th></tr></thead><tbody>'+data.latest.map(r=>'<tr><td>'+esc(drone(r.peer_a)+' ↔ '+drone(r.peer_b))+'</td><td>'+esc(drone(r.observer))+'</td><td>'+(r.valid?number(r.distance_m,2):'Not yet measured')+'</td><td>'+(r.valid?number(r.travel_time_s,6):'N/A')+'</td><td>'+number(r.geometric_distance_m,2)+'</td><td>'+number(r.error_m,2)+'</td><td>'+number(r.time,1)+'</td><td>'+number(r.changed_time,1)+'</td></tr>').join('')+'</tbody></table>';
  $('#ranging-note').textContent='Estimate: time of flight measured by the '+protocol+' MAC × configured sound speed ('+number(sound,0)+' m/s). The module does not expose the time of the measurement: the geometric distance is the latest HoloOcean sample at the time of reading. An estimate stays unchanged until a new measurement arrives: the last change shows since when. The difference is estimate minus reference.';
}
async function loadComparisons(){
  const data=await api('/api/comparisons'),runs=data.runs;if(!runs.length){$('#comparison').innerHTML='<p>No summary kept. Complete an integrated run to start the comparison.</p>';return}
  const rows=[['Messages generated',x=>x.generated],['Messages delivered',x=>x.received],['Messages expired',x=>x.timed_out],['Pending',x=>x.pending],['Delivery ratio',x=>x.pdr_resolved==null?'N/A':number(x.pdr_resolved*100,1)+'%'],['Mean goodput [bit/s]',x=>number(x.goodput_bps,1)],['Throughput envelope [bit/s]',x=>number(x.application_wire_throughput_bps,1)],['Mean latency [s]',x=>number(x.mean_latency_s,3)],['PHY interference branch outcomes',x=>x.phy_observations.interference_error],['PHY noise errors',x=>x.phy_observations.noise_error],['PHY not synchronised',x=>x.phy_observations.not_synchronized],['Sampled MAC queue peak',x=>x.mac_queue_peak??'N/A']];
  rows.push(['PHY data frames TX',x=>x.network_metrics?.data_tx_frames??'N/A'],['PHY control frames TX',x=>x.network_metrics?.control_tx_frames??'N/A'],['PHY data bits TX',x=>x.network_metrics?.data_tx_bits??'N/A'],['PHY control bits TX',x=>x.network_metrics?.control_tx_bits??'N/A'],['Data airtime [s]',x=>number(x.network_metrics?.data_airtime_s,6)],['Control airtime [s]',x=>number(x.network_metrics?.control_airtime_s,6)],['Arrivals after TTL',x=>x.network_metrics?.late_received??'N/A'],['Aggregated MAC discards',x=>{const values=Object.values(x.mac_stats||{}).map(n=>n.mac_discarded_tx);return values.length&&values.every(Number.isFinite)?values.reduce((a,b)=>a+b,0):'N/A'}]);
  $('#comparison').innerHTML='<p>'+esc(data.equivalent?'The common parameters match: only the MAC changes.':runs.length===1?'First summary kept. Run again changing only the MAC.':'The common parameters differ or the MAC is the same: the comparison is not controlled.')+'</p><div class="table-scroll"><table><thead><tr><th>Metric</th>'+runs.map(r=>'<th>'+esc(moduleName('mac',r.mac))+'</th>').join('')+'</tr></thead><tbody>'+rows.map(([name,read])=>'<tr><td>'+name+'</td>'+runs.map(r=>'<td>'+esc(read(r.summary))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><p class="micro">At most six summaries are kept in memory. Negative results remain visible. The same configured geometry and seed do not guarantee identical measured trajectories.</p>';
}
function render(){
  const s=latest,hasRun=s.state!=='idle'&&!!s.configuration;renderServices();setInterfaceNames(s.configuration);
  $('#configure').disabled=busy||active()||!configuration||view==='editor'||(view==='home'&&libraryTab==='user'&&!catalog.some(s=>s.kind==='user'));$('#configure').title=active()?'Settings can be changed once the simulation has stopped.':'Parameters of the next simulation';
  renderHome();if(view==='editor'){editor.resize();return}
  $('#run-status').textContent=names[s.state]||s.state;$('#run-status').className='status-label '+s.state+(s.state==='starting'?' loading-dot':'');
  $('#run-time').textContent=number(s.time||0,1)+' / '+number(s.configuration?.duration||configuration?.duration||0,0)+' s';
  $('#run-title').textContent=hasRun?scenarioInfo(s.configuration.name,s.configuration).title:'Your simulation';
  $('#scenario-hint').textContent=hasRun?scenarioInfo(s.configuration.name,s.configuration).observe:'Choose a scenario to start your experiment.';
  $('#metrics-summary').hidden=!hasRun;
  for(const id of ['pause','stop','export','rerun','reset'])$('#'+id).hidden=!hasRun;
  $('#pause').hidden=!['running','paused'].includes(s.state);$('#pause').disabled=busy||!s.pause_supported;$('#pause').textContent=s.state==='paused'?'▶ Resume':'Ⅱ Pause';
  $('#stop').hidden=!['starting','running','paused'].includes(s.state);$('#stop').disabled=busy;
  $('#rerun').hidden=!['finished','stopped','failed'].includes(s.state);$('#rerun').disabled=busy;
  $('#reset').hidden=!['finished','stopped','failed'].includes(s.state);$('#reset').disabled=busy;
  const counts=s.counts||{},resolved=(counts.received||0)+(counts.timed_out||0),last=s.series?.at(-1);
  $('#generated').textContent=hasRun?number(counts.generated||0,0):'—';$('#received').textContent=hasRun?number(counts.received||0,0):'—';$('#delivery-rate').textContent=resolved?number(counts.received/resolved*100,1)+'%':'—';$('#mean-latency').textContent=last?.mean_latency_s==null?'—':number(last.mean_latency_s,3)+' s';
  const nodes=Object.keys(s.fleet||{}),pairs=Object.keys(s.distances_m||{});
  choices('#metric-node',nodes,null,drone);choices('#metric-pair',pairs,null,p=>p.split('>').map(drone).join(' ↔ '));choices('#packet-node',nodes,'All drones',drone);choices('#packet-destination',nodes,'All recipients',drone);choices('#packet-type',[...new Set((s.packets||[]).map(p=>p.type))],'All types',typeName);
  const indices=[...new Set((s.packets||[]).flatMap(p=>p.events.filter(e=>e.event==='phy_tx_start'&&e.interface_index>0).map(e=>String(e.interface_index))))].sort();
  choices('#packet-interface',indices,'All interfaces',v=>interfaceLabel(Number(v)));$('#packet-interface-label').hidden=!s.configuration?.network?.multiphy&&!indices.length;
  if(selectedNode&&!nodes.includes(selectedNode))selectedNode=null;
  if(view==='simulation'){
    $('#map-empty').hidden=nodes.length>0;$('#map-empty-title').textContent=s.state==='starting'?'Preparing the simulators':s.state==='failed'?'The experiment did not start':'Your experiment will appear here';
    $('#map-empty-text').textContent=s.state==='starting'?'Initialising HoloOcean and DESERT. The first Docker start-up may take a few minutes.':s.state==='failed'?'See the error message and the diagnostic details.':'Select a scenario and start the simulation.';
    $('#position-source').textContent=s.standalone?'Fixed configured positions · no HoloOcean physics':'Positions measured by HoloOcean';
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
for(const id of ['trails','route-layer','phy-layer','delivery-layer','packet-node','packet-status','packet-event','packet-destination','packet-type','packet-interface','metric-window','metric-node','metric-pair'])$('#'+id).onchange=render;
for(const id of ['filter','packet-from','packet-to'])$('#'+id).oninput=render;
$('#analysis-tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{analysisGroup=b.dataset.group;$('#analysis-tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));if(analysisGroup==='compare')loadComparisons().catch(showError);render()});
$('#retain').onclick=()=>action(async()=>{await api('/api/comparison',{});await loadComparisons();notify('Summary kept in memory.')});
$('#guide-open').onclick=()=>$('#guide-dialog').showModal();$('#about-open').onclick=()=>$('#about-dialog').showModal();document.querySelectorAll('[data-close-dialog]').forEach(b=>b.onclick=()=>b.closest('dialog').close());$('#dismiss-error').onclick=()=>showError(null);bindHelp();
$('#duplicate-scenario').onclick=()=>action(async()=>{const copy=structuredClone(configuration);copy.name=uniqueName(scenarioInfo(selectedId,configuration).title+' · copy');if(SCENARIOS[selectedId])copy.description=SCENARIOS[selectedId].description;await editor.open(copy)});
$('#edit-scenario').onclick=()=>action(async()=>{const record=await api('/api/user-scenarios/'+encodeURIComponent(selectedId));await editor.open(record.configuration,record)});
$('#new-scenario').onclick=()=>action(async()=>{const config=await api('/api/scenarios/e01_chat');config.name='';config.description='';config.duration=30;config.flows[0].reply=false;config.flows[0].stop=null;config.flows[0].interval=3;await editor.open(config)});
$('#delete-scenario').onclick=()=>action(async()=>{if(!await confirm('Delete this scenario?','The custom scenario “'+configuration.name+'” will be deleted from the library. The examples are not modified.','Delete scenario'))return;await api('/api/user-scenarios/'+selectedId+'?revision='+encodeURIComponent(byId(selectedId).revision),undefined,'DELETE');await loadCatalog();libraryTab='user';await selectScenario(catalog.find(x=>x.kind==='user')?.id||'e01_chat');notify('Custom scenario deleted.')});
$('#import-scenario').onclick=()=>$('#import-file').click();$('#import-file').onchange=()=>action(async()=>{const file=$('#import-file').files[0];if(!file)return;try{const config=await api('/api/user-scenarios/import',{yaml:await file.text()});if(SCENARIOS[config.name])config.name=uniqueName(SCENARIOS[config.name].title+' · imported');await editor.open(config);notify('YAML imported into the editor. Check the data before saving.')}finally{$('#import-file').value=''}});
window.addEventListener('resize',()=>{if(view==='editor')editor.resize();else render()});
async function poll(){try{const state=await api('/api/state');if(state.run_id!==latest.run_id){selectedNode=null;selectedPacket=null;resetMaps()}latest=state;if(state.error)showError(state.error);render();$('#updated').textContent='Updated at '+new Date().toLocaleTimeString('en-US')}catch(e){showError(e)}setTimeout(poll,500)}
// Keep controls inert until bootstrap has chosen the initial view.
(async()=>{setNetworkCatalog(await api('/api/network-catalog'));await loadCatalog();await selectScenario('e01_chat');latest=await api('/api/state');if(latest.configuration&&latest.state!=='idle'){const known=catalog.find(x=>x.id===latest.configuration.name||x.name===latest.configuration.name);selectedId=known?.id||'e01_chat';configuration=latest.configuration;executionMode=latest.standalone?'standalone':'integrated';showView('simulation')}else showView('home');poll()})().catch(showError).finally(()=>{document.body.inert=false});
