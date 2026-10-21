const {test,expect}=require('@playwright/test');
async function cleanLibrary({request}){const records=await (await request.get('/api/user-scenarios')).json();for(const record of records)await request.delete('/api/user-scenarios/'+record.id+'?revision='+record.revision)}
test.beforeEach(cleanLibrary);
test.afterEach(cleanLibrary);

test('empty personal library and invalid drone edits give useful choices without losing the draft',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');
  await page.locator('#personal-tab').click();await expect(page.locator('#scenario-card')).toBeHidden();await expect(page.locator('#configure')).toBeDisabled();
  await page.locator('#new-scenario').click();await page.locator('[data-general="name"]').fill('Bozza da conservare');await page.locator('[data-general="description"]').fill('Verifica della bozza e dei controlli sui droni.');await page.locator('#editor-next').click();
  await page.locator('[data-node="id"]').fill('auv_02');await page.locator('[data-add-waypoint]').click();await expect(page.locator('#editor-error')).toContainText('univoco');await expect(page.locator('[data-waypoint]')).toHaveCount(0);
  await page.locator('[data-node="id"]').fill('auv_01');await page.locator('[data-add-waypoint]').click();await expect(page.locator('[data-waypoint]')).toHaveCount(1);
  await page.locator('#editor-close').click();await page.locator('#confirm-cancel').click();await expect(page.locator('#editor')).toBeVisible();
  await page.locator('#editor-close').click();await page.locator('#confirm-accept').click();await expect(page.locator('#editor')).toBeHidden();expect(errors).toEqual([]);
});

test('create three drones, edit positions and waypoints, configure relay, save, reload, export and delete',async({page,request})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await page.locator('#new-scenario').click();
  await page.locator('[data-general="name"]').fill('Rete personale con relay');await page.locator('[data-general="description"]').fill('Tre droni, due tratte e un messaggio da seguire.');await page.locator('[data-general="duration"]').fill('8');
  await page.locator('#editor-next').click();await page.locator('[data-add-node]').click();await expect(page.locator('[data-select-node]')).toHaveCount(3);
  // The third drone sits midway between the two original drones, at the preview centre.
  await page.locator('[data-node="x"]').fill('15');
  const canvas=page.locator('#editor-canvas');await canvas.scrollIntoViewIfNeeded();const map=await canvas.boundingBox();
  await canvas.hover();await page.mouse.down();await page.mouse.move(map.x+map.width/2+18,map.y+map.height/2-10,{steps:4});await page.mouse.up();
  await expect(page.locator('[data-node="x"]')).not.toHaveValue('15');await page.locator('[data-add-waypoint]').click();await expect(page.locator('[data-waypoint]')).toHaveCount(1);
  await page.locator('#editor-next').click();await page.locator('.flow-card [data-field="destination"]').selectOption('auv_03');await page.locator('#editor-next').click();
  await page.locator('[data-network-root] summary').filter({hasText:'Impostazioni avanzate'}).click();await page.locator('[data-add-route]').click();
  await page.locator('[data-routes] [data-field="destination"]').selectOption('auv_03');await page.locator('[data-routes] [data-field="hop"]').selectOption('auv_02');await page.locator('#editor-next').click();await page.locator('#editor-save').click();await expect(page.locator('#editor')).toBeHidden();
  await expect(page.locator('#scenario-title')).toHaveText('Rete personale con relay');await expect(page.locator('#scenario-meta')).toContainText('3');
  let records=await (await request.get('/api/user-scenarios')).json();expect(records).toHaveLength(1);const id=records[0].id;let record=await (await request.get('/api/user-scenarios/'+id)).json();expect(record.configuration.network.routes.auv_01.auv_03).toBe('auv_02');expect(record.configuration.nodes[2].waypoints).toHaveLength(1);
  await page.locator('#edit-scenario').click();await page.locator('[data-general="name"]').fill('Relay modificato');await page.locator('[data-step="4"]').click();await page.locator('#editor-save').click();await expect(page.locator('#editor')).toBeHidden();await page.reload();await page.locator('#personal-tab').click();await page.locator('[data-scenario="'+id+'"]').click();await expect(page.locator('#scenario-title')).toHaveText('Relay modificato');
  const downloadPromise=page.waitForEvent('download');await page.locator('#export-scenario').click();const download=await downloadPromise;expect(download.suggestedFilename()).toBe('scenario.yaml');
  await page.locator('#delete-scenario').click();await expect(page.locator('#confirm-dialog')).toBeVisible();await page.locator('#confirm-cancel').click();expect((await (await request.get('/api/user-scenarios')).json()).length).toBe(1);
  await page.locator('#delete-scenario').click();await page.locator('#confirm-accept').click();await expect(page.locator('#personal-count')).toHaveText('0');expect(errors).toEqual([]);
});

test('duplicate E03 preserves original motion, import YAML and remove a node with references',async({page,request})=>{
  await page.goto('/');await page.locator('[data-scenario="e03_mobility"]').click();await expect(page.locator('#edit-scenario')).toBeHidden();await expect(page.locator('#delete-scenario')).toBeHidden();
  await page.locator('#duplicate-scenario').click();await expect(page.locator('[data-general="name"]')).toHaveValue('Droni in movimento · copia');await page.locator('[data-step="4"]').click();await page.locator('#editor-save').click();await expect(page.locator('#editor')).toBeHidden();
  await expect(page.locator('#scenario-title')).toHaveText('Droni in movimento · copia');
  let records=await (await request.get('/api/user-scenarios')).json();const copy=await (await request.get('/api/user-scenarios/'+records[0].id)).json();const original=await (await request.get('/api/scenarios/e03_mobility')).json();expect(copy.configuration.nodes).toEqual(original.nodes);
  const yaml=await (await request.get('/api/scenarios/'+copy.id+'/yaml')).text();await page.locator('#import-file').setInputFiles({name:'scenario.yaml',mimeType:'application/yaml',buffer:Buffer.from(yaml)});await page.locator('[data-general="name"]').fill('Scenario importato');await page.locator('[data-step="4"]').click();await page.locator('#editor-save').click();await expect(page.locator('#editor')).toBeHidden();await expect(page.locator('#scenario-title')).toHaveText('Scenario importato');
  await page.locator('#edit-scenario').click();await page.locator('[data-step="1"]').click();await page.locator('[data-remove-node]').click();await page.locator('#confirm-accept').click();await page.locator('[data-add-node]').click();await page.locator('[data-step="2"]').click();await expect(page.locator('.flow-card')).toHaveCount(0);await page.locator('[data-step="4"]').click();await page.locator('#editor-save').click();await expect(page.locator('#editor')).toBeHidden();await expect(page.locator('#scenario-title')).toHaveText('Scenario importato');
  expect((await (await request.get('/api/scenarios/e03_mobility')).json()).nodes).toEqual(original.nodes);
});

test('startup keeps editor actions unavailable until the initial state is loaded',async({page})=>{
  let release,stateRequested;const pending=new Promise(resolve=>release=resolve),requested=new Promise(resolve=>stateRequested=resolve);let first=true;
  await page.route('**/api/state',async route=>{if(!first)return route.continue();first=false;const response=await route.fetch();stateRequested();await pending;await route.fulfill({response})});
  try{
    await page.goto('/');await requested;
    const create=page.locator('#new-scenario');await create.focus();await expect(create).not.toBeFocused();
    release();await create.click();await page.locator('[data-general="name"]').fill('Bozza dopo il caricamento');await expect(page.locator('#editor')).toBeVisible();
  }finally{release()}
});
