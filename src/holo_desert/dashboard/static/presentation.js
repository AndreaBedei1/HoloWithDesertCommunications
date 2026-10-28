import {esc,number} from './ui.js';

export const SCENARIOS = {
  e01_chat: {code:'E01', title:'Message exchange', description:'Two stationary drones exchange a request and a reply.', observe:'Follow a message from generation to delivery.', diagram:['A','→ ←','B']},
  e02_multi_node: {code:'E02', title:'Multi-drone communication', description:'Four drones share the same acoustic channel and send messages at the same time.', observe:'See which messages arrive when several drones use the channel.', diagram:['A','B','C','D']},
  e03_mobility: {code:'E03', title:'Moving drones', description:'Two drones move apart and then close in again while they keep exchanging messages.', observe:'Compare the measured distance with the delivery ratio.', diagram:['A','← →','B']},
  e04_congestion: {code:'E04', title:'Network congestion', description:'Three drones send messages to a fourth drone at an increasing rate.', observe:'Watch pending messages, queues and interference. You can compare the two MACs.', diagram:['A · B · C','→','D']},
  e05_multihop: {code:'E05', title:'Relay communication', description:'The message reaches C through B, which forwards it. Under the configured conditions the direct link does not deliver.', observe:'Follow the two hops A → B and B → C and the final delivery.', diagram:['A','→','B','→','C']},
  e06_coordination: {code:'E06', title:'Drone coordination', description:'A drone proceeds while it receives recent heartbeats from the leader and holds when communication is interrupted.', observe:'Follow the follower state while communication is lost and restored.', diagram:['Leader','→','Follower']},
  e07_ranging_tokenbus: {code:'E07', title:'Native ranging with TokenBus', description:'Three stationary drones share the native DESERT Ranging-TokenBus MAC. Data travels on the token ring while the MAC measures one-way travel times and estimates distances (travel time × sound speed).', observe:'In Analysis → Ranging, compare the native DESERT estimates with the HoloOcean geometric distance, which the protocol does not know.', diagram:['A','B','C']},
  e08_woss: {code:'E08', title:'Bellhop propagation (WOSS)', description:'Native Bellhop propagation with a synthetic non-uniform sound speed profile. The receiver changes range and depth over a flat seabed.', observe:'Inspect the native received power and the arrival delay as the receiver moves.', diagram:['A','→','B']},
  e09_sun_convergecast: {code:'E09', title:'SUN convergecast to a sink', description:'Four stationary drones use native SUN dynamic routing towards the sink D. Probes select relays B or C instead of the 800 m direct link; routes can change during the run.', observe:'Follow the relays SUN discovers for each message. Some late messages are still pending when the run ends.', diagram:['A · C','→','B / C','→','Sink D']},
};
export const HELP = {
  PDR:'Share of delivered messages among those already received or expired. Messages still pending are excluded.',
  MAC:'Rule the drones use to access the shared channel. The Designer shows the verified modules of the DESERT catalogue.',
  Latenza:'Simulated time from the generation to the delivery of a message. The mean includes delivered messages only.',
  Relay:'Intermediate drone that forwards a message towards its final destination through the network stack.',
  Interferenza:'This counter records outcomes of the PHY interference branch. In the original BPSK model the second test can fail even without interference. Read the powers, the patch and the event outcome; a timeout does not prove a collision.',
  Scadenza:'The message was not delivered within its TTL. The cause is unknown; it does not necessarily mean a collision or a physical loss.',
  Goodput:'Application payload bits delivered per second in the sampled interval.',
  Throughput:'Bits of the delivered application envelope per second, including JSON and base64. Excludes PHY/MAC headers, ACKs and retransmissions.',
  PHY:'Physical layer of the channel (acoustic, optical or electromagnetic). A PHY reception alone does not confirm delivery to the application.',
  'Multi-PHY':'Each drone has several interfaces (acoustic or optical) under the same MAC; the native DESERT controller selects the active one, manually through the API or from the received power. The chart shows the interface of every observed transmission.',
  TTL:'Maximum application validity time of the message. It does not remove a packet already in the MAC queue.',
  Evidence:'Observed: read directly from recorded events (both endpoints for a duration). Inferred: derived by matching events, for example a transmission and a decoded reception with the same transmitter; retransmissions can make the match ambiguous. Configured: taken from the scenario, not measured. Nothing here attributes a collision or a cause of loss.',
  Ranging:'Native DESERT estimate: time of flight measured by the ranging MAC multiplied by the configured sound speed. The HoloOcean geometric distance is an external reference the protocol does not know; the difference shows the estimation error.',
};
// HELP keys are stable data-help identifiers; these give the readable term for screen readers.
const TERMS={Latenza:'latency',Interferenza:'interference',Scadenza:'expiry'};
export const help = term => '<button type="button" class="help" data-help="'+esc(term)+'" aria-label="Explain '+esc(TERMS[term]||term)+'">?</button>';
export const drone = id => id ? 'Drone '+id.replace(/^auv_/, '') : '—';
export const typeName = type => ({data:'Data',binary:'Binary data',json:'JSON data',request:'Request',reply:'Reply',heartbeat:'Heartbeat',desert_cbr:'Native CBR',desert_vbr:'Native VBR'}[type]||type);
export function interferenceLabel(e){
  const patch=e.phy_patch_id||'',zero=e.positive_interference===false||e.pi===0,positive=e.positive_interference===true||e.pi>0;
  if(zero&&/upstream/.test(patch))return 'Second PHY test failed (zero interference)';
  if(!zero&&positive&&/conditional|corrected/.test(patch))return 'Interference error';
  return 'Error in the PHY interference branch (cause not measured)';
}
// Multi-PHY interface names of the configuration on screen (events carry 1-based indices).
let interfaceNames=[];
export function setInterfaceNames(configuration){interfaceNames=(configuration?.network?.multiphy?.interfaces||[]).map(i=>i.id)}
export const interfaceLabel=index=>(interfaceNames[index-1]||'interface')+' · '+index;
export const powerLabel=e=>e.tx_power_db!=null?number(e.tx_power_db,1)+' dB re 1 µPa':e.tx_power_dbm!=null?number(e.tx_power_dbm,1)+' dBm':e.tx_power_w!=null?Number(e.tx_power_w).toExponential(3)+' W':null;
const signal=e=>({optical:'Optical',em:'EM'}[e.medium]||'Acoustic'),transmission=e=>({optical:'Optical',em:'EM'}[e.medium]||'Acoustic');
export const eventLabel = e => ({late_receive:'Received after the TTL (not delivered)',duplicate:'Application duplicate ignored',generated:'Message generated',app_tx:'Injected into the network',forward:'Network forwarding',phy_tx_start:transmission(e)+' transmission started',phy_tx_end:transmission(e)+' transmission ended',phy_rx_start:signal(e)+' signal observed',phy_rx_end:e.outcome==='decoded'?signal(e)+' signal decoded':e.outcome==='interference_error'?(e.medium==='optical'?'Interference error (non-zero interfering power)':interferenceLabel(e)):e.outcome==='noise_error'?'Error due to noise':e.outcome==='not_synchronized'?'Reception not synchronised':'End of reception (outcome not exposed by the PHY)',rx:'Received by the application stack',delivered:'Delivered to the application',ttl_expired:'Validity time expired',application_state:'Drone state',power_applied:'Power applied'}[e.event.replace('phy_control_','phy_')]||e.event)+(e.event.startsWith('phy_control_')?' (MAC control)':'');
export function eventTone(e) {
  if(e.event==='delivered')return 'success';
  if(e.event==='ttl_expired')return 'warning';
  if(e.event==='phy_rx_end'&&['noise_error','interference_error','not_synchronized'].includes(e.outcome))return 'error';
  if(e.event==='phy_tx_start'||e.event==='forward')return 'info';
  return 'neutral';
}
export function scenarioInfo(id,configuration) {
  return SCENARIOS[id] || {code:'Custom',title:configuration?.name||'Custom scenario',description:configuration?.description||'Your communication experiment.',observe:'Watch motion, transmissions and deliveries on the map.',diagram:[]};
}
export function bindHelp() {
  const box=document.querySelector('#tooltip');let pinned=false;
  const show=target=>{(target.closest('dialog')||document.body).append(box);box.textContent=HELP[target.dataset.help]||target.dataset.help;box.hidden=false;const r=target.getBoundingClientRect();box.style.left=Math.max(12,Math.min(innerWidth-300,r.left-120))+'px';box.style.top=Math.min(innerHeight-box.offsetHeight-12,r.bottom+8)+'px';target.setAttribute('aria-describedby','tooltip')};
  document.addEventListener('pointerover',e=>{const target=e.target.closest('[data-help]');if(target&&!pinned)show(target)});
  document.addEventListener('pointerout',e=>{if(e.target.closest('[data-help]')&&!pinned)box.hidden=true});
  document.addEventListener('focusin',e=>{if(e.target.matches('[data-help]'))show(e.target)});
  document.addEventListener('focusout',()=>{if(!pinned)box.hidden=true});
  document.addEventListener('click',e=>{const target=e.target.closest('[data-help]');if(target){pinned=!pinned;if(pinned)show(target);else box.hidden=true}else{pinned=false;box.hidden=true}});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!box.hidden)e.preventDefault();pinned=false;box.hidden=true}});
}
