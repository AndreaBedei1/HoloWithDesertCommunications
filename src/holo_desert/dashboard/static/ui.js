export const $ = s => document.querySelector(s);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number = (x, digits=3) => x == null ? 'N/D' : Number(x).toFixed(digits);
export async function api(url, body) {
  const r = await fetch(url, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await r.json();
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
export function choices(selector, values, placeholder) {
  const el = $(selector), signature = JSON.stringify([values,placeholder]);
  if (el.dataset.choices === signature) return;
  const old = el.value;
  el.innerHTML = (placeholder ? '<option value="">'+esc(placeholder)+'</option>' : '') + values.map(v=>'<option value="'+esc(v)+'">'+esc(v.replace('>',' ↔ '))+'</option>').join('');
  if ([...el.options].some(o=>o.value===old)) el.value = old;
  el.dataset.choices = signature;
}
export function canvas(selector) {
  const c=$(selector), {width:w,height:h}=c.getBoundingClientRect(), d=devicePixelRatio||1;
  c.width=Math.round(w*d); c.height=Math.round(h*d);
  const ctx=c.getContext('2d');ctx.scale(d,d);
  return {c,ctx,w,h};
}
export function fields(data) {
  return '<dl>'+Object.entries(data).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v??'N/D')+'</dd>').join('')+'</dl>';
}
export const statusName = s => ({queued:'Generato',in_flight:'Inserito nello stack',phy_tx_observed:'PHY TX osservata',received:'Consegnato',timeout_unknown_cause:'TTL scaduto / causa ignota'}[s]||s);
export function timeline(events) {
  return events.map(e=>'<li><time>'+number(e.time)+' s</time> <b>'+esc(e.event)+'</b> '+esc(e.node_id||e.node||'')+' '+esc(e.state||e.outcome||'')+
    (e.next_hop_id?' → '+esc(e.next_hop_id):'')+(e.tx_power_db!=null?' · '+number(e.tx_power_db,1)+' dB SPL':'')+'</li>').join('');
}
