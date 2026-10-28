import {addParameterHelp,parameterHelp} from './parameter-help.js';
import {$,esc,api} from './ui.js';
import {drone} from './presentation.js';
import {openProfiles} from './network-profiles.js';

let catalog={modules:[],selectors:{}};
// The configuration each form currently shows: values without a control are kept from it.
const rendered=new WeakMap();
export function setNetworkCatalog(value){catalog=value}
const mod=id=>catalog.modules.find(m=>m.id===id);
const selector=key=>catalog.selectors?.[key];
export const moduleName=(layer,id)=>{const module=catalog.modules.find(m=>m.layer.toLowerCase()===layer&&m.id===id);return module?module.name+(module.experimental?' - experimental':''):id};
const get=(o,path)=>path.split('.').reduce((a,k)=>a?.[k],o);
let sequence=0;
function set(o,path,value){const keys=path.split('.'),key=keys.pop();keys.reduce((a,k)=>a[k]??={},o)[key]=value}
const options=(nodes,value)=>nodes.map(n=>'<option value="'+esc(n.id)+'"'+(n.id===value?' selected':'')+'>'+esc(drone(n.id))+'</option>').join('');
export function nodeSelect(nodes,field,value){return '<select data-field="'+field+'" aria-label="'+field+'">'+options(nodes,value)+'</select>'}
function addHelp(root){addParameterHelp(root)}
const tip=text=>'<button type="button" class="help" data-help="'+esc(text)+'" aria-label="Explain parameter">?</button>';
// Nonacoustic media and their two primary controls; everything else is in the advanced section.
const MEDIA=['optical','em'],PRIMARY={acoustic:['network.acoustic.bitrate_bps','network.acoustic.tx_power_db'],optical:['network.optical.tx_power_w','network.optical.bitrate_bps'],em:['network.em.tx_power_dbm','network.em.bitrate_bps']};
const numeric=type=>['number','integer','int'].includes(type),checkbox=type=>['boolean','bool','checkbox'].includes(type);
const format=value=>typeof value==='number'?value.toLocaleString('en-US',{maximumFractionDigits:15}):String(value);
const unitLabel=p=>p.unit&&p.unit!=='dimensionless'&&numeric(p.type)?' ['+p.unit+']':'';
// Meaning, unit, default and constraints of a control, all taken from the catalogue.
export function helpText(p){
  const unit=numeric(p.type)?p.unit||'dimensionless':'',suffix=unit&&unit!=='dimensionless'?' '+unit:'',picked=p.choices?.find(c=>(c.value??c)===p.default);
  const fallback=p.default===undefined||p.default===null||p.default===''?'':checkbox(p.type)?(p.default?'enabled':'disabled'):picked?picked.label??picked:Array.isArray(p.default)?'':format(p.default)+suffix;
  const range=p.min!=null&&p.max!=null?'from '+format(p.min)+' to '+format(p.max)+suffix:p.min!=null?'at least '+format(p.min)+suffix:p.max!=null?'at most '+format(p.max)+suffix:'';
  const limits=[range,p.constraint].filter(Boolean).join('; ')||(numeric(p.type)?'any finite value':'');
  return [p.help||p.label,unit?'Unit: '+unit+'.':'',fallback?'Default: '+fallback+'.':'',limits?'Constraints: '+limits+'.':''].filter(Boolean).join(' ');
}
const choice=(value,label,selected,reason='')=>'<option value="'+esc(value)+'"'+(selected?' selected':'')+(reason?' disabled':'')+'>'+esc(label+(reason?' — not available: '+reason:''))+'</option>';
const unavailable=items=>items.length?' Not available: '+items.map(([label,reason])=>label+' ('+reason+')').join('; ')+'.':'';
const note=reason=>reason?'<small class="unavailable-note">Not available: '+esc(reason)+'</small>':'';
function parameter(config,p,{path=p.path,optional=false,value=get(config,p.path)??p.default,reason=''}={}){
  const id='network-field-'+(++sequence),label=p.label+unitLabel(p),type=p.type;
  const attrs=' id="'+id+'" aria-label="'+esc(label)+'" data-path="'+esc(path)+'"'+(reason?' disabled':'');
  let control;
  if(p.choices?.length)control='<select'+attrs+'>'+p.choices.map(c=>{const v=c.value??c.id??c;return choice(v,c.label??c.name??v,v===value)}).join('')+'</select>';
  else if(checkbox(type))control='<input'+attrs+' type="checkbox" '+(value?'checked':'')+'>';
  else control='<input'+attrs+' type="number" step="'+(['integer','int'].includes(type)?'1':'any')+'" '+(optional?'':'required')+' '+(p.min!=null?'min="'+p.min+'" ':'')+(p.max!=null?'max="'+p.max+'" ':'')+' value="'+esc(value??'')+'">';
  return '<label for="'+id+'" class="'+(checkbox(type)?'check-field':'')+'"><span>'+esc(label)+tip(helpText(p)+(reason?' Not available: '+reason+'.':''))+'</span>'+control+note(reason)+'</label>';
}
const mediumOf=config=>config.network.medium||'acoustic',propagationOf=config=>config.network.acoustic.propagation||'underwater';
const mediumLabel=value=>(selector('medium')?.choices||[]).find(c=>c.value===value)?.label||value;
const names=ids=>ids.map(id=>mod(id)?.name||id).join(' or ');
// Catalogued features stay disabled until the catalogue marks them verified end to end.
const unverified=id=>{const m=mod(id);return m&&!m.operational?m.unavailable||m.reason||'not verified end to end':''};
const overridden=config=>config.nodes.some(n=>Object.values(n.communication?.acoustic||{}).some(v=>v!==null&&v!==undefined&&v!==''));
// Why an option cannot be combined with the rest of the configuration ('' when it can).
function moduleReason(config,layer,m){
  const n=config.network,medium=mediumOf(config),routing=n.routing||'static',mac=mod(n.mac.protocol);
  if(!m.operational)return m.unavailable||m.reason||'not verified end to end';
  if(layer==='mac'){
    if(!(m.compatibility?.media||['acoustic']).includes(medium))return 'not verified with '+mediumLabel(medium).toLowerCase()+' technology';
    if(n.multiphy&&m.id!=='csma_aloha')return 'multi-PHY is verified only with CSMA-ALOHA';
    const route=mod(routing);
    if(route?.compatibility?.mac&&!route.compatibility.mac.includes(m.id))return route.name+' routing requires '+names(route.compatibility.mac);
    if(m.compatibility?.routing&&!m.compatibility.routing.includes(routing))return 'requires '+names(m.compatibility.routing)+' routing';
  }
  if(layer==='routing'){
    if(mac?.compatibility?.routing&&!mac.compatibility.routing.includes(m.id))return 'not supported by '+mac.name;
    if(m.compatibility?.mac&&!m.compatibility.mac.includes(n.mac.protocol))return 'requires '+names(m.compatibility.mac);
    if(m.id==='sun'&&n.mac.ack)return 'requires the MAC without ACK';
    if(m.id!=='static'&&medium!=='acoustic')return 'with '+mediumLabel(medium).toLowerCase()+' technology only static routing is verified';
    if(m.id!=='static'&&n.multiphy)return 'multi-PHY is verified only with static routing';
    if(m.compatibility?.propagation&&!m.compatibility.propagation.includes(propagationOf(config)))return 'not verified with WOSS propagation';
    if(m.id==='position_based'&&config.nodes.every(node=>(node.waypoints||[]).length))return 'at least one drone without waypoints is needed as an anchor';
    if((config.flows||[]).some(f=>(f.generator||'python')!=='python'&&!(mod(f.generator==='desert_vbr'?'native_vbr':'native_cbr')?.compatibility?.routing||[m.id]).includes(m.id)))return 'the native CBR/VBR generators are not verified with this routing';
  }
  if(layer==='phy'&&m.id!=='bpsk_upstream'&&propagationOf(config)==='woss')return 'WOSS uses the original BPSK PHY';
  return '';
}
function moduleSelect(config,layer,path,label){
  const value=get(config,path)??(path.endsWith('.phy')?'bpsk_upstream':'static');
  const rows=catalog.modules.filter(m=>m.layer.toLowerCase()===layer&&!(layer==='phy'&&[...MEDIA,'woss'].includes(m.id))).map(m=>({m,reason:m.id===value?'':moduleReason(config,layer,m)}));
  const current=rows.find(r=>r.m.id===value)?.m;
  return '<label><span>'+esc(label)+tip((current?.description||'')+' Only adapters verified in the laboratory can be selected.'+unavailable(rows.filter(r=>r.reason).map(r=>[r.m.name,r.reason])))+'</span><select aria-label="'+esc(label)+'" data-path="'+path+'" data-module required>'+(!current?.operational?'<option value="" selected disabled>Select an operational module</option>':'')+rows.map(({m,reason})=>choice(m.id,moduleName(layer,m.id),m.id===value,reason)).join('')+'</select></label>';
}
// Each power event carries the native unit of one technology (POWER_UNITS in scenarios/config.py).
const POWER_UNITS={acoustic:['tx_power_db','dB re 1 µPa'],optical:['tx_power_w','W'],em:['tx_power_dbm','dBm']};
function mediumReason(config,value){
  const [unit,label]=POWER_UNITS[value];
  if((config.power_events||[]).some(e=>e[unit]==null))return 'the power events of the scenario must be in '+label+' (field '+unit+', editable in the JSON)';
  if(value==='acoustic')return '';
  const n=config.network,need=mod(value)?.compatibility||{};
  if(unverified(value))return unverified(value);
  if(n.multiphy)return 'cannot be combined with multi-PHY';
  if(propagationOf(config)!=='underwater')return 'cannot be combined with WOSS';
  if(need.mac&&!need.mac.includes(n.mac.protocol)||need.routing&&!need.routing.includes(n.routing||'static'))return 'verified only with '+names(need.mac||[])+' and '+names(need.routing||[])+' routing';
  if(overridden(config))return 'remove the per-drone acoustic overrides';
  if(value==='optical'&&config.nodes.some(node=>[node.position,...(node.waypoints||[]).map(w=>w.slice(1))].some(p=>!(p[2]>=-20&&p[2]<0))))return 'optical noise is tabulated only between 0 and 20 m depth';
  return '';
}
// MAC and routing a catalogued feature has been verified with (its compatibility block).
const stackReason=(config,id)=>{const need=mod(id)?.compatibility||{},n=config.network;return need.mac&&!need.mac.includes(n.mac.protocol)?'not verified with '+(mod(n.mac.protocol)?.name||n.mac.protocol):need.routing&&!need.routing.includes(n.routing||'static')?'not verified with '+(mod(n.routing||'static')?.name||n.routing)+' routing':''};
function propagationReason(config,value){
  if(value!=='woss')return '';
  if(unverified('woss'))return unverified('woss');
  const n=config.network,depth=n.woss?.water_depth_m??100,points=config.nodes.flatMap(node=>[node.position,...(node.waypoints||[]).map(w=>w.slice(1))]);
  if(stackReason(config,'woss'))return stackReason(config,'woss');
  if(mediumOf(config)!=='acoustic')return 'acoustic technology only';
  if(n.multiphy)return 'multi-PHY uses the analytical propagation';
  if((n.acoustic.phy||'bpsk_upstream')!=='bpsk_upstream'||config.nodes.some(node=>(node.communication?.acoustic?.phy||'bpsk_upstream')!=='bpsk_upstream'))return 'requires the original BPSK PHY on every drone';
  if(points.some(p=>!(p[2]>-depth+.1&&p[2]<-.1))||config.nodes.some((a,i)=>config.nodes.slice(i+1).some(b=>Math.hypot(a.position[0]-b.position[0],a.position[1]-b.position[1])<1)))return 'needs 1 m of horizontal separation and 0.1 m from the surface and the seabed';
  return '';
}
function multiphyReason(config){
  const n=config.network;
  if(unverified('multi_phy'))return unverified('multi_phy');
  if(mediumOf(config)!=='acoustic')return 'acoustic technology only';
  if(propagationOf(config)!=='underwater')return 'requires the analytical propagation';
  if(n.mac.protocol!=='csma_aloha'||n.mac.ack)return 'requires CSMA-ALOHA without ACK';
  if((n.routing||'static')!=='static')return 'requires static routing';
  return '';
}
function selectorSelect(config,key,reasonOf){
  const s=selector(key);if(!s)return '';
  const value=get(config,s.path)??s.default,rows=s.choices.map(c=>({c,reason:c.value===value?'':reasonOf(config,c.value)}));
  return '<label><span>'+esc(s.label)+tip(helpText(s)+unavailable(rows.filter(r=>r.reason).map(r=>[r.c.label,r.reason])))+'</span><select aria-label="'+esc(s.label)+'" data-path="'+esc(s.path)+'" data-rerender>'+rows.map(({c,reason})=>choice(c.value,c.label,c.value===value,reason)).join('')+'</select></label>';
}
const ackReason=config=>(config.network.routing||'static')==='sun'?'SUN requires the MAC without ACK':config.network.multiphy?'multi-PHY requires the MAC without ACK':'';
const primaryPaths=Object.values(PRIMARY).flat();
function selectedParameters(config,layer,id){return (catalog.modules.find(m=>m.layer.toLowerCase()===layer&&m.id===id)?.parameters||[]).filter(p=>(!p.visible_when||p.visible_when.values.includes(get(config,p.visible_when.path)??'legacy'))&&!primaryPaths.includes(p.path)&&!p.path.endsWith('slot_assignment')&&!['network.mac.protocol','network.acoustic.phy','network.routing'].includes(p.path)).map(p=>parameter(config,p,{reason:p.path==='network.mac.ack'&&!get(config,p.path)?ackReason(config):''})).join('')}
const sspRow=(p,fixed)=>'<tr data-ssp-row><td><input type="number" step="any" min="0" required aria-label="Depth of the SSP point [m]" data-ssp="depth_m" value="'+esc(p.depth_m)+'"></td><td><input type="number" step="any" min="1000" max="2000" required aria-label="Sound speed of the SSP point [m/s]" data-ssp="speed_mps" value="'+esc(p.speed_mps)+'"></td><td><button type="button" class="text-button danger" data-remove-ssp aria-label="Remove SSP point"'+(fixed?' disabled title="At least two points are needed"':'')+'>Remove</button></td></tr>';
function sspEditor(config){
  const s=selector('ssp')||{label:'SSP profile'},points=config.network.woss?.ssp||s.default||[];
  const text=[s.help,'Unit: depth in m, sound speed in m/s.',s.default?'Default: '+s.default.map(p=>format(p.depth_m)+' m → '+format(p.speed_mps)+' m/s').join(', ')+'.':'',s.constraint?'Constraints: '+s.constraint+'.':''].filter(Boolean).join(' ');
  return '<h3>'+esc(s.label)+tip(text)+'</h3><div class="table-scroll network-routes"><table><thead><tr><th>Depth [m]</th><th>Sound speed [m/s]</th><th></th></tr></thead><tbody data-ssp-points>'+points.map(p=>sspRow(p,points.length<=2)).join('')+'</tbody></table></div><button type="button" class="subtle" data-add-ssp>+ SSP point</button>';
}
function mediumSection(config){
  const medium=mediumOf(config);
  if(medium!=='acoustic'){
    const module=mod(medium),parameters=(module?.parameters||[]).filter(p=>!PRIMARY[medium].includes(p.path));
    return '<p class="network-note">'+esc(module?.description||'')+' '+esc(module?.experimental?'Verified experimental module.':'')+'</p><div class="form-grid">'+parameters.map(p=>parameter(config,p)).join('')+'</div>';
  }
  const woss=propagationOf(config)==='woss',w=mod('woss');
  return '<div class="form-grid">'+selectorSelect(config,'propagation',propagationReason)+'</div>'+(woss?'<p class="network-note">'+esc(w?.description||'')+'</p><div class="form-grid">'+(w?.parameters||[]).map(p=>parameter(config,p)).join('')+'</div>'+sspEditor(config):'');
}
// Default interfaces use disjoint bands so a new multi-PHY stack validates as is.
const DEFAULT_INTERFACES=[{id:'long',acoustic:{frequency_hz:25000,bandwidth_hz:5000,bitrate_bps:4800}},{id:'short',acoustic:{frequency_hz:50000,bandwidth_hz:9000,bitrate_bps:8800}},{id:'third',acoustic:{frequency_hz:75000,bandwidth_hz:10000,bitrate_bps:9600}}];
// Per-interface fields of each medium; an empty field inherits that medium's global value.
const INTERFACE_FIELDS={acoustic:['frequency_hz','bandwidth_hz','bitrate_bps','tx_power_db'],optical:['frequency_hz','bandwidth_hz','bitrate_bps','tx_power_w']};
const interfaceMedium=item=>item?.medium||'acoustic';
// Defaults in the received-power unit of the interface the master leaves: linear acoustic power or W.
const thresholdDefault=(interfaces,from,to)=>{const ids=interfaces.map(i=>i.id),up=ids.indexOf(to)>ids.indexOf(from);return interfaceMedium(interfaces.find(i=>i.id===from))==='optical'?(up?1e-6:3e-8):(up?1e12:1e11)};
// The received-power master moves to the next interface on stronger power, so acoustic ones come first.
const opticalBeforeAcoustic=interfaces=>interfaces.some((item,k)=>interfaceMedium(item)==='optical'&&interfaces.slice(k+1).some(i=>interfaceMedium(i)==='acoustic'));
function interfaceMediumReason(config,k,value){
  const m=config.network.multiphy,ids=m.interfaces.map(i=>i.id),item=m.interfaces[k];
  if(m.policy==='received_power'&&opticalBeforeAcoustic(m.interfaces.map((i,j)=>j===k?{...i,medium:value}:i)))return 'with received-power selection the acoustic interfaces come before the optical ones';
  const [unit,label]=POWER_UNITS[value];
  if((config.power_events||[]).some(e=>(e.interface===item.id||(!e.interface&&k===0))&&e[unit]==null))return 'the power events of this interface must be in '+label+' (field '+unit+', editable in the JSON)';
  if(value!=='optical')return '';
  if(unverified('optical'))return unverified('optical');
  const holders=config.nodes.filter(node=>item.id===m.initial_interface||(node.communication?.interfaces||ids).includes(item.id));
  if(holders.some(node=>[node.position,...(node.waypoints||[]).map(w=>w.slice(1))].some(p=>!(p[2]>=-20&&p[2]<0))))return 'optical noise is tabulated only between 0 and 20 m depth';
  if(holders.some(node=>Object.values(node.communication?.interface_overrides?.[item.id]||{}).some(v=>v!=null)))return 'remove the per-drone acoustic overrides of this interface';
  return '';
}
function multiphyEditor(config){
  const n=config.network,m=n.multiphy,s=catalog.selectors||{},reason=m?'':multiphyReason(config),label=s.multiphy?.label||'Multiple interfaces (multi-PHY)';
  let html='<label class="check-field"><span>'+esc(label)+tip(helpText(s.multiphy||{label})+(reason?' Not available: '+reason+'.':''))+'</span><input type="checkbox" data-multiphy data-rerender aria-label="'+esc(label)+'"'+(m?' checked':'')+(reason?' disabled':'')+'></label>'+note(reason);
  if(!m)return html;
  const ids=m.interfaces.map(i=>i.id),optical=m.interfaces.some(i=>interfaceMedium(i)==='optical');
  // Catalogue control and global value behind each per-interface field.
  const source={acoustic:[mod('bpsk_upstream')?.parameters||[],'network.acoustic.',n.acoustic],optical:[mod('optical')?.parameters||[],'network.optical.',n.optical||{}]};
  const field=(medium,key)=>source[medium][0].find(p=>p.path===source[medium][1]+key)||{label:key};
  const inherited=(medium,key)=>{const p=field(medium,key);return format(source[medium][2][key])+(p.unit&&p.unit!=='dimensionless'?' '+p.unit:'')};
  const header=k=>{const [a,o]=['acoustic','optical'].map(md=>field(md,INTERFACE_FIELDS[md][k]));return '<th>'+esc(k===3?'Transmit power':a.label+unitLabel(a))+tip((optical?'Acoustic interfaces: ':'')+helpText(a)+' Empty field: inherits the global value ('+inherited('acoustic',INTERFACE_FIELDS.acoustic[k])+').'+(optical?' Optical interfaces: '+helpText(o)+' Empty field: inherits '+inherited('optical',INTERFACE_FIELDS.optical[k])+'.':''))+'</th>'};
  const cell=(item,k,key)=>{const md=interfaceMedium(item),p=field(md,key);return '<td><input type="number" step="any" min="'+(p.min??0)+'"'+(p.max!=null?' max="'+p.max+'"':'')+' data-mp-field="'+key+'" aria-label="'+esc(p.label+unitLabel(p)+' interface '+(k+1))+'" placeholder="'+esc(inherited(md,key))+'" value="'+esc(item[md]?.[key]??'')+'"></td>'};
  const phyCell=(item,k)=>interfaceMedium(item)==='optical'?'<td><span class="micro">'+esc(moduleName('phy','optical'))+'</span></td>':'<td><select data-mp-field="phy" aria-label="PHY interface '+(k+1)+'">'+choice('','Inherit',!item.acoustic?.phy)+catalog.modules.filter(x=>x.layer==='phy'&&x.operational&&![...MEDIA,'woss'].includes(x.id)).map(x=>choice(x.id,x.name,item.acoustic?.phy===x.id)).join('')+'</select></td>';
  const medium=s.multiphy_medium||{label:'Medium',choices:[{value:'acoustic',label:'Acoustic'},{value:'optical',label:'Optical'}]};
  const mediumCell=(item,k)=>'<td><select data-mp-medium data-rerender aria-label="'+esc(medium.label+' interface '+(k+1))+'">'+medium.choices.map(c=>choice(c.value,c.label,c.value===interfaceMedium(item),c.value===interfaceMedium(item)?'':interfaceMediumReason(config,k,c.value))).join('')+'</select></td>';
  html+='<div class="table-scroll network-routes"><table><thead><tr><th>'+esc(s.multiphy_interface?.label||'Interface')+tip(helpText(s.multiphy_interface||{label:'Interface'}))+'</th><th>'+esc(medium.label)+tip(helpText(medium))+'</th>'+[0,1,2,3].map(header).join('')+'<th>PHY</th><th></th></tr></thead><tbody>'+m.interfaces.map((item,k)=>'<tr data-mp-row><td><input data-mp-id data-previous="'+esc(item.id)+'" aria-label="Interface name '+(k+1)+'" value="'+esc(item.id)+'" pattern="[a-z][a-z0-9_]{0,15}" required data-rerender></td>'+mediumCell(item,k)+INTERFACE_FIELDS[interfaceMedium(item)].map(key=>cell(item,k,key)).join('')+phyCell(item,k)+'<td><button type="button" class="text-button danger" data-mp-remove="'+k+'"'+(ids.length<=2?' disabled title="At least two interfaces are needed"':'')+'>Remove</button></td></tr>').join('')+'</tbody></table></div><button type="button" class="subtle" data-mp-add'+(ids.length>=3?' disabled title="At most three interfaces"':'')+'>+ Interface</button>'+(ids.length>=3?note('at most three interfaces per drone'):'');
  if(optical)html+='<h3>Shared optical parameters'+tip('Global values inherited by every optical interface: transmitter and receiver optics, water attenuation, beam, mounting and noise. Each interface can override bandwidth, bitrate and power in the table.')+'</h3><div class="form-grid">'+(mod('optical')?.parameters||[]).map(p=>parameter(config,p)).join('')+'</div>';
  const policy=m.policy||'manual',automatic=policy==='received_power';
  html+='<div class="form-grid">'+selectorSelect(config,'multiphy_policy',(c,value)=>value==='received_power'&&opticalBeforeAcoustic(m.interfaces)?'optical interfaces must come after the acoustic ones':'')+parameter(config,{...(s.multiphy_initial||{label:'Initial interface',path:'network.multiphy.initial_interface'}),type:'select',choices:ids.map(id=>({value:id,label:id}))},{value:m.initial_interface})+(automatic?parameter(config,{...(s.multiphy_master||{label:'Master drone',path:'network.multiphy.master'}),type:'select',choices:config.nodes.map(node=>({value:node.id,label:drone(node.id)}))},{value:m.master})+parameter(config,s.multiphy_alpha||{label:'Alpha',path:'network.multiphy.alpha',type:'number',min:0,max:1}):'')+'</div>';
  if(automatic){
    const t=s.multiphy_threshold||{label:'Threshold'},pairs=ids.slice(1).flatMap((id,k)=>[[ids[k],id],[id,ids[k]]]);
    const unit=id=>interfaceMedium(m.interfaces.find(i=>i.id===id))==='optical'?'W':'linear acoustic (µPa²)';
    html+='<h3>'+esc(t.label)+tip(helpText(t))+'</h3><div class="table-scroll network-routes"><table><thead><tr><th>Switch</th><th>Condition</th><th>'+esc(t.label)+'</th><th>Unit</th></tr></thead><tbody>'+pairs.map(([from,to])=>{const value=(m.thresholds||[]).find(x=>x.from_interface===from&&x.to_interface===to)?.power_linear??thresholdDefault(m.interfaces,from,to);return '<tr data-threshold data-from="'+esc(from)+'" data-to="'+esc(to)+'"><td>'+esc(from+' → '+to)+'</td><td>'+(ids.indexOf(to)>ids.indexOf(from)?'Mean Pr above the threshold':'Mean Pr below the threshold')+'</td><td><input type="number" step="any" min="0" required aria-label="'+esc('Threshold '+from+' → '+to+' ['+unit(from)+']')+'" value="'+esc(value)+'"></td><td>'+esc(unit(from))+'</td></tr>'}).join('')+'</tbody></table></div>';
  }else{
    const a=s.multiphy_available||{label:'Interfaces available per drone'};
    html+='<h3>'+esc(a.label)+tip(helpText(a))+'</h3><div class="table-scroll network-routes"><table><thead><tr><th>Drone</th>'+ids.map(id=>'<th>'+esc(id)+'</th>').join('')+'</tr></thead><tbody>'+config.nodes.map(node=>{const own=node.communication?.interfaces||ids;return '<tr><td>'+esc(drone(node.id))+'</td>'+ids.map(id=>'<td><input type="checkbox" data-available data-node="'+esc(node.id)+'" data-interface="'+esc(id)+'" aria-label="'+esc(drone(node.id)+' · '+id)+'"'+(own.includes(id)||id===m.initial_interface?' checked':'')+(id===m.initial_interface?' disabled title="The initial interface is mandatory"':'')+'></td>').join('')+'</tr>'}).join('')+'</tbody></table></div>';
  }
  return html;
}
function readMultiphy(root,result){
  const box=root.querySelector('[data-multiphy]'),n=result.network;
  if(!box)return;
  if(!box.checked){n.multiphy=null;for(const node of result.nodes)if(node.communication){delete node.communication.interfaces;delete node.communication.interface_overrides}return}
  const rows=[...root.querySelectorAll('[data-mp-row]')],before=n.multiphy||{};
  if(!rows.length){n.multiphy={interfaces:structuredClone(DEFAULT_INTERFACES.slice(0,2)),policy:'manual',initial_interface:DEFAULT_INTERFACES[0].id,master:result.nodes[0]?.id||'auv_01',thresholds:[],alpha:.5};return}
  // The table edits a few fields; the others (spreading, noise, SNR penalty, ...) keep their configured values.
  // A new medium starts from its global values: the fields still shown belong to the previous medium.
  const renamed={},changed=new Set(),interfaces=rows.map(row=>{const name=row.querySelector('[data-mp-id]'),previous=structuredClone((before.interfaces||[]).find(i=>i.id===name.dataset.previous)||{}),shown=interfaceMedium(previous),medium=row.querySelector('[data-mp-medium]')?.value||shown,settings=medium===shown?{...previous[medium]}:{};renamed[name.dataset.previous]=name.value.trim();if(medium!==shown)changed.add(name.value.trim());if(medium===shown)row.querySelectorAll('[data-mp-field]').forEach(el=>settings[el.dataset.mpField]=el.value===''?null:el.type==='number'?Number(el.value):el.value);return {...previous,id:name.value.trim(),medium,acoustic:medium==='acoustic'?settings:{},optical:medium==='optical'?settings:{}}});
  const rename=id=>renamed[id]??id,ids=interfaces.map(i=>i.id),policy=before.policy||'manual',initial=rename(before.initial_interface);
  n.multiphy={...before,interfaces,policy,initial_interface:ids.includes(initial)?initial:ids[0],master:before.master||result.nodes[0]?.id,alpha:before.alpha??.5,
    // A threshold is in the unit of its from-interface: one whose medium changed returns to its default.
    thresholds:policy==='received_power'?[...root.querySelectorAll('[data-threshold]')].map(row=>({from_interface:rename(row.dataset.from),to_interface:rename(row.dataset.to),power_linear:Number(row.querySelector('input').value)})).filter(t=>ids.includes(t.from_interface)&&ids.includes(t.to_interface)&&!changed.has(t.from_interface)):[]};
  result.power_events=(result.power_events||[]).map(e=>e.interface?{...e,interface:rename(e.interface)}:e);
  if(n.multiphy.thresholds.some(t=>!(t.power_linear>0)))throw Error('Switching thresholds must be greater than zero.');
  for(const node of result.nodes){
    const boxes=[...root.querySelectorAll('[data-available]')].filter(b=>b.dataset.node===node.id),own=boxes.filter(b=>b.checked).map(b=>rename(b.dataset.interface)).filter(id=>ids.includes(id));
    const available=policy==='manual'&&boxes.length&&own.length<ids.length?ids.filter(id=>own.includes(id)):ids,c=node.communication;
    // Overrides follow a renamed interface and go with an interface the drone no longer has.
    if(c){delete c.interfaces;if(c.interface_overrides)c.interface_overrides=Object.fromEntries(Object.entries(c.interface_overrides).map(([k,v])=>[rename(k),v]).filter(([k])=>available.includes(k)))}
    if(available.length<ids.length)(node.communication??={}).interfaces=available;
  }
}
// Anchors of the position-based routing: static drones with an optional surveyed position.
function anchorsEditor(config){
  const s=selector('position_based_anchors')||{label:'Anchors'},anchors=config.network.position_based?.anchors||{};
  return '<h3>'+esc(s.label)+tip(helpText(s))+'</h3><div class="table-scroll network-routes"><table><thead><tr><th>Drone</th><th>Anchor</th><th>Surveyed position x [m]</th><th>y [m]</th><th>z [m]</th></tr></thead><tbody>'+config.nodes.map(node=>{const moving=(node.waypoints||[]).length>0,anchor=node.id in anchors&&!moving,survey=anchors[node.id]?.surveyed_position;return '<tr data-pbr-row data-node="'+esc(node.id)+'"><td>'+esc(drone(node.id))+'</td><td><input type="checkbox" data-pbr-anchor data-rerender aria-label="'+esc(drone(node.id)+' · anchor')+'"'+(anchor?' checked':'')+(moving?' disabled title="A drone with waypoints is a vehicle"':'')+'></td>'+[0,1,2].map(k=>'<td><input type="number" step="any" data-pbr-survey="'+k+'" aria-label="'+esc(drone(node.id)+' · surveyed position '+'xyz'[k]+' [m]')+'" placeholder="'+esc(format(node.position[k]))+'" value="'+esc(survey?.[k]??'')+'"'+(anchor?'':' disabled')+'></td>').join('')+'</tr>'}).join('')+'</tbody></table></div><p class="micro">Empty surveyed position: the scenario position is used. Unselected drones are vehicles and know only their own position.</p>';
}
function readAnchors(root,result){
  const n=result.network,rows=[...root.querySelectorAll('[data-pbr-row]')];
  if(n.routing!=='position_based')return;
  if(!rows.length){
    // First selection: drones without waypoints become anchors, keeping at least one vehicle.
    if(Object.keys(n.position_based?.anchors||{}).length)return;
    const fixed=result.nodes.filter(node=>!(node.waypoints||[]).length).map(node=>node.id);
    n.position_based={...(n.position_based||{}),anchors:Object.fromEntries((fixed.length===result.nodes.length?fixed.slice(0,-1):fixed).map(id=>[id,{}]))};
    return;
  }
  const anchors={};
  for(const row of rows){
    const box=row.querySelector('[data-pbr-anchor]');if(!box.checked||box.disabled)continue;
    const values=[...row.querySelectorAll('[data-pbr-survey]')].map(el=>el.value);
    if(values.some(v=>v!=='')&&values.some(v=>v===''))throw Error('Enter all three coordinates of the surveyed position, or none.');
    anchors[row.dataset.node]=values.every(v=>v!=='')?{surveyed_position:values.map(Number)}:{};
  }
  n.position_based={...(n.position_based||{}),anchors};
}
function addRoute(root,config,src,dst,hop){
  const row=document.createElement('tr');row.innerHTML='<td>'+nodeSelect(config.nodes,'source',src)+'</td><td>'+nodeSelect(config.nodes,'destination',dst)+'</td><td>'+nodeSelect(config.nodes,'hop',hop)+'</td><td><button type="button" class="text-button danger" aria-label="Remove route">Remove</button></td>';
  row.querySelector('button').onclick=()=>row.remove();root.querySelector('[data-routes]').append(row);
}
const FLOW_DEFAULTS={start:1,stop:null,interval:3,pattern:'periodic',generator:'python',burst_count:3,burst_interval_s:.25,burst_period_s:5,events:[],final_interval:null,payload_bytes:32,ttl:20,reply:false,message_type:'data'};
const nativeReason=flow=>!['periodic','poisson'].includes(flow.pattern)?'requires periodic or Poisson timing':flow.reply?'generates no replies':flow.final_interval!=null?'does not use the final interval':(flow.message_type||'data')!=='data'?'carries only data messages':'';
function drawFlow(row,config,flow){
  const native=(flow.generator||'python')!=='python',generator=selector('generator')||{label:'Generator',choices:[{value:'python',label:'Python (application)'}]};
  const numeric=(key,title,min,{optional=false,max=null,reason=''}={})=>'<label><span>'+title+tip((parameterHelp(key)||(key==='ttl'?'Maximum application validity time; it does not remove frames already queued.':key==='interval'?'Periodic interval, or mean interval of the Poisson generator, in seconds.':title))+(reason?' Not available: '+reason+'.':''))+'</span><input data-field="'+key+'" aria-label="'+title+'" type="number" step="'+(['payload_bytes','burst_count'].includes(key)?'1':'any')+'" min="'+min+'" '+(max?'max="'+max+'"':'')+' '+(optional?'':'required')+(reason?' disabled':'')+' value="'+(flow[key]??'')+'"></label>'+note(reason);
  const nativeField=p=>'<label><span>'+esc(p.label+unitLabel(p))+tip(helpText(p))+'</span><input data-field="'+esc(p.path)+'" aria-label="'+esc(p.label)+'" type="number" step="'+(p.type==='integer'?'1':'any')+'" '+(p.min!=null?'min="'+p.min+'" ':'')+(p.max!=null?'max="'+p.max+'" ':'')+'required value="'+esc(flow[p.path]??p.default)+'"></label>';
  const why=nativeReason(flow),patterns=[['periodic','Periodic'],['poisson','Poisson'],['burst','Burst'],['events','Explicit events']];
  const nativeParameters=native?(mod(flow.generator==='desert_vbr'?'native_vbr':'native_cbr')?.flow_parameters||[]):[];
  row.innerHTML='<header><h3>Message flow</h3><button type="button" class="text-button danger" data-remove>Remove</button></header><div class="form-grid"><label><span>Sender</span>'+nodeSelect(config.nodes,'source',flow.source)+'</label><label><span>Recipient</span>'+nodeSelect(config.nodes,'destination',flow.destination)+'</label>'
    +'<label><span>'+esc(generator.label)+tip(helpText(generator)+(!native&&why?' Native generators not available: '+why+'.':''))+'</span><select data-field="generator" aria-label="'+esc(generator.label)+'" data-redraw>'+generator.choices.map(c=>{const id=c.value==='desert_vbr'?'native_vbr':'native_cbr';return choice(c.value,c.label,c.value===(flow.generator||'python'),c.value==='python'||c.value===flow.generator?'':unverified(id)||stackReason(config,id)||(!native?why:''))}).join('')+'</select></label>'
    +'<label><span>Traffic pattern'+tip((parameterHelp('pattern')||'')+(native?' Native generators use only periodic or Poisson timing.':''))+'</span><select data-field="pattern" aria-label="Traffic pattern" data-redraw>'+patterns.map(([v,l])=>choice(v,l,flow.pattern===v,native&&!['periodic','poisson'].includes(v)?'not with native generators':'')).join('')+'</select></label>'
    +(['events','burst'].includes(flow.pattern)?'':numeric('interval','Interval [s]',.001))+(native?'':numeric('payload_bytes','Payload [byte]',1,{max:2048}))+'</div>'
    +'<div class="form-grid traffic-pattern">'+(flow.pattern==='burst'?numeric('burst_count','Messages per burst',1)+numeric('burst_interval_s','Interval within the burst [s]',.001)+numeric('burst_period_s','Burst period [s]',.001):flow.pattern==='events'?'<label class="wide"><span>Events · absolute simulated times [s]'+tip('Increasing list of seconds from the start of the simulation, separated by commas.')+'</span><input data-field="events" aria-label="Events · absolute simulated times [s]" value="'+esc((flow.events||[]).join(', '))+'"></label>':'')+nativeParameters.map(nativeField).join('')+'</div>'
    +(native?'<p class="network-note">Native DESERT timers and packets: no JSON envelope, no Python TTL and no application reply.</p>':'')
    +'<details><summary>Timing, validity and reply</summary><div class="form-grid">'+numeric('start','Start [s]',0)+numeric('stop','Stop [s] · optional',.001,{optional:true})+(['periodic','poisson'].includes(flow.pattern)?numeric('final_interval','Final interval [s] · optional',.001,{optional:true,reason:native?'not with native generators':''}):'')+numeric('ttl','TTL [s]',.001,{reason:native?'the Python TTL does not apply to native packets':''})+'<label><span>Message type</span><input data-field="message_type" value="'+esc(flow.message_type)+'" required data-redraw'+(native?' disabled':'')+'></label><label class="check-field"><span>Request a reply</span><input type="checkbox" data-field="reply" data-redraw '+(flow.reply?'checked':'')+(native?' disabled':'')+'></label></div></details>';
  const opened=row.dataset.details==='open';if(opened)row.querySelector('details').open=true;row.querySelector('details').ontoggle=e=>row.dataset.details=e.target.open?'open':'';
  row.querySelectorAll('[data-redraw]').forEach(el=>el.onchange=()=>{const next={...flow,...readFlow(row)};if((next.generator||'python')!=='python')Object.assign(next,{reply:false,final_interval:null,message_type:'data',pattern:['periodic','poisson'].includes(next.pattern)?next.pattern:'periodic'});drawFlow(row,config,next)});
  row.querySelector('[data-remove]').onclick=()=>row.remove();addHelp(row);
}
export function renderFlows(root,config){
  root.innerHTML='<div data-flows></div><button type="button" class="subtle" data-add-flow>+ Add flow</button>';
  if(config.coordination){root.innerHTML='<p class="network-note">This scenario uses the two-drone heartbeat application. Ordinary flows do not apply; the existing behaviour is preserved.</p>';return}
  const add=(f={})=>{const row=document.createElement('section');row.className='flow-card';root.querySelector('[data-flows]').append(row);drawFlow(row,config,{source:config.nodes[0]?.id,destination:config.nodes[1]?.id,...FLOW_DEFAULTS,...f})};
  config.flows.forEach(add);root.querySelector('[data-add-flow]').onclick=()=>add();
}
function readFlow(row){return Object.fromEntries([...row.querySelectorAll('[data-field]')].map(el=>[el.dataset.field,el.dataset.field==='events'?el.value.split(',').filter(x=>x.trim()).map(x=>{const n=Number(x);if(!Number.isFinite(n))throw Error('Event times must be numbers.');return n}):el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value]))}
export function readFlows(root){return [...root.querySelectorAll('.flow-card')].map(readFlow)}
export function renderNetwork(root,config,{includeFlows=true,mode=null}={}){
  rendered.set(root,config);
  const opened=new Set([...root.querySelectorAll('details[open]>summary')].map(el=>el.textContent));
  const mac=config.network.mac.protocol,phy=config.network.acoustic.phy||'bpsk_upstream',routing=config.network.routing||'static',medium=mediumOf(config),acoustic=medium==='acoustic';
  const primary=(acoustic?catalog.modules.find(m=>m.layer.toLowerCase()==='phy'&&m.id===phy)?.parameters||[]:mod(medium)?.parameters||[]).filter(p=>PRIMARY[medium].includes(p.path));
  root.innerHTML='<div class="designer-heading"><h3>Network Designer</h3><button type="button" class="subtle" data-catalog>Module catalogue</button></div><div class="form-grid">'+selectorSelect(config,'medium',mediumReason)+moduleSelect(config,'mac','network.mac.protocol','MAC protocol')+(acoustic?moduleSelect(config,'phy','network.acoustic.phy','Physical model'):'')+moduleSelect(config,'routing','network.routing','Routing')+'</div><div class="form-grid">'+primary.map(p=>parameter(config,p)).join('')+'</div>'+(catalog.modules.find(m=>m.id===mac)?.compatibility_reason?'<p class="network-note">'+esc(catalog.modules.find(m=>m.id===mac).compatibility_reason)+'</p>':'')+(acoustic?'':'<p class="network-note">'+esc(mediumLabel(medium))+' technology: the native PHY is '+esc(moduleName('phy',medium))+'; MAC, routing and acoustic overrides remain limited to the verified combinations.</p>')+'<details class="advanced-settings"><summary>Advanced settings</summary>'
    +'<details class="advanced-settings" open><summary>'+(acoustic?'Acoustic propagation and environment':esc(mediumLabel(medium))+' technology parameters')+'</summary>'+mediumSection(config)+'</details>'
    +'<details class="advanced-settings" open><summary>'+(acoustic?'Acoustic channel and medium access':'Medium access')+'</summary><div class="form-grid">'+(acoustic?selectedParameters(config,'phy',phy):'')+selectedParameters(config,'mac',mac)+'</div>'+(mac==='tdma'||mac==='tdma_frame'?'<h3>Slot per drone</h3><p class="micro">Index of the slot in the DESERT frame, starting from zero.</p><div class="form-grid">'+config.nodes.map((n,i)=>parameter(config,{path:'network.mac.tdma.slot_assignment.'+n.id,label:drone(n.id)+' · slot',type:'integer',min:0,max:config.nodes.length-1,help:'Slot assigned to this interface in the shared frame.',constraint:'unique slots, one per drone',default:i})).join('')+'</div>':'')+'</details>'
    +(acoustic?'<details class="advanced-settings"'+(config.network.multiphy?' open':'')+'><summary>Multiple interfaces (multi-PHY)</summary>'+multiphyEditor(config)+'</details>':'')
    +'<details class="advanced-settings" open><summary>Routing and relays</summary><div class="form-grid">'+selectedParameters(config,'routing',routing)+'</div>'+(routing==='position_based'?anchorsEditor(config):'')+'<div data-static-routes '+(!['static','position_based'].includes(routing)?'hidden':'')+'><p class="network-note">'+(routing==='position_based'?'Anchor tables: an anchor sends directly to the vehicle when its estimate is within range, otherwise to the listed next hop; without an entry, to the destination itself. The next hop is an anchor or the destination.':'Without an explicit route the next hop is the destination itself.')+' A configured route does not guarantee that the signal arrives.</p><div class="table-scroll network-routes"><table><thead><tr><th>From drone</th><th>To destination</th><th>Via</th><th></th></tr></thead><tbody data-routes></tbody></table></div><button class="subtle" type="button" data-add-route>+ Add route</button></div></details>'
    +'<details class="advanced-settings"><summary>Per-drone acoustic overrides</summary>'+(acoustic?'<p class="micro">Empty fields inherit the global channel. The sound speed stays shared. An override changes only the interface of the given drone'+(config.network.multiphy?' and applies to all its acoustic interfaces, before the values of each interface':'')+'.</p>'+config.nodes.map((n,i)=>'<details><summary>'+esc(drone(n.id))+'</summary><div class="form-grid">'+parameter(config,{path:'nodes.'+i+'.communication.acoustic.phy',label:'Drone PHY',help:'Independent PHY class; empty inherits the global profile.',constraint:propagationOf(config)==='woss'?'with WOSS only the original BPSK PHY is allowed':'',choices:[{value:'',label:'Inherit global profile'},...catalog.modules.filter(m=>m.layer==='phy'&&m.operational&&![...MEDIA,'woss'].includes(m.id)).map(m=>({value:m.id,label:moduleName('phy',m.id)}))]},{value:n.communication?.acoustic?.phy||''})+(catalog.modules.find(m=>m.layer.toLowerCase()==='phy'&&m.id===phy)?.parameters||[]).filter(p=>p.path.startsWith('network.acoustic.')&&!['network.acoustic.phy','network.acoustic.sound_speed_mps'].includes(p.path)&&!p.choices).map(p=>parameter(config,{...p,help:p.help+' Empty field: inherits the global value.'},{path:'nodes.'+i+'.communication.acoustic.'+p.path.split('.').at(-1),optional:true,value:n.communication?.acoustic?.[p.path.split('.').at(-1)]??''})).join('')+'</div></details>').join(''):'<p class="unavailable-note">Not available: per-drone acoustic overrides do not apply to the '+esc(mediumLabel(medium).toLowerCase())+' technology.</p>')+'</details>'
    +(includeFlows?'<details class="advanced-settings"><summary>Application flows</summary><div data-flow-editor></div></details>':'')+(mode!==null?'<details class="advanced-settings"><summary>Experiment engines</summary><label class="field"><span>Execution mode'+tip('Integrated: HoloOcean moves the drones with physics and DESERT simulates the network on the measured poses. DESERT only: fixed configured positions, no motion or waypoints. Default: integrated.')+'</span><select data-mode aria-label="Execution mode"><option value="integrated">HoloOcean and DESERT · full simulation</option><option value="standalone">DESERT only · fixed configured positions</option></select></label><p class="network-note">DESERT-only mode does not simulate motion and is not available for Moving drones and Drone coordination.</p></details>':'')+'</details>';
  for(const [src,routes]of Object.entries(config.network.routes||{}))for(const [dst,hop]of Object.entries(routes))addRoute(root,config,src,dst,hop);
  root.querySelector('[data-add-route]').onclick=()=>addRoute(root,config,config.nodes[0]?.id,config.nodes[1]?.id,config.nodes[1]?.id);
  const error=document.createElement('p');error.className='inline-error';error.setAttribute('role','alert');root.append(error);
  const redraw=change=>{try{const next=readNetwork(root,config,{includeFlows});change?.(next);renderNetwork(root,next,{includeFlows,mode:root.querySelector('[data-mode]')?.value??mode})}catch(e){error.textContent=e.message}};
  root.querySelectorAll('[data-module],[data-rerender],[data-path="network.mac.queue_mode"],[data-path="network.mac.ack"],[data-path="network.multiphy.initial_interface"]').forEach(el=>el.onchange=()=>redraw());
  // A new SSP sample goes midway before the seabed sample, so the profile stays valid.
  root.querySelector('[data-add-ssp]')?.addEventListener('click',()=>redraw(next=>{const ssp=next.network.woss.ssp,[a,b]=ssp.slice(-2);if(a&&b)ssp.splice(ssp.length-1,0,{depth_m:(a.depth_m+b.depth_m)/2,speed_mps:(a.speed_mps+b.speed_mps)/2})}));
  root.querySelectorAll('[data-remove-ssp]').forEach((b,k)=>b.onclick=()=>redraw(next=>next.network.woss.ssp.splice(k,1)));
  root.querySelector('[data-mp-add]')?.addEventListener('click',()=>redraw(next=>{const used=new Set(next.network.multiphy.interfaces.map(i=>i.id));next.network.multiphy.interfaces.push(structuredClone(DEFAULT_INTERFACES.find(i=>!used.has(i.id))||{id:'extra',acoustic:{}}))}));
  root.querySelectorAll('[data-mp-remove]').forEach(b=>b.onclick=()=>redraw(next=>{const m=next.network.multiphy,[gone]=m.interfaces.splice(Number(b.dataset.mpRemove),1);if(m.initial_interface===gone.id)m.initial_interface=m.interfaces[0].id;m.thresholds=m.thresholds.filter(t=>t.from_interface!==gone.id&&t.to_interface!==gone.id);next.power_events=(next.power_events||[]).filter(e=>e.interface!==gone.id);for(const node of next.nodes)if(node.communication?.interfaces)node.communication.interfaces=node.communication.interfaces.filter(id=>id!==gone.id)}));
  root.querySelector('[data-catalog]').onclick=()=>{let dialog=document.querySelector('#network-catalog-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='network-catalog-dialog';dialog.className='settings-dialog';document.body.append(dialog)}dialog.innerHTML='<div class="dialog-heading"><h2>DESERT catalogue</h2><button type="button" class="icon-button" aria-label="Close catalogue">×</button></div>'+catalog.modules.map(m=>'<article class="catalog-module"><h3>'+esc(m.name)+' <small>'+esc(m.layer)+'</small></h3><p>'+esc(m.description)+'</p><p><strong>'+esc(m.experimental&&m.operational?'Verified experimental':m.operational?'Operational · verified':'Not available in the Designer')+'</strong> '+esc(m.reason||(typeof m.validation==='string'?m.validation:JSON.stringify(m.validation||{})))+'</p><details><summary>Verification details</summary><pre>'+esc(JSON.stringify({tcl_class:m.tcl_class,libraries:m.libraries,source_present:m.source_present,compiled:m.compiled,loadable:m.loadable,official_example:m.official_example,bridge_compatible:m.bridge_compatible,validation:m.validation},null,2))+'</pre></details></article>').join('')+'<details><summary>Environment inventory</summary><pre>'+esc(JSON.stringify(catalog.inventory||{},null,2))+'</pre></details>';dialog.querySelector('button').onclick=()=>dialog.close();dialog.showModal()};
  if(includeFlows)renderFlows(root.querySelector('[data-flow-editor]'),config);
  if(mode!==null)root.querySelector('[data-mode]').value=mode;root.querySelectorAll('details').forEach(el=>{if(opened.has(el.querySelector('summary')?.textContent))el.open=true});addHelp(root);
}
export function readNetwork(root,config,{includeFlows=true}={}){
  const result=structuredClone({...(rendered.get(root)??config),nodes:config.nodes});
  root.querySelectorAll('[data-path]').forEach(el=>set(result,el.dataset.path,el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?undefined:Number(el.value)):(el.value===''?undefined:el.value)));
  // Only MACs that implement the ALOHA-style ACK show its control; the others run without it.
  if(!(mod(result.network.mac.protocol)?.parameters||[]).some(p=>p.path==='network.mac.ack'))result.network.mac.ack=false;
  const points=root.querySelector('[data-ssp-points]');
  if(points)result.network.woss.ssp=[...points.querySelectorAll('[data-ssp-row]')].map(row=>{const read=key=>row.querySelector('[data-ssp="'+key+'"]').value;if(read('depth_m')===''||read('speed_mps')==='')throw Error('Enter the depth and speed of every SSP point.');return {depth_m:Number(read('depth_m')),speed_mps:Number(read('speed_mps'))}});
  readMultiphy(root,result);
  readAnchors(root,result);
  const routes={};for(const row of root.querySelector('[data-routes]').children){const read=k=>row.querySelector('[data-field="'+k+'"]').value,src=read('source'),dst=read('destination');routes[src]??={};if(dst in routes[src])throw Error('The route '+src+' → '+dst+' is duplicated.');routes[src][dst]=read('hop')}result.network.routes=routes;
  if(includeFlows&&!config.coordination)result.flows=readFlows(root.querySelector('[data-flow-editor]'));
  return result;
}
export function bindConfiguration(getConfig,onSave,getMode=()=> 'integrated'){
  let draft;
  const populate=value=>{draft=structuredClone(value);renderNetwork($('#network-form'),draft,{mode:getMode()});$('#config-editor').value=JSON.stringify(draft,null,2)};
  $('#configure').onclick=()=>{const c=getConfig();if(!c)return;populate(c);$('#config-error').textContent='';$('#config-dialog').showModal()};
  $('#network-profiles-open').onclick=()=>openProfiles(()=>readNetwork($('#network-form'),draft).network,async network=>{const current=readNetwork($('#network-form'),draft);populate(await api('/api/validate',{...current,network}))}).catch(failure);
  $('#close-config').onclick=()=>$('#config-dialog').close();
  const failure=e=>$('#config-error').textContent=e.message;
  $('#form-to-json').onclick=()=>{try{$('#config-editor').value=JSON.stringify(readNetwork($('#network-form'),draft),null,2)}catch(e){failure(e)}};
  $('#json-to-form').onclick=async()=>{try{populate(await api('/api/validate',JSON.parse($('#config-editor').value)));$('#config-error').textContent=''}catch(e){failure(e)}};
  $('#config-form').onsubmit=async e=>{e.preventDefault();try{const configuration=await api('/api/validate',readNetwork($('#network-form'),draft));onSave(configuration,$('#network-form [data-mode]').value);$('#config-dialog').close()}catch(e){failure(e)}};
}
