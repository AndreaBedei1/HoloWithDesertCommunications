import {$,canvas,number} from './ui.js';
import {drone} from './presentation.js';
import {messageHops,HOP_STATUS} from './packets.js';
import {transmissionsAt,transmissionLabel,transmissionTone} from './replay.js';

const HOP_COLORS={success:'#237454',error:'#b44343',info:'#3165cf',neutral:'#8795a8'};

const cameras=new Map();
export function resetMaps(){cameras.clear()}
function arrow(ctx,a,b,color,{dash=[],offset=0,label='',width=1.7}={}){
  const angle=Math.atan2(b[1]-a[1],b[0]-a[0]),normal=[-Math.sin(angle),Math.cos(angle)];
  const start=[a[0]+18*Math.cos(angle),a[1]+18*Math.sin(angle)],end=[b[0]-20*Math.cos(angle),b[1]-20*Math.sin(angle)];
  if(Math.hypot(b[0]-a[0],b[1]-a[1])<45)return;
  const control=[(a[0]+b[0])/2+normal[0]*offset,(a[1]+b[1])/2+normal[1]*offset];
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(...start);ctx.quadraticCurveTo(...control,...end);ctx.stroke();ctx.setLineDash([]);
  const tangent=Math.atan2(end[1]-control[1],end[0]-control[0]);
  ctx.beginPath();ctx.moveTo(...end);ctx.lineTo(end[0]-7*Math.cos(tangent-.4),end[1]-7*Math.sin(tangent-.4));ctx.lineTo(end[0]-7*Math.cos(tangent+.4),end[1]-7*Math.sin(tangent+.4));ctx.fill();
  if(label){ctx.font='12px "Segoe UI",sans-serif';const x=(a[0]+b[0])/2+normal[0]*offset/2,y=(a[1]+b[1])/2+normal[1]*offset/2+(offset>40?20:-8);ctx.textAlign='center';ctx.fillStyle='#fff';ctx.fillRect(x-ctx.measureText(label).width/2-5,y-10,ctx.measureText(label).width+10,14);ctx.fillStyle=color;ctx.fillText(label,x,y);ctx.textAlign='left'}
}
export function drawMap(selector,s,selected,packetId=null){
  const {ctx,w,h}=canvas(selector),fleet=Object.entries(s.fleet||{});
  if(!fleet.length)return;
  let camera=cameras.get(selector);if(!camera){camera={auto:true,zoom:1,hits:[]};cameras.set(selector,camera)}
  if(camera.auto){const xs=fleet.map(([,p])=>p.x),ys=fleet.map(([,p])=>p.y);camera.x=(Math.min(...xs)+Math.max(...xs))/2;camera.y=(Math.min(...ys)+Math.max(...ys))/2;camera.scale=Math.max(.000001,Math.min((w-150)/Math.max(20,Math.max(...xs)-Math.min(...xs)),(h-110)/Math.max(20,Math.max(...ys)-Math.min(...ys))))}
  const scale=camera.scale*camera.zoom,xy=p=>[w/2+(p.x-camera.x)*scale,h/2-(p.y-camera.y)*scale];
  const raw=80/scale,base=10**Math.floor(Math.log10(raw)),grid=[1,2,5,10].map(v=>v*base).find(v=>v>=raw);
  ctx.strokeStyle='#eff2f7';ctx.fillStyle='#94a0b0';ctx.font='12px "Segoe UI",sans-serif';ctx.lineWidth=1;
  const minX=camera.x-w/2/scale,maxX=camera.x+w/2/scale,minY=camera.y-h/2/scale,maxY=camera.y+h/2/scale;
  for(let x=Math.ceil(minX/grid)*grid;x<maxX;x+=grid){const [px]=xy({x,y:0});ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,h-20);ctx.stroke();ctx.fillText(number(x,0),px+4,h-7)}
  for(let y=Math.ceil(minY/grid)*grid;y<maxY;y+=grid){const [,py]=xy({x:0,y});ctx.beginPath();ctx.moveTo(0,py);ctx.lineTo(w,py);ctx.stroke();ctx.fillText(number(y,0),4,py-4)}
  const bar=Math.min(w/4,grid*scale);ctx.strokeStyle='#8594aa';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(w-bar-14,h-32);ctx.lineTo(w-14,h-32);ctx.stroke();ctx.fillStyle='#748399';ctx.fillText(number(bar/scale,grid<1?2:0)+' m',w-bar-14,h-38);ctx.fillText('Y ↑  X →',12,h-30);
  if($('#trails').checked)for(const points of Object.values(s.trails||{})){ctx.strokeStyle='#b9cce9';ctx.lineWidth=2;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(...xy({x,y})):ctx.moveTo(...xy({x,y})));ctx.stroke()}
  const link=(a,b,color,options)=>{if(s.fleet[a]&&s.fleet[b])arrow(ctx,xy(s.fleet[a]),xy(s.fleet[b]),color,options)};
  if($('#route-layer').checked){const routes=s.configured_routes||[],relevant=new Set();for(const r of routes)if(r.explicit)relevant.add(r.source+'>'+r.destination);
    for(const f of s.configuration?.flows||[]){let n=f.source;const visited=new Set();while(n!==f.destination&&!visited.has(n)){visited.add(n);const r=routes.find(r=>r.source===n&&r.destination===f.destination);if(!r)break;relevant.add(n+'>'+f.destination);n=r.next_hop}}
    for(const r of routes)if(relevant.has(r.source+'>'+r.destination))link(r.source,r.next_hop,'#9aa5b5',{dash:[4,5],offset:-25,label:'Configured route',width:1});
  }
  const packet=(s.packets||[]).find(p=>p.id===packetId),events=packet?packet.events:(s.observations||[]);
  // Selected message: its addressed hops in order, coloured by the outcome recorded at each next hop.
  if(packet&&$('#phy-layer').checked)messageHops(packet).forEach((h,i)=>{const [,tone,kind]=HOP_STATUS[h.status];link(h.from,h.to,HOP_COLORS[tone],{offset:-14,dash:kind==='inferred'||h.status==='routed'?[5,4]:[],label:'Hop '+(i+1)+' · '+{decoded:'decoded',reached:'reached (inferred)',error:'PHY error',sent:'no reception recorded',routed:'routed only'}[h.status],width:2.4})});
  // Frames on the air at the drawn time: arrow transmitter → receiver, dot = elapsed share of the recorded TX → RX interval.
  if(!packet&&$('#phy-layer').checked)for(const x of transmissionsAt(s,s.time))if(x.to&&s.fleet[x.from]&&s.fleet[x.to]){
    const color=HOP_COLORS[transmissionTone(x)],a=xy(s.fleet[x.from]),b=xy(s.fleet[x.to]);
    arrow(ctx,a,b,color,{label:transmissionLabel(x),width:2.4,dash:x.observedEnd?[]:[5,4]});
    const d=Math.hypot(b[0]-a[0],b[1]-a[1]);if(d<45)continue;
    const ux=(b[0]-a[0])/d,uy=(b[1]-a[1])/d,f=18+(d-38)*x.frac;
    ctx.fillStyle=color;ctx.beginPath();ctx.arc(a[0]+ux*f,a[1]+uy*f,5,0,Math.PI*2);ctx.fill();
  }
  const delivered=packet?(packet.status==='received'?[{source:packet.source,destination:packet.destination,last_receive:packet.receive_time}]:[]):s.edges||[];
  const newest=Math.max(...delivered.map(e=>e.last_receive));
  if($('#delivery-layer').checked)for(const e of delivered)link(e.source,e.destination,e.last_receive===newest?'#438264':'#a0b7ab',{offset:85,dash:[6,4],label:packet||e.last_receive===newest?'Delivery · absolute t = '+number(e.last_receive,2)+' s':'',width:1.5});
  camera.hits=[];
  for(const [node,p]of fleet){const [x,y]=xy(p);camera.hits.push({node,x,y});
    const recent=events.filter(e=>e.node_id===node&&s.time>=e.time&&s.time-e.time<1.2&&['phy_tx_start','phy_rx_end'].includes(e.event)).at(-1);
    if(recent&&$('#phy-layer').checked){ctx.strokeStyle=recent.event==='phy_tx_start'?'#3165cf':recent.outcome==='decoded'?'#8eabc9':'#c57272';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,22,0,Math.PI*2);ctx.stroke()}
    ctx.fillStyle=node===selected?'#eaf1ff':'#f6f8fc';ctx.strokeStyle=node===selected?'#3165cf':'#c0ccde';ctx.lineWidth=node===selected?1.7:1;ctx.beginPath();ctx.arc(x,y,16,0,Math.PI*2);ctx.fill();ctx.stroke();
    ctx.save();ctx.translate(x,y);ctx.rotate(-p.yaw*Math.PI/180);ctx.fillStyle=node===selected?'#3165cf':'#647c9f';ctx.beginPath();ctx.moveTo(9,0);ctx.lineTo(-6,-5);ctx.lineTo(-3,0);ctx.lineTo(-6,5);ctx.closePath();ctx.fill();ctx.restore();
    let label=drone(node);if(s.configuration?.name==='e05_multihop')label=String.fromCharCode(65+fleet.findIndex(([n])=>n===node))+' · '+label;
    ctx.font='13px "Segoe UI",sans-serif';ctx.textAlign='center';const tw=ctx.measureText(label).width;ctx.fillStyle='#ffffffed';ctx.fillRect(x-tw/2-4,y+22,tw+8,18);ctx.fillStyle='#435570';ctx.fillText(label,x,y+35);ctx.textAlign='left';
  }
}
export function bindMap(selector,fitButton,onSelect,render){
  const c=$(selector);let drag=null,moved=false;
  $(fitButton).onclick=()=>{cameras.delete(selector);render()};
  c.addEventListener('wheel',e=>{e.preventDefault();const cam=cameras.get(selector);if(!cam)return;cam.auto=false;cam.zoom=Math.max(.1,Math.min(30,cam.zoom*Math.exp(-e.deltaY*.001)));render()},{passive:false});
  c.onpointerdown=e=>{const cam=cameras.get(selector);if(!cam)return;drag={x:e.clientX,y:e.clientY,cx:cam.x,cy:cam.y};moved=false;c.setPointerCapture(e.pointerId)};
  c.onpointermove=e=>{if(!drag)return;const cam=cameras.get(selector),dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>4)moved=true;if(!moved)return;cam.auto=false;cam.x=drag.cx-dx/(cam.scale*cam.zoom);cam.y=drag.cy+dy/(cam.scale*cam.zoom);render()};
  c.onpointerup=e=>{if(!drag)return;drag=null;if(!moved){const r=c.getBoundingClientRect(),hit=cameras.get(selector)?.hits.find(p=>Math.hypot(p.x-e.clientX+r.left,p.y-e.clientY+r.top)<25);if(hit)onSelect(hit.node)}render()};
  c.onpointercancel=()=>{drag=null};
}
