import {esc} from './ui.js';
// Network controls use the capability catalog; these describe host inputs.
const descriptions={
name:'Nome nella libreria; non cambia il comportamento della rete.',
description:'Scopo di questo esperimento o profilo, conservato nella configurazione.',
world:'Ambiente HoloOcean installato. La geometria visiva non definisce il modello acustico DESERT.',
duration:'Tempo simulato in secondi. Alla fine i pacchetti ancora validi possono restare pendenti.',
physics_hz:'Passi fisici e barriere al secondo. Default 30 Hz; intervallo 1-240.',
realtime:'Segue il tempo reale. Disattivato accelera conservando le stesse barriere logiche.',
id:'Indirizzo unico auv_NN. La rinomina aggiorna flussi, route e slot.',
vehicle:'Veicolo fisico HoloOcean con sensori e controller; HoveringAUV verificato.',
x:'Posizione iniziale X in metri; poi si usano le pose misurate dai sensori.',
y:'Posizione iniziale Y in metri; i sensori misurano poi il movimento reale.',
z:'Quota iniziale in metri, negativa sotto la superficie. Profondita = -Z.',
yaw:'Orientamento attorno a un asse verticale, in gradi.',
source:'Drone che genera il messaggio oppure origine della route.',
destination:'Destinatario unicast. Flooding usa broadcast nativi sotto questo indirizzo finale.',
hop:'Prossimo drone nella route statica; non garantisce che il segnale arrivi.',
message_type:'Etichetta applicativa; request genera una risposta alla ricezione. Nessuna priorita MAC implicita.',
reply:'Richiesta e risposta applicativa, distinte da ACK del MAC.',
pattern:'Generatore Python; DESERT gestisce accesso, canale, routing e consegna.',
interval:'Intervallo periodico o medio esponenziale Poisson, in secondi; default 3.',
start:'Primo tempo assoluto di generazione, in secondi simulati; default 1.',
stop:'Limite escluso di generazione in secondi. Vuoto: fino alla fine della corsa.',
final_interval:'Intervallo raggiunto con interpolazione lineare fra inizio e fine; richiede un tempo di fine.',
payload_bytes:'Byte applicativi, default 32. Envelope JSON/base64 e header aumentano i bit trasmessi.',
ttl:'Validita dalla generazione, in secondi; default 20. Non cancella frame accodati nel MAC.',
burst_count:'Messaggi per raffica, default 3; intervallo consentito 1-100.',
burst_interval_s:'Secondi fra messaggi della raffica, default 0,25. Deve finire prima del periodo successivo.',
burst_period_s:'Secondi fra gli inizi delle raffiche; default 5.',
events:'Tempi assoluti in secondi, crescenti e unici, entro la finestra del flusso.',
profile:'Rete riutilizzabile: conserva movimento e traffico; i riferimenti ai droni vengono validati.',
network:'Rete tipizzata in JSON; campi sconosciuti e moduli non supportati sono rifiutati.'
};
export const parameterHelp=key=>descriptions[key];
export function addParameterHelp(root){
root.querySelectorAll('input,select,textarea').forEach(control=>{
if(['file','hidden'].includes(control.type))return;
const key=control.dataset.general||control.dataset.node||control.dataset.field||['name','description','network','profile'].find(k=>control.hasAttribute('data-'+k));
let text=descriptions[key];
if(control.closest('[data-waypoint]'))text='Target HoloOcean: tempo assoluto crescente in secondi, poi X/Y/Z in metri. Il controller muove il veicolo attraverso la fisica.';
if(!text)return;
const label=control.closest('label'),host=label?.querySelector(':scope > span')||label||control.parentElement;
if(host.querySelector('[data-help]'))return;
host.insertAdjacentHTML('beforeend','<button type="button" class="help" data-help="'+esc(text)+'" aria-label="Spiega parametro">?</button>');
});
}
