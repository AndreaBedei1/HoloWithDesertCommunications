import {esc} from './ui.js';
// Network controls use the capability catalog; these describe host inputs.
const descriptions={
name:'Name in the library; it does not change the network behaviour.',
description:'Purpose of this experiment or profile, stored in the configuration.',
world:'Installed HoloOcean environment. The visual geometry does not define the DESERT acoustic model.',
duration:'Simulated time in seconds. At the end, packets that are still valid may remain pending.',
physics_hz:'Physics steps and barriers per second. Default 30 Hz; range 1-240.',
realtime:'Follows wall-clock time. When disabled the run is faster and keeps the same logical barriers.',
id:'Unique address auv_NN. Renaming updates flows, routes and slots.',
vehicle:'HoloOcean physical vehicle with sensors and controller; HoveringAUV is verified.',
x:'Initial X position in metres; afterwards the poses measured by the sensors are used.',
y:'Initial Y position in metres; the sensors then measure the actual motion.',
z:'Initial height in metres, negative below the surface. Depth = -Z.',
yaw:'Orientation around a vertical axis, in degrees.',
source:'Drone that generates the message, or origin of the route.',
destination:'Unicast recipient. Flooding uses native broadcasts towards this final address.',
hop:'Next drone on the static route; it does not guarantee that the signal arrives.',
message_type:'Application label; request generates a reply on reception. No implicit MAC priority.',
reply:'Application request and reply, distinct from MAC ACKs.',
pattern:'Timing pattern of the messages: periodic, Poisson, burst or explicit instants. DESERT handles access, channel, routing and delivery.',
interval:'Periodic interval or mean of the exponential Poisson interval, in seconds; default 3.',
start:'First absolute generation time, in simulated seconds; default 1.',
stop:'Exclusive generation limit in seconds. Empty: until the end of the run.',
final_interval:'Interval reached by linear interpolation between start and stop; requires a stop time.',
payload_bytes:'Application bytes, default 32. The JSON/base64 envelope and headers increase the transmitted bits.',
ttl:'Validity from generation, in seconds; default 20. It does not remove frames queued in the MAC.',
burst_count:'Messages per burst, default 3; allowed range 1-100.',
burst_interval_s:'Seconds between messages of a burst, default 0.25. The burst must end before the next period.',
burst_period_s:'Seconds between the starts of consecutive bursts; default 5.',
events:'Absolute times in seconds, increasing and unique, within the flow window.',
profile:'Reusable network: keeps motion and traffic; references to drones are validated.',
network:'Typed network in JSON; unknown fields and unsupported modules are rejected.'
};
export const parameterHelp=key=>descriptions[key];
export function addParameterHelp(root){
root.querySelectorAll('input,select,textarea').forEach(control=>{
if(['file','hidden'].includes(control.type))return;
const key=control.dataset.general||control.dataset.node||control.dataset.field||['name','description','network','profile'].find(k=>control.hasAttribute('data-'+k));
let text=descriptions[key];
if(control.closest('[data-waypoint]'))text='HoloOcean target: increasing absolute time in seconds, then X/Y/Z in metres. The controller moves the vehicle through the physics.';
if(!text)return;
const label=control.closest('label'),host=label?.querySelector(':scope > span')||label||control.parentElement;
if(host.querySelector('[data-help]'))return;
host.insertAdjacentHTML('beforeend','<button type="button" class="help" data-help="'+esc(text)+'" aria-label="Explain parameter">?</button>');
});
}
