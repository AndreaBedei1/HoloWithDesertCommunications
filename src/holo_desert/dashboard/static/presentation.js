import {esc,number} from './ui.js';

export const SCENARIOS = {
  e01_chat: {code:'E01', title:'Scambio di messaggi', description:'Due droni fermi si scambiano una richiesta e una risposta.', observe:'Segui il viaggio di un messaggio, dalla generazione alla consegna.', diagram:['A','→ ←','B']},
  e02_multi_node: {code:'E02', title:'Comunicazione tra più droni', description:'Quattro droni condividono lo stesso canale acustico e inviano messaggi contemporaneamente.', observe:'Osserva quali messaggi arrivano quando più droni usano il canale.', diagram:['A','B','C','D']},
  e03_mobility: {code:'E03', title:'Droni in movimento', description:'Due droni si allontanano e poi tornano vicini, continuando a scambiarsi messaggi.', observe:'Confronta la distanza misurata con la percentuale di consegna.', diagram:['A','← →','B']},
  e04_congestion: {code:'E04', title:'Congestione della rete', description:'Tre droni inviano messaggi sempre più spesso verso un quarto drone.', observe:'Osserva messaggi in attesa, code e interferenza. Puoi confrontare i due MAC.', diagram:['A · B · C','→','D']},
  e05_multihop: {code:'E05', title:'Comunicazione tramite relay', description:'Il messaggio raggiunge C passando per B, che lo inoltra. Nelle condizioni configurate il collegamento diretto non consegna.', observe:'Segui le due tratte A → B e B → C e la consegna finale.', diagram:['A','→','B','→','C']},
  e06_coordination: {code:'E06', title:'Coordinamento tra droni', description:'Un drone procede quando riceve heartbeat recenti dal leader e attende quando la comunicazione si interrompe.', observe:'Segui lo stato del follower durante l’interruzione e il ripristino della comunicazione.', diagram:['Leader','→','Follower']},
};
export const HELP = {
  PDR:'Percentuale di messaggi consegnati tra quelli già ricevuti o scaduti. I messaggi ancora in attesa sono esclusi.',
  MAC:'Regola usata dai droni per accedere al canale condiviso. Il Designer mostra i moduli verificati nel catalogo DESERT.',
  Latenza:'Tempo simulato dalla generazione alla consegna di un messaggio. La media include solo i messaggi consegnati.',
  Relay:'Drone intermedio che inoltra un messaggio verso la destinazione finale attraverso lo stack di rete.',
  Interferenza:'Il contatore registra esiti del ramo PHY interferenza. Nel modello BPSK originale il secondo test può fallire anche senza interferenza. Leggi potenze, patch ed esito dell’evento; un timeout non dimostra una collisione.',
  Scadenza:'Il messaggio non è stato consegnato entro il proprio TTL. La causa è ignota; non significa necessariamente collisione o perdita fisica.',
  Goodput:'Bit di payload applicativo consegnati per secondo nell’intervallo campionato.',
  Throughput:'Bit dell’envelope applicativo consegnato al secondo, inclusi JSON e base64. Esclude header PHY/MAC, ACK e ritrasmissioni.',
  PHY:'Livello fisico del canale (acustico, ottico o elettromagnetico). Una ricezione PHY non conferma da sola la consegna all’applicazione.',
  'Multi-PHY':'Ogni drone ha più interfacce (acustiche o ottiche) sotto lo stesso MAC; il controller nativo DESERT sceglie quella attiva, a mano tramite l’API o in base alla potenza ricevuta. Il grafico mostra l’interfaccia di ogni trasmissione osservata.',
  TTL:'Tempo massimo di validità applicativa del messaggio. Non cancella un pacchetto già nella coda del MAC.',
  Ranging:'Stima nativa DESERT: tempo di volo misurato dal MAC di ranging moltiplicato per la velocità del suono configurata. La distanza geometrica HoloOcean è un riferimento esterno che il protocollo non conosce; la differenza mostra l’errore della stima.',
};
export const help = term => '<button type="button" class="help" data-help="'+esc(term)+'" aria-label="Spiega '+esc(term)+'">?</button>';
export const drone = id => id ? 'Drone '+id.replace(/^auv_/, '') : '—';
export const typeName = type => ({data:'Dati',binary:'Dati binari',json:'Dati JSON',request:'Richiesta',reply:'Risposta',heartbeat:'Heartbeat'}[type]||type);
export function interferenceLabel(e){
  const patch=e.phy_patch_id||'',zero=e.positive_interference===false||e.pi===0,positive=e.positive_interference===true||e.pi>0;
  if(zero&&/upstream/.test(patch))return 'Secondo test PHY fallito (interferenza nulla)';
  if(!zero&&positive&&/conditional|corrected/.test(patch))return 'Errore di interferenza';
  return 'Errore nel ramo PHY interferenza (causa non misurata)';
}
// Multi-PHY interface names of the configuration on screen (events carry 1-based indices).
let interfaceNames=[];
export function setInterfaceNames(configuration){interfaceNames=(configuration?.network?.multiphy?.interfaces||[]).map(i=>i.id)}
export const interfaceLabel=index=>(interfaceNames[index-1]||'interfaccia')+' · '+index;
export const powerLabel=e=>e.tx_power_db!=null?number(e.tx_power_db,1)+' dB re 1 µPa':e.tx_power_dbm!=null?number(e.tx_power_dbm,1)+' dBm':e.tx_power_w!=null?Number(e.tx_power_w).toExponential(3)+' W':null;
const signal=e=>({optical:'ottico',em:'EM'}[e.medium]||'acustico'),transmission=e=>({optical:'ottica',em:'EM'}[e.medium]||'acustica');
export const eventLabel = e => ({late_receive:'Ricevuto dopo il TTL (non consegnato)',duplicate:'Duplicato applicativo ignorato',generated:'Messaggio generato',app_tx:'Inserito nella rete',forward:'Inoltro di rete',phy_tx_start:'Trasmissione '+transmission(e)+' iniziata',phy_tx_end:'Trasmissione '+transmission(e)+' terminata',phy_rx_start:'Segnale '+signal(e)+' osservato',phy_rx_end:e.outcome==='decoded'?'Segnale '+signal(e)+' decodificato':e.outcome==='interference_error'?interferenceLabel(e):e.outcome==='noise_error'?'Errore dovuto al rumore':e.outcome==='not_synchronized'?'Ricezione non sincronizzata':'Fine ricezione (esito non esposto dal PHY)',rx:'Ricezione nello stack applicativo',delivered:'Consegnato all’applicazione',ttl_expired:'Tempo di validità scaduto',application_state:'Stato del drone',power_applied:'Potenza applicata'}[e.event.replace('phy_control_','phy_')]||e.event)+(e.event.startsWith('phy_control_')?' (controllo MAC)':'');
export function eventTone(e) {
  if(e.event==='delivered')return 'success';
  if(e.event==='ttl_expired')return 'warning';
  if(e.event==='phy_rx_end'&&['noise_error','interference_error','not_synchronized'].includes(e.outcome))return 'error';
  if(e.event==='phy_tx_start'||e.event==='forward')return 'info';
  return 'neutral';
}
export function scenarioInfo(id,configuration) {
  return SCENARIOS[id] || {code:'Personale',title:configuration?.name||'Scenario personale',description:configuration?.description||'Il tuo esperimento di comunicazione.',observe:'Osserva movimento, trasmissioni e consegne nella mappa.',diagram:[]};
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
