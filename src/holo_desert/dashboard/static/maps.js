import {$,canvas} from './ui.js';

const cameras=new Map();
export function resetMaps(){cameras.clear()}
function arrow(ctx,a,b,color,dash=[],offset=0){
  const angle=Math.atan2(b[1]-a[1],b[0]-a[0]), nx=-Math.sin(angle)*offset,ny=Math.cos(angle)*offset;
  const start=[a[0]+nx+14*Math.cos(angle),a[1]+ny+14*Math.sin(angle)],end=[b[0]+nx-18*Math.cos(angle),b[1]+ny-18*Math.sin(angle)];
  if(Math.hypot(b[0]-a[0],b[1]-a[1])<38)return;
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(...start);ctx.lineTo(...end);ctx.stroke();ctx.setLineDash([]);
  ctx.beginPath();ctx.moveTo(...end);ctx.lineTo(end[0]-9*Math.cos(angle-.4),end[1]-9*Math.sin(angle-.4));ctx.lineTo(end[0]-9*Math.cos(angle+.4),end[1]-9*Math.sin(angle+.4));ctx.fill();
}
export function drawMap(selector,s,selected,network=false){
  const {ctx,w,h}=canvas(selector),fleet=Object.entries(s.fleet||{});
  if(!fleet.length){ctx.fillStyle='#9fb0bf';ctx.font='13px system-ui';ctx.fillText('Attesa delle osservazioni del simulatore',20,h/2);return}
  let camera=cameras.get(selector);
  if(!camera){camera={auto:true,zoom:1,hits:[]};cameras.set(selector,camera)}
  if(camera.auto){const xs=fleet.map(([,p])=>p.x),ys=fleet.map(([,p])=>p.y);
    camera.x=(Math.min(...xs)+Math.max(...xs))/2;camera.y=(Math.min(...ys)+Math.max(...ys))/2;
    camera.scale=Math.min((w-120)/Math.max(40,Math.max(...xs)-Math.min(...xs)),(h-100)/Math.max(40,Math.max(...ys)-Math.min(...ys)));
  }
  const scale=camera.scale*camera.zoom, xy=p=>[w/2+(p.x-camera.x)*scale,h/2-(p.y-camera.y)*scale];
  const raw=70/scale,base=10**Math.floor(Math.log10(raw)),grid=[1,2,5,10].map(v=>v*base).find(v=>v>=raw);
  ctx.strokeStyle='#243746';ctx.fillStyle='#9fb0bf';ctx.font='10px monospace';ctx.lineWidth=.7;
  const minX=camera.x-w/2/scale,maxX=camera.x+w/2/scale,minY=camera.y-h/2/scale,maxY=camera.y+h/2/scale;
  for(let x=Math.ceil(minX/grid)*grid;x<maxX;x+=grid){const [px]=xy({x,y:0});ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,h);ctx.stroke();ctx.fillText(x.toFixed(1),px+3,h-22)}
  for(let y=Math.ceil(minY/grid)*grid;y<maxY;y+=grid){const [,py]=xy({x:0,y});ctx.beginPath();ctx.moveTo(0,py);ctx.lineTo(w,py);ctx.stroke();ctx.fillText(y.toFixed(1),3,py-4)}
  ctx.fillText('X →   Y ↑   '+grid.toPrecision(2)+' m / griglia',12,h-7);
  const line=(a,b,color,dash=[],offset=0)=>{if(s.fleet[a]&&s.fleet[b])arrow(ctx,xy(s.fleet[a]),xy(s.fleet[b]),color,dash,offset)};
  if(network){
    if($('#route-layer').checked){const relevant=new Set(),routes=s.configured_routes||[];
      for(const r of routes)if(r.explicit)relevant.add(r.source+'>'+r.destination);
      for(const f of s.configuration?.flows||[]) {let current=f.source;const visited=new Set();while(current!==f.destination&&!visited.has(current)){visited.add(current);const r=routes.find(r=>r.source===current&&r.destination===f.destination);if(!r)break;relevant.add(current+'>'+f.destination);current=r.next_hop}}
      for(const r of routes)if(relevant.has(r.source+'>'+r.destination))line(r.source,r.next_hop,'#8494aa',[5,5],-8);
    }
    const observed=new Map();
    for(const e of s.observations||[]){if(e.event==='forward')observed.set('forward'+e.node_id+'>'+e.next_hop_id,e);if(e.event==='phy_tx_start')observed.set('tx'+e.node_id+'>'+e.next_hop_id,e);if(e.event==='phy_rx_end'&&e.outcome==='decoded')observed.set('rx'+e.transmitter_id+'>'+e.node_id,e)}
    for(const e of observed.values()){const recent=s.time-e.time<=1;if(e.event==='forward')line(e.node_id,e.next_hop_id,recent?'#cda5ff':'#644e80',[],0);
      else if($('#phy-layer').checked)line(e.event==='phy_rx_end'?e.transmitter_id:e.node_id,e.event==='phy_rx_end'?e.node_id:e.next_hop_id,recent?(e.event==='phy_tx_start'?'#f5be6d':'#69adff'):'#344d60',[],7);
    }
    if($('#delivery-layer').checked)for(const e of s.edges||[])line(e.source,e.destination,s.time-e.last_receive<=1?'#54d8ba':'#315f55',[10,3],18);
  }else if($('#trails').checked){for(const points of Object.values(s.trails||{})){ctx.strokeStyle='#54d8ba80';ctx.lineWidth=1.5;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(...xy({x,y})):ctx.moveTo(...xy({x,y})));ctx.stroke()}}
  camera.hits=[];
  for(const [node,p] of fleet){const [x,y]=xy(p);camera.hits.push({node,x,y});
    if(network&&$('#phy-layer').checked){const events=(s.observations||[]).filter(e=>e.node_id===node&&s.time>=e.time&&s.time-e.time<=1&&e.event.startsWith('phy_'));const last=events.at(-1);
      if(last){ctx.strokeStyle=last.event==='phy_tx_start'?'#f5be6d':last.outcome==='decoded'?'#69adff':'#ff7e88';ctx.lineWidth=3;ctx.beginPath();ctx.arc(x,y,21,0,2*Math.PI);ctx.stroke()}}
    ctx.save();ctx.translate(x,y);ctx.rotate(-p.yaw*Math.PI/180);ctx.fillStyle=node===selected?'#fff':'#54d8ba';ctx.beginPath();ctx.moveTo(12,0);ctx.lineTo(-8,-7);ctx.lineTo(-5,0);ctx.lineTo(-8,7);ctx.closePath();ctx.fill();ctx.restore();
    ctx.fillStyle='#e6edf2';ctx.font='11px monospace';ctx.fillText(node,x+15,y-9);
  }
}
export function bindMap(selector,fitButton,onSelect,render){
  const c=$(selector);let drag=null,moved=false;
  $(fitButton).onclick=()=>{cameras.delete(selector);render()};
  c.onwheel=e=>{e.preventDefault();const cam=cameras.get(selector);if(!cam)return;cam.auto=false;cam.zoom=Math.max(.1,Math.min(30,cam.zoom*Math.exp(-e.deltaY*.001)));render()};
  c.onpointerdown=e=>{const cam=cameras.get(selector);if(!cam)return;drag={x:e.clientX,y:e.clientY,cx:cam.x,cy:cam.y};moved=false;c.setPointerCapture(e.pointerId)};
  c.onpointermove=e=>{if(!drag)return;const cam=cameras.get(selector),dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>4)moved=true;if(!moved)return;cam.auto=false;cam.x=drag.cx-dx/(cam.scale*cam.zoom);cam.y=drag.cy+dy/(cam.scale*cam.zoom);render()};
  c.onpointerup=e=>{if(!drag)return;drag=null;if(!moved){const r=c.getBoundingClientRect(),hit=cameras.get(selector)?.hits.find(p=>Math.hypot(p.x-e.clientX+r.left,p.y-e.clientY+r.top)<23);if(hit)onSelect(hit.node)}render()};
  c.onpointercancel=()=>{drag=null};
}
