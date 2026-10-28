export const $ = s => document.querySelector(s);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number = (x, digits=2) => x == null || !Number.isFinite(Number(x)) ? 'N/A' : Number(x).toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
export async function api(url, body, method='POST') {
  const r = await fetch(url, body === undefined && method==='POST' ? {} : {method,headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data = await r.json();
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
export function choices(selector, values, placeholder, label=value=>value.replace('>',' ↔ ')) {
  const el = $(selector), signature = JSON.stringify([values,placeholder]);
  if (el.dataset.choices === signature) return;
  const old = el.value;
  el.innerHTML = (placeholder ? '<option value="">'+esc(placeholder)+'</option>' : '') + values.map(v=>'<option value="'+esc(v)+'">'+esc(label(v))+'</option>').join('');
  if ([...el.options].some(o=>o.value===old)) el.value = old;
  el.dataset.choices = signature;
}
// Replace only changed markup, keeping open <details> and the scroll position across refreshes.
export function preserve(root,html){
  if(root.innerHTML===html)return;
  const opened=new Set([...root.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent)),scroll=root.scrollTop;
  root.innerHTML=html;root.querySelectorAll('details').forEach(d=>{if(opened.has(d.querySelector('summary')?.textContent))d.open=true});root.scrollTop=scroll;
}
export function canvas(selector) {
  const c=$(selector), {width:w,height:h}=c.getBoundingClientRect(), d=devicePixelRatio||1;
  c.width=Math.round(w*d); c.height=Math.round(h*d);
  const ctx=c.getContext('2d');ctx.scale(d,d);
  return {c,ctx,w,h};
}
export function fields(data) {
  return '<dl>'+Object.entries(data).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v??'N/A')+'</dd>').join('')+'</dl>';
}
export const statusName = s => ({queued:'Generated',in_flight:'In the network',phy_tx_observed:'Transmission observed',received:'Delivered',timeout_unknown_cause:'Expired'}[s]||s);
export function timeline(events) {
  return events.map(e=>'<li><time>'+number(e.time)+' s</time> <b>'+esc(e.event)+'</b> '+esc(e.node_id||e.node||'')+' '+esc(e.state||e.outcome||'')+
    (e.next_hop_id?' → '+esc(e.next_hop_id):'')+(e.tx_power_db!=null?' · '+number(e.tx_power_db,1)+' dB re 1 µPa':e.tx_power_dbm!=null?' · '+number(e.tx_power_dbm,1)+' dBm':e.tx_power_w!=null?' · '+Number(e.tx_power_w).toExponential(3)+' W':'')+'</li>').join('');
}
