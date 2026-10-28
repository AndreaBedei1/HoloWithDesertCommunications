import {canvas,number} from './ui.js';
import {drone} from './presentation.js';

export function createEditorMap(selector,fitButton,{getScenario,getSelected,onSelect,onMove}){
  const c=document.querySelector(selector);let camera=null,hits=[],drag=null;
  function draw(){
    const config=getScenario();if(!config)return;
    const {ctx,w,h}=canvas(selector),points=config.nodes.flatMap(n=>[n.position,...n.waypoints.map(v=>v.slice(1))]);
    if(!points.length)return;
    if(!camera){const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);camera={x:(Math.min(...xs)+Math.max(...xs))/2,y:(Math.min(...ys)+Math.max(...ys))/2,scale:Math.max(.0001,Math.min((w-100)/Math.max(60,Math.max(...xs)-Math.min(...xs)),(h-90)/Math.max(60,Math.max(...ys)-Math.min(...ys))))}}
    const xy=p=>[w/2+(p[0]-camera.x)*camera.scale,h/2-(p[1]-camera.y)*camera.scale];
    ctx.fillStyle='#fbfcfe';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#edf1f7';ctx.lineWidth=1;
    for(let x=0;x<w;x+=35){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}for(let y=0;y<h;y+=35){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}
    for(const flow of config.flows){const a=config.nodes.find(n=>n.id===flow.source),b=config.nodes.find(n=>n.id===flow.destination);if(!a||!b)continue;const [x,y]=xy(a.position),[tx,ty]=xy(b.position),angle=Math.atan2(ty-y,tx-x);ctx.strokeStyle='#b4c7e6';ctx.fillStyle='#92acd3';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(tx,ty);ctx.stroke();ctx.beginPath();ctx.moveTo(tx-16*Math.cos(angle),ty-16*Math.sin(angle));ctx.lineTo(tx-24*Math.cos(angle-.4),ty-24*Math.sin(angle-.4));ctx.lineTo(tx-24*Math.cos(angle+.4),ty-24*Math.sin(angle+.4));ctx.fill()}
    config.nodes.forEach(n=>{if(!n.waypoints.length)return;ctx.strokeStyle='#9caec8';ctx.setLineDash([4,5]);ctx.lineWidth=1.4;ctx.beginPath();ctx.moveTo(...xy(n.position));for(const wp of n.waypoints)ctx.lineTo(...xy(wp.slice(1)));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#8597b1';ctx.font='10px "Segoe UI",sans-serif';for(const wp of n.waypoints){const [x,y]=xy(wp.slice(1));ctx.fillRect(x-2,y-2,4,4);ctx.fillText(number(wp[0],0)+' s',x+5,y-4)}});
    hits=[];config.nodes.forEach((n,index)=>{const [x,y]=xy(n.position),selected=index===getSelected();hits.push({index,x,y});ctx.beginPath();ctx.arc(x,y,13,0,Math.PI*2);ctx.fillStyle=selected?'#e9f1ff':'#fff';ctx.strokeStyle=selected?'#3165cf':'#a8b9d1';ctx.lineWidth=1.5;ctx.fill();ctx.stroke();ctx.save();ctx.translate(x,y);ctx.rotate(-n.yaw*Math.PI/180);ctx.beginPath();ctx.moveTo(7,0);ctx.lineTo(-4,-4);ctx.lineTo(-2,0);ctx.lineTo(-4,4);ctx.fillStyle=selected?'#3165cf':'#778eaf';ctx.fill();ctx.restore();ctx.font='11px "Segoe UI",sans-serif';ctx.fillStyle='#526782';ctx.textAlign='center';ctx.fillText(drone(n.id),x,y+29);ctx.textAlign='left'});
    ctx.fillStyle='#8393aa';ctx.font='10px "Segoe UI",sans-serif';ctx.fillText('Y ↑   X →    '+number(35/camera.scale,1)+' m / grid cell',12,h-12);
  }
  const fit=()=>{camera=null;draw()};document.querySelector(fitButton).onclick=fit;
  c.onpointerdown=e=>{const r=c.getBoundingClientRect(),hit=hits.find(p=>Math.hypot(p.x-e.clientX+r.left,p.y-e.clientY+r.top)<23);if(!hit||onSelect(hit.index)===false)return;drag=hit.index;c.setPointerCapture(e.pointerId)};
  c.onpointermove=e=>{if(drag===null||!camera)return;const r=c.getBoundingClientRect();onMove(drag,[Math.round((camera.x+(e.clientX-r.left-r.width/2)/camera.scale)*10)/10,Math.round((camera.y-(e.clientY-r.top-r.height/2)/camera.scale)*10)/10]);draw()};
  c.onpointerup=c.onpointercancel=()=>{drag=null};
  return {draw,fit};
}
