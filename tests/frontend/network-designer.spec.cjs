const {test,expect}=require('@playwright/test');
test('completed-run fixture: rerun uses newly applied network settings',async({page,request})=>{
 const {fixturePage}=require('./fixtures.cjs'),fixture=await fixturePage(page,request);
 fixture.setState({...fixture.state(),state:'finished',run_id:'rerun-fixture'});
 await expect(page.locator('#rerun')).toBeVisible();
 let submitted;await page.route('**/api/start',r=>{submitted=r.request().postDataJSON();return r.fulfill({json:{state:'starting'}})});
 await page.locator('#configure').click();
 await page.locator('[data-path="network.mac.protocol"]').selectOption('tdma');
 await page.getByRole('button',{name:'Applica alla prossima corsa'}).click();
 await page.locator('#rerun').click();
 await expect.poll(()=>submitted?.configuration.network.mac.protocol).toBe('tdma');
 expect(submitted.configuration.nodes).toHaveLength(3);
});
// Presentation-only fixture: no simulator result is supplied or claimed.
const p=(path,label,value)=>({path,label,type:'number',default:value,min:0,help:'Parametro fixture del Designer.'});
const catalog={modules:[
{id:'csma_aloha',name:'CSMA-ALOHA',layer:'mac',operational:true,parameters:[p('network.mac.buffer_packets','Buffer MAC',50)]},
{id:'tdma',name:'TDMA',layer:'mac',operational:true,parameters:[p('network.mac.tdma.frame_duration_s','Durata frame',20)]},
{id:'bpsk_upstream',name:'BPSK originale',layer:'phy',operational:true,parameters:[p('network.acoustic.bitrate_bps','Bitrate',4800),p('network.acoustic.tx_power_db','Potenza',120)]},
{id:'bpsk_corrected',name:'BPSK corretto',layer:'phy',operational:false,reason:'Fixture: compilazione da verificare.',parameters:[]},
{id:'static',name:'Statico',layer:'routing',operational:true,parameters:[]},
{id:'flooding',name:'Flooding',layer:'routing',operational:true,parameters:[p('network.flooding.ttl','Limite hop',6)]},
{id:'woss',name:'WOSS',layer:'phy',operational:false,reason:'Fixture: dataset batimetrico assente.',parameters:[]}]};
const scenario={name:'e01_chat',description:'Fixture del Designer',duration:30,nodes:[{id:'auv_01',position:[0,0,-20],waypoints:[]},{id:'auv_02',position:[50,0,-20],waypoints:[]}],network:{mac:{protocol:'csma_aloha',buffer_packets:50},acoustic:{bitrate_bps:4800,tx_power_db:120},routes:{}},flows:[{source:'auv_01',destination:'auv_02',interval:3,payload_bytes:32}],power_events:[]};
async function designer(page){await page.route('**/api/scenarios',r=>r.fulfill({json:[{id:'e01_chat',description:scenario.description}]}));await page.route('**/api/scenarios/e01_chat',r=>r.fulfill({json:scenario}));await page.route('**/api/network-catalog',r=>r.fulfill({json:catalog}));await page.goto('/');await expect(page.locator('#scenario-title')).toHaveText('Scambio di messaggi');await page.evaluate(()=>{const banner=document.querySelector('#snapshot-banner');banner.textContent='Fixture: catalogo sintetico, nessuna simulazione';banner.hidden=false});await page.locator('#configure').click();await page.locator('#network-form summary').filter({hasText:'Impostazioni avanzate'}).click();await page.locator('summary').filter({hasText:'Configurazione completa in JSON'}).click();}
test('catalog fixture: operational selectors, dependent MAC, node override and routing',async({page})=>{
const errors=[];page.on('pageerror',e=>errors.push(e.message));await designer(page);await page.locator('#network-form [data-help]').first().focus();await expect(page.locator('#config-dialog #tooltip')).toBeVisible();await page.keyboard.press('Escape');await expect(page.locator('#tooltip')).toBeHidden();await page.locator('#network-form [data-help]').first().click();await expect(page.locator('#config-dialog #tooltip')).toBeVisible();await page.locator('#network-form [data-help]').first().click();await expect(page.locator('#tooltip')).toBeHidden();await expect(page.locator('[data-path="network.acoustic.phy"] option:not([disabled])')).toHaveCount(1);await expect(page.locator('[data-path="network.acoustic.phy"] option[disabled]')).toContainText('non disponibile: Fixture: compilazione da verificare.');await page.locator('[data-path="network.mac.protocol"]').selectOption('tdma');await expect(page.locator('[data-path="network.mac.buffer_packets"]')).toHaveCount(0);await expect(page.locator('[data-path="network.mac.tdma.frame_duration_s"]')).toHaveValue('20');await expect(page.locator('[data-path^="network.mac.tdma.slot_assignment."]')).toHaveCount(2);await page.locator('[data-path="network.routing"]').selectOption('flooding');await expect(page.locator('[data-static-routes]')).toBeHidden();
await page.locator('summary').filter({hasText:'Override acustici per drone'}).click();await page.locator('#network-form summary').filter({hasText:'Drone 01'}).click();await page.locator('[data-path="nodes.0.communication.acoustic.tx_power_db"]').fill('130');await page.locator('#form-to-json').click();const config=JSON.parse(await page.locator('#config-editor').inputValue());expect(config.nodes[0].communication.acoustic.tx_power_db).toBe(130);expect(config.network.mac.protocol).toBe('tdma');expect(config.nodes[1].communication.acoustic.tx_power_db).toBeUndefined();await page.locator('[data-catalog]').click();await expect(page.locator('#network-catalog-dialog')).toContainText('dataset batimetrico assente');expect(errors).toEqual([]);
});
test('catalog fixture: burst and explicit event controls serialize',async({page})=>{await designer(page);await page.locator('summary').filter({hasText:'Flussi applicativi'}).click();const flow=page.locator('.flow-card').first();await flow.locator('[data-field="pattern"]').selectOption('burst');await flow.locator('[data-field="burst_count"]').fill('4');await page.locator('#form-to-json').click();expect(JSON.parse(await page.locator('#config-editor').inputValue()).flows[0].burst_count).toBe(4);await flow.locator('[data-field="pattern"]').selectOption('events');await flow.locator('[data-field="events"]').fill('1, 2.5, 8');await page.locator('#form-to-json').click();expect(JSON.parse(await page.locator('#config-editor').inputValue()).flows[0].events).toEqual([1,2.5,8]);});
test('profile fixture: save, duplicate and revision-aware delete',async({page})=>{let records=[],serial=0,deleted='';await page.route('**/api/network-profiles**',async route=>{const request=route.request(),url=new URL(request.url()),method=request.method();if(method==='GET')return route.fulfill({json:{builtins:[],personal:records}});if(method==='POST'){const record={...request.postDataJSON(),id:'fixture-'+(++serial),kind:'personal',revision:'rev-'+serial};records.push(record);return route.fulfill({json:record})}if(method==='DELETE'){deleted=url.search;records=records.filter(r=>!url.pathname.endsWith('/'+r.id));return route.fulfill({json:{ok:true}})}});await designer(page);await page.locator('#network-profiles-open').click();const dialog=page.locator('#network-profiles-dialog');await dialog.locator('[data-name]').fill('Profilo fixture');await dialog.locator('[data-save]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo salvato.');expect(records[0].network.mac.protocol).toBe('csma_aloha');await dialog.locator('[data-duplicate]').click();await dialog.locator('[data-save]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo salvato.');expect(records).toHaveLength(2);await dialog.locator('[data-delete]').click();await dialog.locator('[data-delete]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo eliminato.');expect(deleted).toBe('?revision=rev-2');expect(records).toHaveLength(1);});
test('profile fixture: apply replaces network while preserving movement and traffic',async({page})=>{
const profile={id:'fixture-builtin',name:'TDMA fixture',revision:'1',network:{...scenario.network,mac:{protocol:'tdma',tdma:{frame_duration_s:20}}}};let validated;await page.route('**/api/network-profiles',r=>r.fulfill({json:{builtins:[profile],personal:[]}}));await page.route('**/api/validate',r=>{validated=r.request().postDataJSON();return r.fulfill({json:validated})});await designer(page);await page.locator('#network-profiles-open').click();await page.locator('[data-profile]').selectOption(profile.id);await page.locator('[data-apply]').click();await expect(page.locator('#network-profiles-dialog')).toBeHidden();expect(validated.network.mac.protocol).toBe('tdma');expect(validated.nodes.map(n=>[n.id,n.position,n.waypoints])).toEqual(scenario.nodes.map(n=>[n.id,n.position,n.waypoints]));expect(validated.flows[0].source).toBe(scenario.flows[0].source);expect(validated.flows[0].interval).toBe(scenario.flows[0].interval);
});
test('catalog fixture: Designer fits desktop and reduced windows',async({page})=>{await designer(page);for(const width of [1920,1440,900]){await page.setViewportSize({width,height:900});await expect(page.locator('#config-dialog')).toBeInViewport();expect(await page.locator('#config-dialog').evaluate(el=>el.getBoundingClientRect().width<=innerWidth)).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)}await page.screenshot({path:test.info().outputPath('network-designer-900.png')});});
test('real API: profile create, edit, export, import draft, apply and delete',async({page,request})=>{
  const name='Browser profilo '+Date.now(),changed=name+' modificato';let id;
  try{await page.goto('/');await expect(page.locator('#scenario-title')).toHaveText('Scambio di messaggi');await page.locator('#configure').click();await expect(page.locator('[data-path="network.acoustic.sound_speed_mps"]')).toHaveCount(1);await expect(page.locator('[data-path="nodes.0.communication.acoustic.sound_speed_mps"]')).toHaveCount(0);await page.locator('#network-profiles-open').click();const dialog=page.locator('#network-profiles-dialog');await dialog.locator('[data-name]').fill(name);await dialog.locator('[data-save]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo salvato.');id=await dialog.locator('[data-profile]').inputValue();expect(id).toMatch(/^profile_/);
    await dialog.locator('[data-name]').fill(changed);await dialog.locator('[data-save]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo salvato.');const data=await (await request.get('/api/network-profiles')).json();expect(data.personal.find(r=>r.id===id).name).toBe(changed);
    const downloaded=page.waitForEvent('download');await dialog.locator('[data-export]').click();expect((await downloaded).suggestedFilename()).toBe(id+'.yaml');const yaml=await (await request.get('/api/network-profiles/'+id+'/yaml')).text();await dialog.locator('[data-file]').setInputFiles({name:'profile.yaml',mimeType:'application/yaml',buffer:Buffer.from(yaml)});await expect(dialog.locator('[data-status]')).toContainText('YAML importato come bozza');await dialog.locator('[data-apply]').click();await expect(dialog).toBeHidden();await expect(page.locator('[data-path="network.mac.protocol"]')).toHaveValue('csma_aloha');
    await page.locator('#network-profiles-open').click();await dialog.locator('[data-profile]').selectOption(id);await dialog.locator('[data-delete]').click();await dialog.locator('[data-delete]').click();await expect(dialog.locator('[data-status]')).toHaveText('Profilo eliminato.');
  }finally{const data=await (await request.get('/api/network-profiles')).json();for(const record of data.personal.filter(r=>[name,changed].includes(r.name)))await request.delete('/api/network-profiles/'+record.id+'?revision='+encodeURIComponent(record.revision));}
});
test('diagnostic fixture: zero interference is not attributed to collision and raw PHY fields remain inspectable',async({page})=>{
  await page.goto('/');const result=await page.evaluate(async()=>{const {eventLabel}=await import('/static/presentation.js'),{packetDetails}=await import('/static/packets.js');const base={event:'phy_rx_end',time:3,node_id:'auv_02',outcome:'interference_error',phy_patch_id:'upstream',positive_interference:false,pt:1e10,pr:1e-9,pn:1e-10,pi:0,phy_bits:800,phy_tx_time:1,phy_rx_time:2,snr_db:10,rx_snr_penalty_db:-10};return {zero:eventLabel(base),unknown:eventLabel({event:'phy_rx_end',outcome:'interference_error'}),corrected:eventLabel({...base,phy_patch_id:'conditional-bpsk-v1',positive_interference:true,pi:1e-9}),html:packetDetails({id:'diagnostic-fixture',source:'auv_01',destination:'auv_02',status:'timeout_unknown_cause',type:'data',size:32,wire_size:100,creation_time:1,deadline:8,events:[base]})}});
  expect(result.zero).toBe('Secondo test PHY fallito (interferenza nulla)');expect(result.unknown).toBe('Errore nel ramo PHY interferenza (causa non misurata)');expect(result.corrected).toBe('Errore di interferenza');expect(result.html).toContain('SNR grezzo Pr/Pn');expect(result.html).toContain('SNR dopo penalit\u00e0');expect(result.html).toContain('unit\u00e0 acustiche normalizzate');expect(result.html).toContain('Dimensione PHY [bit]');expect(result.html).toContain('interference_error');
});
test('observed-state fixture: mixed PHY header and real-event accounting have explicit labels',async({page,request})=>{
  const {fixturePage}=require('./fixtures.cjs'),fixture=await fixturePage(page,request),state=fixture.state();state.configuration.network.acoustic.phy='bpsk_upstream';state.configuration.nodes[1].communication={acoustic:{phy:'bpsk_corrected'}};fixture.setState({...state,engine_info:{phy_patch:'conditional-bpsk-v1'},network_metrics:{data_tx_frames:4,control_tx_frames:2,data_tx_bits:3200,control_tx_bits:128,data_airtime_s:1.2,control_airtime_s:.1,late_received:1}});
  await expect(page.locator('#run-services')).toContainText('PHY misto');await expect(page.locator('#run-services')).toContainText('bpsk_upstream');await expect(page.locator('#run-services')).toContainText('bpsk_corrected');await expect(page.locator('#run-services')).toContainText('Patch motore: conditional-bpsk-v1');await page.locator('.app-header [data-view="analysis"]').click();await page.locator('#advanced-analysis>summary').click();await expect(page.locator('#network-accounting')).toContainText('Frame controllo TX');await expect(page.locator('#network-accounting')).toContainText('Ricevuti dopo TTL');
});

