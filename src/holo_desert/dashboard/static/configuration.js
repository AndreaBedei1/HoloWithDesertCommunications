import {$,esc,api} from './ui.js';

const parameters=[
  ['MAC','network.mac.protocol','select',['csma_aloha','aloha']],
  ['Bitrate [bit/s]','network.acoustic.bitrate_bps','number',.001],
  ['Frequenza [Hz]','network.acoustic.frequency_hz','number',.001],
  ['Banda [Hz]','network.acoustic.bandwidth_hz','number',.001],
  ['Potenza [dB SPL]','network.acoustic.tx_power_db','number',0,200],
  ['Buffer MAC [pacchetti]','network.mac.buffer_packets','number',1,10000],
  ['Massimo tentativi','network.mac.max_tx_tries','number',1,20],
  ['ACK','network.mac.ack','checkbox'],
];
const flowParameters=[['start','Inizio [s]',0],['stop','Fine [s] (vuoto: durata)',0,true],['interval','Intervallo [s]',.001],['final_interval','Intervallo finale [s]',.001,true],['payload_bytes','Payload [B]',1,false,2048],['ttl','TTL [s]',.001]];
let draft;
function get(obj,path){return path.split('.').reduce((o,k)=>o[k],obj)}
function set(obj,path,value){const keys=path.split('.'),key=keys.pop();keys.reduce((o,k)=>o[k],obj)[key]=value}
function options(values,value){return values.map(x=>'<option value="'+esc(x)+'"'+(x===value?' selected':'')+'>'+esc(x)+'</option>').join('')}
function nodeSelect(field,value){return '<select data-field="'+field+'">'+options(draft.nodes.map(n=>n.id),value)+'</select>'}
function routeRow(src,dst,hop){
  const tr=document.createElement('tr');tr.innerHTML='<td>'+nodeSelect('source',src)+'</td><td>'+nodeSelect('destination',dst)+'</td><td>'+nodeSelect('hop',hop)+'</td><td><button type="button">Rimuovi</button></td>';
  tr.querySelector('button').onclick=()=>tr.remove();$('#route-rows').append(tr);
}
function flowRow(flow={}){
  const row=document.createElement('fieldset');row.className='flow form-grid';
  const f={source:draft.nodes[0].id,destination:draft.nodes[1].id,start:1,stop:null,interval:3,final_interval:null,payload_bytes:32,ttl:20,reply:false,message_type:'data',...flow};
  row.innerHTML='<label>Sorgente'+nodeSelect('source',f.source)+'</label><label>Destinazione'+nodeSelect('destination',f.destination)+'</label>'+flowParameters.map(([key,label,min,optional,max])=>'<label>'+label+'<input data-field="'+key+'" type="number" step="'+(key==='payload_bytes'?'1':'any')+'" min="'+min+'" '+(max?'max="'+max+'"':'')+' '+(optional?'':'required')+' value="'+(f[key]??'')+'"></label>').join('')+'<label>Tipo messaggio<input data-field="message_type" required value="'+esc(f.message_type)+'"></label><label>Richiedi reply<input type="checkbox" data-field="reply" '+(f.reply?'checked':'')+'></label><button type="button">Rimuovi flusso</button>';
  row.querySelector('button').onclick=()=>row.remove();$('#flow-rows').append(row);
}
function populate(config){
  draft=structuredClone(config);
  $('#network-form').innerHTML=parameters.map(([label,path,type,min,max])=>'<label>'+label+(type==='select'?'<select data-path="'+path+'">'+options(min,get(draft,path))+'</select>':'<input data-path="'+path+'" type="'+type+'" '+(type==='checkbox'?(get(draft,path)?'checked':''):'required step="'+(path.includes('buffer')||path.includes('tries')?'1':'any')+'" min="'+min+'" '+(max!=null?'max="'+max+'"':'')+' value="'+get(draft,path)+'"')+'>')+'</label>').join('');
  $('#route-rows').innerHTML='';for(const [src,routes]of Object.entries(draft.network.routes))for(const [dst,hop]of Object.entries(routes))routeRow(src,dst,hop);
  $('#flow-rows').innerHTML='';draft.flows.forEach(flowRow);
  $('#add-flow').disabled=draft.coordination;
  if(draft.coordination)$('#flow-rows').textContent='E06 utilizza l’applicazione heartbeat esistente; parametri dei flussi ordinari non applicabili.';
  $('#config-editor').value=JSON.stringify(draft,null,2);
}
function read(){
  const result=structuredClone(draft);
  document.querySelectorAll('[data-path]').forEach(el=>set(result,el.dataset.path,el.type==='checkbox'?el.checked:el.type==='number'?Number(el.value):el.value));
  const routes={};for(const tr of $('#route-rows').children){const value=k=>tr.querySelector('[data-field="'+k+'"]').value,src=value('source'),dst=value('destination');routes[src]??={};if(dst in routes[src])throw Error('Route duplicata: '+src+' → '+dst);routes[src][dst]=value('hop')}result.network.routes=routes;
  result.flows=[...document.querySelectorAll('.flow')].map(row=>Object.fromEntries([...row.querySelectorAll('[data-field]')].map(el=>[el.dataset.field,el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value])));
  return result;
}
export function bindConfiguration(getConfig,onSave){
  $('#configure').onclick=()=>{populate(getConfig());$('#config-error').textContent='';$('#config-dialog').showModal()};
  $('#close-config').onclick=()=>$('#config-dialog').close();
  $('#add-route').onclick=()=>routeRow(draft.nodes[0].id,draft.nodes[1].id,draft.nodes[1].id);
  $('#add-flow').onclick=()=>flowRow();
  const failure=e=>$('#config-error').textContent=e.message;
  $('#form-to-json').onclick=()=>{try{$('#config-editor').value=JSON.stringify(read(),null,2)}catch(e){failure(e)}};
  $('#json-to-form').onclick=async()=>{try{populate(await api('/api/validate',JSON.parse($('#config-editor').value)));$('#config-error').textContent=''}catch(e){failure(e)}};
  $('#config-form').onsubmit=async e=>{e.preventDefault();try{const config=await api('/api/validate',read());onSave(config);$('#config-dialog').close()}catch(e){failure(e)}};
}
