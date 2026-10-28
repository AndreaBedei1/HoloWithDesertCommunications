import {canvas} from './ui.js';

// Round axis step (1, 2 or 5 times a power of ten) giving about `count` intervals over `span`.
function niceStep(span,count){const raw=span/Math.max(1,count),power=10**Math.floor(Math.log10(raw)),unit=raw/power;return (unit<=1?1:unit<=2?2:unit<=5?5:10)*power}
const label=v=>(Math.abs(v)<1e-9?0:v).toLocaleString('en-US',{maximumFractionDigits:3});

// Null is a gap, including unknown MAC counters. No invented zero samples.
export function chart(selector, series, lines, {window=0, max=null, dual=false, step=false}={}) {
  const {ctx,w,h}=canvas(selector), left=58,right=dual?48:15,top=24,bottom=32;
  const end=series.at(-1)?.time||1, start=window?Math.max(series[0]?.time||0,end-window):(series[0]?.time||0);
  const data=series.filter(p=>p.time>=start), x=t=>left+(t-start)/Math.max(.01,end-start)*(w-left-right);
  const values=data.flatMap(p=>lines.filter(l=>!l.right).map(l=>l.value(p))).filter(Number.isFinite);
  const divisions=Math.max(1,Math.min(4,Math.floor((h-top-bottom)/26)));
  let lo=Math.min(0,...values), hi=max??Math.max(0.01,...values); if(hi===lo)hi=lo+1;
  // The axis ends on a round tick instead of the raw extreme of the data.
  const yStep=niceStep(hi-lo,divisions);
  if(max==null){hi=Math.ceil(hi/yStep-1e-9)*yStep;lo=Math.floor(lo/yStep+1e-9)*yStep}
  const y=(v,rightAxis=false)=>h-bottom-(rightAxis?v:(v-lo)/(hi-lo))*(h-top-bottom);
  ctx.font='11px "Segoe UI",sans-serif';ctx.fillStyle='#748096';ctx.textAlign='left';
  for(let i=0,v=lo;v<=hi+yStep*1e-6;v=lo+(++i)*yStep){
    const py=y(v);ctx.strokeStyle='#edf0f5';ctx.beginPath();ctx.moveTo(left,py);ctx.lineTo(w-right,py);ctx.stroke();
    ctx.fillStyle='#748096';ctx.fillText(label(v),2,py+3);
  }
  if(dual)for(let f=0;f<=1;f+=.25)ctx.fillText(label(f),w-right+7,y(f,true)+3);
  const xStep=niceStep(Math.max(.01,end-start),4);
  ctx.textAlign='center';
  for(let i=0,t=Math.ceil(start/xStep-1e-9)*xStep;t<=end+xStep*1e-6;t=Math.ceil(start/xStep-1e-9)*xStep+(++i)*xStep)ctx.fillText(label(t),x(t),h-14);
  ctx.fillText('simulated time [s]',left+(w-left-right)/2,h-1);ctx.textAlign='left';
  for(const line of lines){ctx.strokeStyle=line.color;ctx.lineWidth=2;ctx.beginPath();let previous=null;
    for(const p of data){const value=line.value(p);if(!Number.isFinite(value)){previous=null;continue}
      const px=x(p.time),py=y(value,line.right);if(previous){if(step)ctx.lineTo(px,previous[1]);ctx.lineTo(px,py)}else ctx.moveTo(px,py);previous=[px,py];
    }ctx.stroke();
  }
  if(!values.length){ctx.fillStyle='#9fb0bf';ctx.fillText('No data available',left+12,top+14)}
}

// One row per drone, one mark per observed transmission, coloured by the interface used.
export function strips(selector, rows, marks, colors, {start=0,end=1}={}) {
  const {ctx,w,h}=canvas(selector), left=86,right=15,top=12,bottom=32,row=(h-top-bottom)/Math.max(1,rows.length);
  const x=t=>left+(t-start)/Math.max(.01,end-start)*(w-left-right);
  ctx.font='11px "Segoe UI",sans-serif';ctx.textAlign='left';
  rows.forEach((r,i)=>{const cy=top+row*(i+.5);ctx.strokeStyle='#edf0f5';ctx.beginPath();ctx.moveTo(left,cy);ctx.lineTo(w-right,cy);ctx.stroke();ctx.fillStyle='#53647d';ctx.fillText(r.label,2,cy+4)});
  for(const m of marks){const i=rows.findIndex(r=>r.id===m.row);if(i<0)continue;ctx.fillStyle=colors[m.key]||'#8795a8';ctx.beginPath();ctx.arc(x(m.time),top+row*(i+.5),4,0,2*Math.PI);ctx.fill()}
  const xStep=niceStep(Math.max(.01,end-start),4);ctx.fillStyle='#748096';ctx.textAlign='center';
  for(let i=0,t=Math.ceil(start/xStep-1e-9)*xStep;t<=end+xStep*1e-6;t=Math.ceil(start/xStep-1e-9)*xStep+(++i)*xStep)ctx.fillText(label(t),x(t),h-14);
  ctx.fillText('simulated time [s]',left+(w-left-right)/2,h-1);ctx.textAlign='left';
  if(!marks.length){ctx.fillStyle='#9fb0bf';ctx.fillText('No transmissions observed',left+12,top+14)}
}
