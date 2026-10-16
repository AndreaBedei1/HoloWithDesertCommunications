import {canvas} from './ui.js';

// Null is a gap, including unknown MAC counters. No invented zero samples.
export function chart(selector, series, lines, {window=0, max=null, dual=false, step=false}={}) {
  const {ctx,w,h}=canvas(selector), left=58,right=dual?48:15,top=24,bottom=32;
  const end=series.at(-1)?.time||1, start=window?Math.max(series[0]?.time||0,end-window):(series[0]?.time||0);
  const data=series.filter(p=>p.time>=start), x=t=>left+(t-start)/Math.max(.01,end-start)*(w-left-right);
  const values=data.flatMap(p=>lines.filter(l=>!l.right).map(l=>l.value(p))).filter(Number.isFinite);
  let lo=Math.min(0,...values), hi=max??Math.max(0.01,...values); if(hi===lo)hi=lo+1;
  const y=(v,rightAxis=false)=>h-bottom-(rightAxis?v:(v-lo)/(hi-lo))*(h-top-bottom);
  ctx.font='10px ui-monospace,monospace';ctx.fillStyle='#9fb0bf';
  for(let i=0;i<5;i++){
    const f=i/4,py=y(lo+f*(hi-lo));ctx.strokeStyle='#263746';ctx.beginPath();ctx.moveTo(left,py);ctx.lineTo(w-right,py);ctx.stroke();
    ctx.fillStyle='#9fb0bf';ctx.fillText((lo+f*(hi-lo)).toLocaleString(undefined,{maximumFractionDigits:2}),2,py+3);
    if(dual)ctx.fillText(f.toFixed(2),w-right+7,py+3);
  }
  for(let i=0;i<5;i++){const t=start+i/4*(end-start);ctx.fillText(t.toFixed(1),x(t)-12,h-14)}
  ctx.fillText('tempo simulato [s]',Math.max(left,w/2-55),h-1);
  for(const line of lines){ctx.strokeStyle=line.color;ctx.lineWidth=2;ctx.beginPath();let previous=null;
    for(const p of data){const value=line.value(p);if(!Number.isFinite(value)){previous=null;continue}
      const px=x(p.time),py=y(value,line.right);if(previous){if(step)ctx.lineTo(px,previous[1]);ctx.lineTo(px,py)}else ctx.moveTo(px,py);previous=[px,py];
    }ctx.stroke();
  }
  if(!values.length){ctx.fillStyle='#9fb0bf';ctx.fillText('Dati non disponibili',left+12,top+14)}
}
