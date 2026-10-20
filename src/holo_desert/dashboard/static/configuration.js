import {$,esc,api} from './ui.js';
import {drone,help} from './presentation.js';

const parameters=[
  ['Protocollo MAC','network.mac.protocol','select',['csma_aloha','aloha'],'MAC'],
  ['Bitrate [bit/s]','network.acoustic.bitrate_bps','number',.001],
  ['Potenza [dB SPL]','network.acoustic.tx_power_db','number',0,200],
  ['Frequenza acustica [Hz]','network.acoustic.frequency_hz','number',.001],
  ['Larghezza di banda [Hz]','network.acoustic.bandwidth_hz','number',.001],
  ['Buffer MAC [pacchetti]','network.mac.buffer_packets','number',1,10000],
  ['Numero massimo di tentativi','network.mac.max_tx_tries','number',1,20],
  ['Conferme di ricezione (ACK)','network.mac.ack','checkbox'],
];
const get=(o,path)=>path.split('.').reduce((a,k)=>a[k],o);
let sequence=0;
function set(o,path,value){const keys=path.split('.'),key=keys.pop();keys.reduce((a,k)=>a[k],o)[key]=value}
const options=(nodes,value)=>nodes.map(n=>'<option value="'+esc(n.id)+'"'+(n.id===value?' selected':'')+'>'+esc(drone(n.id))+'</option>').join('');
export function nodeSelect(nodes,field,value){return '<select data-field="'+field+'" aria-label="'+field+'">'+options(nodes,value)+'</select>'}
function parameter(config,[label,path,type,min,max]){
  const id='network-field-'+(++sequence);
  const title=path==='network.mac.protocol'?help('MAC'):'';
  const control=type==='select'?'<select data-path="'+path+'">'+min.map(x=>'<option value="'+x+'"'+(x===get(config,path)?' selected':'')+'>'+({aloha:'ALOHA',csma_aloha:'CSMA-ALOHA'}[x]||x)+'</option>').join('')+'</select>':'<input aria-label="'+esc(label)+'" data-path="'+path+'" type="'+type+'" '+(type==='checkbox'?(get(config,path)?'checked':''):'required step="'+(path.includes('buffer')||path.includes('tries')?'1':'any')+'" min="'+min+'" '+(typeof max==='number'?'max="'+max+'"':'')+' value="'+get(config,path)+'"')+'>';
  return '<label for="'+id+'" class="'+(type==='checkbox'?'check-field':'')+'"><span>'+label+title+'</span>'+control.replace('<select ','<select id="'+id+'" ').replace('<input ','<input id="'+id+'" ')+'</label>';
}
function addRoute(root,config,src,dst,hop){
  const row=document.createElement('tr');row.innerHTML='<td>'+nodeSelect(config.nodes,'source',src)+'</td><td>'+nodeSelect(config.nodes,'destination',dst)+'</td><td>'+nodeSelect(config.nodes,'hop',hop)+'</td><td><button type="button" class="text-button danger" aria-label="Rimuovi route">Rimuovi</button></td>';
  row.querySelector('button').onclick=()=>row.remove();root.querySelector('[data-routes]').append(row);
}
export function renderFlows(root,config){
  root.innerHTML='<div data-flows></div><button type="button" class="subtle" data-add-flow>+ Aggiungi flusso</button>';
  if(config.coordination){root.innerHTML='<p class="network-note">Questo scenario usa l’applicazione heartbeat a due droni. I flussi ordinari non si applicano; il comportamento esistente viene conservato.</p>';return}
  const add=(f={})=>{
    const flow={source:config.nodes[0]?.id,destination:config.nodes[1]?.id,start:1,stop:null,interval:3,final_interval:null,payload_bytes:32,ttl:20,reply:false,message_type:'data',...f};
    const row=document.createElement('section');row.className='flow-card';
    const numeric=(key,title,min,optional=false,max=null)=>'<label><span>'+title+(key==='ttl'?help('TTL'):'')+'</span><input data-field="'+key+'" aria-label="'+title+'" type="number" step="'+(key==='payload_bytes'?'1':'any')+'" min="'+min+'" '+(max?'max="'+max+'"':'')+' '+(optional?'':'required')+' value="'+(flow[key]??'')+'"></label>';
    row.innerHTML='<header><h3>Flusso di messaggi</h3><button type="button" class="text-button danger" data-remove>Rimuovi</button></header><div class="form-grid"><label><span>Mittente</span>'+nodeSelect(config.nodes,'source',flow.source)+'</label><label><span>Destinatario</span>'+nodeSelect(config.nodes,'destination',flow.destination)+'</label>'+numeric('interval','Intervallo [s]',.001)+numeric('payload_bytes','Payload [byte]',1,false,2048)+'</div><details><summary>Tempi, validità e risposta</summary><div class="form-grid">'+numeric('start','Inizio [s]',0)+numeric('stop','Fine [s] · facoltativa',.001,true)+numeric('final_interval','Intervallo finale [s] · facoltativo',.001,true)+numeric('ttl','TTL [s]',.001)+'<label><span>Tipo del messaggio</span><input data-field="message_type" value="'+esc(flow.message_type)+'" required></label><label class="check-field"><span>Richiedi una risposta</span><input type="checkbox" data-field="reply" '+(flow.reply?'checked':'')+'></label></div></details>';
    row.querySelector('[data-remove]').onclick=()=>row.remove();root.querySelector('[data-flows]').append(row);
  };
  config.flows.forEach(add);root.querySelector('[data-add-flow]').onclick=()=>add();
}
export function readFlows(root){return [...root.querySelectorAll('.flow-card')].map(row=>Object.fromEntries([...row.querySelectorAll('[data-field]')].map(el=>[el.dataset.field,el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value])))}
export function renderNetwork(root,config,{includeFlows=true,mode=null}={}){
  root.innerHTML='<div class="form-grid">'+parameters.slice(0,3).map(p=>parameter(config,p)).join('')+'</div><p class="network-note">La potenza segue la convenzione acustica di DESERT. Cambiare soltanto il MAC permette un confronto a parità degli altri parametri.</p><details class="advanced-settings"><summary>Impostazioni avanzate</summary><div class="form-grid">'+parameters.slice(3).map(p=>parameter(config,p)).join('')+'</div><h3>Routing statico e relay '+help('Relay')+'</h3><p class="network-note">Senza una route esplicita il prossimo nodo è la destinazione stessa. Una route configurata non garantisce che il segnale arrivi.</p><div class="table-scroll network-routes"><table><thead><tr><th>Dal drone</th><th>Alla destinazione</th><th>Tramite</th><th></th></tr></thead><tbody data-routes></tbody></table></div><button class="subtle" type="button" data-add-route>+ Aggiungi route</button>'+(includeFlows?'<h3>Flussi applicativi</h3><div data-flow-editor></div>':'')+(mode!==null?'<h3>Motori dell’esperimento</h3><label class="field"><span>Modalità di esecuzione</span><select data-mode><option value="integrated">HoloOcean e DESERT · simulazione completa</option><option value="standalone">Solo DESERT · posizioni fisse configurate</option></select></label><p class="network-note">La modalità solo DESERT non simula movimento e non è disponibile per Droni in movimento e Coordinamento.</p>':'')+'</details>';
  for(const [src,routes]of Object.entries(config.network.routes))for(const [dst,hop]of Object.entries(routes))addRoute(root,config,src,dst,hop);
  root.querySelector('[data-add-route]').onclick=()=>addRoute(root,config,config.nodes[0]?.id,config.nodes[1]?.id,config.nodes[1]?.id);
  if(includeFlows)renderFlows(root.querySelector('[data-flow-editor]'),config);
  if(mode!==null)root.querySelector('[data-mode]').value=mode;
}
export function readNetwork(root,config,{includeFlows=true}={}){
  const result=structuredClone(config);
  root.querySelectorAll('[data-path]').forEach(el=>set(result,el.dataset.path,el.type==='checkbox'?el.checked:el.type==='number'?Number(el.value):el.value));
  const routes={};for(const row of root.querySelector('[data-routes]').children){const read=k=>row.querySelector('[data-field="'+k+'"]').value,src=read('source'),dst=read('destination');routes[src]??={};if(dst in routes[src])throw Error('La route '+src+' → '+dst+' è duplicata.');routes[src][dst]=read('hop')}result.network.routes=routes;
  if(includeFlows&&!config.coordination)result.flows=readFlows(root.querySelector('[data-flow-editor]'));
  return result;
}
export function bindConfiguration(getConfig,onSave,getMode=()=> 'integrated'){
  let draft;
  const populate=value=>{draft=structuredClone(value);renderNetwork($('#network-form'),draft,{mode:getMode()});$('#config-editor').value=JSON.stringify(draft,null,2)};
  $('#configure').onclick=()=>{const c=getConfig();if(!c)return;populate(c);$('#config-error').textContent='';$('#config-dialog').showModal()};
  $('#close-config').onclick=()=>$('#config-dialog').close();
  const failure=e=>$('#config-error').textContent=e.message;
  $('#form-to-json').onclick=()=>{try{$('#config-editor').value=JSON.stringify(readNetwork($('#network-form'),draft),null,2)}catch(e){failure(e)}};
  $('#json-to-form').onclick=async()=>{try{populate(await api('/api/validate',JSON.parse($('#config-editor').value)));$('#config-error').textContent=''}catch(e){failure(e)}};
  $('#config-form').onsubmit=async e=>{e.preventDefault();try{const configuration=await api('/api/validate',readNetwork($('#network-form'),draft));onSave(configuration,$('#network-form [data-mode]').value);$('#config-dialog').close()}catch(e){failure(e)}};
}