test('real API: legacy MAC buffer appears only for an explicitly bounded queue',async({page,request})=>{
  await page.goto('/');await page.locator('#configure').click();
  const form=page.locator('#network-form');await form.locator('summary').filter({hasText:'Impostazioni avanzate'}).click();
  await expect(form.locator('[data-path="network.mac.queue_mode"]')).toHaveValue('legacy');await expect(form.locator('[data-path="network.mac.buffer_packets"]')).toHaveCount(0);
  await form.locator('[data-path="network.mac.queue_mode"]').selectOption('bounded');await form.locator('[data-path="network.mac.buffer_packets"]').fill('1');
  const validated=page.waitForRequest(r=>r.url().endsWith('/api/validate')&&r.method()==='POST');await page.getByRole('button',{name:'Applica alla prossima corsa'}).click();
  expect((await validated).postDataJSON().network.mac).toMatchObject({protocol:'csma_aloha',queue_mode:'bounded',buffer_packets:1});await expect(page.locator('#config-dialog')).toBeHidden();
  await page.locator('#configure').click();await expect(form.locator('[data-path="network.mac.queue_mode"]')).toHaveValue('bounded');await expect(form.locator('[data-path="network.mac.buffer_packets"]')).toHaveValue('1');
});

// Real catalogue served by the dashboard; only /api/validate answers are inspected.
const openAdvanced=form=>form.locator('details:has(> summary:text-is("Impostazioni avanzate"))').evaluate(d=>d.open=true);
async function realDesigner(page){await page.goto('/');await expect(page.locator('#scenario-title')).toHaveText('Scambio di messaggi');await page.locator('#configure').click();const form=page.locator('#network-form');await openAdvanced(form);return form}
async function applied(page){const validated=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.request().method()==='POST');await page.getByRole('button',{name:'Applica alla prossima corsa'}).click();const response=await validated;expect(response.status()).toBe(200);await expect(page.locator('#config-dialog')).toBeHidden();return response.json()}
const helpOf=(form,path)=>form.locator('label:has([data-path="'+path+'"]) [data-help]').first().getAttribute('data-help');
test('real catalogue: optical and EM media expose their native parameters and restrict MAC/routing with reasons',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));const form=await realDesigner(page);
  await expect(form.locator('[data-path="network.medium"] option')).toHaveText(['Acustica','Ottica','Elettromagnetica']);
  await form.locator('[data-path="network.medium"]').selectOption('em');
  await expect(form.locator('[data-path="network.em.tx_power_dbm"]')).toHaveValue('14');
  const power=await helpOf(form,'network.em.tx_power_dbm');expect(power).toContain('Unità: dBm');expect(power).toContain('Predefinito: 14 dBm');expect(power).toContain('da -100 a 100 dBm');
  await expect(form.locator('[data-path="network.mac.protocol"] option:not([disabled])')).toHaveText(['CSMA-ALOHA']);
  await expect(form.locator('[data-path="network.mac.protocol"] option',{hasText:'TDMA Frame'})).toContainText('non verificato con la tecnologia elettromagnetica');
  await expect(form.locator('[data-path="network.routing"] option',{hasText:'Flooding'})).toContainText('solo il routing statico');
  await expect(form.locator('[data-path="network.acoustic.phy"]')).toHaveCount(0);
  await form.locator('[data-path="network.em.tx_power_dbm"]').fill('-20');
  const em=await applied(page);expect(em.network.medium).toBe('em');expect(em.network.em.tx_power_dbm).toBe(-20);
  await page.locator('#configure').click();await openAdvanced(form);
  await form.locator('[data-path="network.medium"]').selectOption('optical');
  await expect(form.locator('[data-path="network.optical.attenuation_per_m"]')).toHaveValue('0.043');
  expect(await helpOf(form,'network.optical.beam_angle_rad')).toContain('da 0 a 1,56');
  const optical=await applied(page);expect(optical.network.medium).toBe('optical');expect(errors).toEqual([]);
});
test('real catalogue: WOSS adds Bellhop parameters and an SSP table and excludes incompatible choices',async({page})=>{
  const form=await realDesigner(page);await form.locator('[data-path="network.acoustic.propagation"]').selectOption('woss');
  await expect(form.locator('[data-path="network.woss.water_depth_m"]')).toHaveValue('100');
  await expect(form.locator('[data-path="network.acoustic.phy"] option',{hasText:'BPSK corretto'})).toContainText('WOSS usa il PHY BPSK originale');
  await expect(form.locator('[data-path="network.medium"] option',{hasText:'Ottica'})).toContainText('non combinabile con WOSS');
  await expect(form.locator('[data-ssp-row]')).toHaveCount(2);await expect(form.locator('[data-remove-ssp]').first()).toBeDisabled();
  await form.locator('[data-add-ssp]').click();await expect(form.locator('[data-ssp-row]')).toHaveCount(3);
  await form.locator('[data-ssp-row]').nth(1).locator('[data-ssp="speed_mps"]').fill('1490');
  const woss=await applied(page);expect(woss.network.acoustic.propagation).toBe('woss');
  expect(woss.network.woss.ssp).toEqual([{depth_m:0,speed_mps:1500},{depth_m:50,speed_mps:1490},{depth_m:100,speed_mps:1500}]);
});
test('real catalogue: multi-PHY editor validates thresholds, availability and renamed interfaces',async({page})=>{
  const form=await realDesigner(page);await form.locator('summary').filter({hasText:'Interfacce multiple'}).click();
  await form.locator('[data-multiphy]').check();await expect(form.locator('[data-mp-row]')).toHaveCount(2);
  await expect(form.locator('[data-path="network.mac.protocol"] option:not([disabled])')).toHaveText(['CSMA-ALOHA']);
  await expect(form.locator('[data-path="network.acoustic.propagation"] option',{hasText:'WOSS'})).toContainText('il multi-PHY usa la propagazione analitica');
  await form.locator('[data-mp-row]').nth(1).locator('[data-mp-id]').fill('fast');await form.locator('[data-mp-row]').nth(1).locator('[data-mp-id]').blur();
  await form.locator('[data-available][data-node="auv_02"][data-interface="fast"]').uncheck();
  const manual=await applied(page);expect(manual.network.multiphy.interfaces.map(i=>i.id)).toEqual(['long','fast']);
  expect(manual.nodes[1].communication.interfaces).toEqual(['long']);expect(manual.nodes[0].communication?.interfaces??null).toBeNull();
  await page.locator('#configure').click();await openAdvanced(form);
  await form.locator('[data-path="network.multiphy.policy"]').selectOption('received_power');
  await expect(form.locator('[data-threshold]')).toHaveCount(2);expect(await form.locator('h3:has-text("Soglia") [data-help]').first().getAttribute('data-help')).toContain('µPa²');
  await form.locator('[data-threshold][data-from="long"] input').fill('2e12');
  const automatic=await applied(page);expect(automatic.network.multiphy.policy).toBe('received_power');
  expect(automatic.network.multiphy.thresholds).toEqual([{from_interface:'long',to_interface:'fast',power_linear:2e12},{from_interface:'fast',to_interface:'long',power_linear:1e11}]);
  expect(automatic.nodes[1].communication?.interfaces??null).toBeNull();
});
test('real catalogue: native CBR/VBR generators expose native timers and disable Python-only options',async({page})=>{
  const form=await realDesigner(page);await form.locator('summary').filter({hasText:'Flussi applicativi'}).click();const flow=form.locator('.flow-card').first();
  await expect(flow.locator('[data-field="generator"] option',{hasText:'VBR'})).toContainText('non genera risposte');
  await flow.locator('summary').click();await flow.locator('[data-field="reply"]').uncheck();
  await flow.locator('[data-field="generator"]').selectOption('desert_vbr');
  await expect(flow.locator('[data-field="native_duration2_s"]')).toHaveValue('5');await expect(flow.locator('[data-field="payload_bytes"]')).toHaveCount(0);
  await expect(flow.locator('[data-field="pattern"] option[value="burst"]')).toHaveAttribute('disabled','');await expect(flow.locator('[data-field="ttl"]')).toBeDisabled();
  expect(await flow.locator('label:has([data-field="native_period2_s"]) [data-help]').getAttribute('data-help')).toContain('secondo stato');
  await flow.locator('[data-field="native_packet_bytes"]').fill('64');
  const vbr=await applied(page);expect(vbr.flows[0]).toMatchObject({generator:'desert_vbr',native_packet_bytes:64,reply:false,message_type:'data',pattern:'periodic'});
});
test('real catalogue: every Designer control explains meaning, unit, default and constraints',async({page})=>{
  const form=await realDesigner(page);await form.locator('summary').filter({hasText:'Interfacce multiple'}).click();await form.locator('[data-multiphy]').check();
  for(const medium of ['acoustic','em','optical']){
    if(medium!=='acoustic'){if(await form.locator('[data-multiphy]').count())await form.locator('[data-multiphy]').uncheck();await form.locator('[data-path="network.medium"]').selectOption(medium)}
    const missing=await form.evaluate(root=>[...root.querySelectorAll('[data-path]')].filter(el=>!el.closest('[data-routes]')).map(el=>{const text=el.closest('label')?.querySelector('[data-help]')?.dataset.help||'',numeric=el.type==='number',override=el.dataset.path.startsWith('nodes.');return {path:el.dataset.path,ok:!!text&&(!numeric||/Unità: /.test(text)&&/Vincoli: /.test(text)&&(override||/Predefinito: /.test(text)))}}).filter(x=>!x.ok).map(x=>x.path));
    expect(missing,medium).toEqual([]);
  }
});
test('ranging fixture: native estimates are shown beside the HoloOcean geometric reference',async({page,request})=>{
  const {fixturePage}=require('./fixtures.cjs'),fixture=await fixturePage(page,request),state=fixture.state();state.configuration.network.mac.protocol='ranging_tokenbus';
  const latest=[{time:12,observer:'auv_01',pair:'auv_01>auv_02',peer_a:'auv_01',peer_b:'auv_02',protocol:'ranging_tokenbus',valid:true,travel_time_s:.3333,distance_m:499.95,geometric_distance_m:500,error_m:-.05},{time:12,observer:'auv_03',pair:'auv_01>auv_02',peer_a:'auv_01',peer_b:'auv_02',protocol:'ranging_tokenbus',valid:false,travel_time_s:null,distance_m:null,geometric_distance_m:500,error_m:null}];
  fixture.setState({...state,ranging:{series:{'auv_01>auv_02':[{time:1,geometric_distance_m:500,estimates:{auv_01:499.9}},{time:12,geometric_distance_m:500,estimates:{auv_01:499.95}}]},latest}});
  await page.locator('.app-header [data-view="analysis"]').click();await page.locator('#analysis-tabs [data-group="ranging"]').click();
  await expect(page.locator('#ranging-key')).toContainText('Distanza geometrica HoloOcean · riferimento');await expect(page.locator('#ranging-key')).toContainText('Stima DESERT misurata da Drone 01');
  await expect(page.locator('#ranging-table tbody tr')).toHaveCount(2);await expect(page.locator('#ranging-table tbody tr').first()).toContainText('499,95');await expect(page.locator('#ranging-table tbody tr').nth(1)).toContainText('Non ancora misurata');
  await expect(page.locator('#ranging-note')).toContainText('non espone l’istante della misura');await expect(page.locator('#pair-filter-label')).toBeVisible();
  fixture.setState({...state,ranging:{series:{},latest:[]}});await expect(page.locator('#ranging-empty')).toContainText('Nessuna stima di distanza');
});
test('observed-state fixture: multi-PHY interface names and EM power units in timelines',async({page,request})=>{
  const {fixturePage}=require('./fixtures.cjs'),fixture=await fixturePage(page,request),state=fixture.state();
  state.configuration.network.multiphy={interfaces:[{id:'long',acoustic:{}},{id:'short',acoustic:{}}],policy:'manual',initial_interface:'long',master:'auv_01',thresholds:[],alpha:.5};
  state.packets[0].events=state.packets[0].events.map(e=>e.event==='phy_tx_start'?{...e,interface_index:2}:e);
  fixture.setState({...state,transitions:[{event:'power_applied',time:5,node:'auv_01',node_id:'auv_01',tx_power_dbm:-20}]});
  await page.locator('[data-packet="received-001"]').first().click();await expect(page.locator('#context-content')).toContainText('Interfaccia: short · 2');
  await page.locator('.app-header [data-view="analysis"]').click();await page.locator('#advanced-analysis>summary').click();await expect(page.locator('#application-events')).toContainText('-20,0 dBm');
});
