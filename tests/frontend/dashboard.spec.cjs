const {test,expect}=require('@playwright/test');
const {fixturePage}=require('./fixtures.cjs');

test('initial screen explains nine scenarios without technical panels or invented graphs',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await expect(page.locator('[data-scenario]')).toHaveCount(9);
  await expect(page.locator('#scenario-title')).toHaveText('Message exchange');await expect(page.getByRole('button',{name:'Start simulation',exact:true})).toBeEnabled();
  await expect(page.locator('#metrics-summary')).toBeHidden();await expect(page.locator('#fleet-canvas')).toBeHidden();
  for(const [id,title]of [['e03_mobility','Moving drones'],['e04_congestion','Network congestion'],['e05_multihop','Relay communication'],['e06_coordination','Drone coordination'],['e07_ranging_tokenbus','Native ranging with TokenBus'],['e08_woss','Bellhop propagation (WOSS)'],['e09_sun_convergecast','SUN convergecast to a sink']]){await page.locator(`[data-scenario="${id}"]`).click();await expect(page.locator('#scenario-title')).toHaveText(title)}
  await page.getByRole('button',{name:'How it works',exact:true}).click();await expect(page.locator('#guide-dialog')).toBeVisible();await page.getByLabel('Close guide').click();
  expect(errors).toEqual([]);
});

test('settings keep advanced fields folded and reject incompatible routes on server',async({page})=>{
  await page.goto('/');await page.locator('[data-scenario="e05_multihop"]').click();await page.locator('#configure').click();
  await expect(page.locator('[data-path="network.mac.protocol"]')).toBeVisible();await expect(page.locator('[data-path="network.mac.ack"]')).toBeHidden();
  await page.locator('#network-form summary').filter({hasText:'Advanced settings'}).click();
  await page.locator('#network-form [data-routes] tr').first().locator('[data-field="hop"]').selectOption('auv_01');
  await page.getByRole('button',{name:'Apply to the next run'}).click();await expect(page.locator('#config-error')).toContainText('own source');
  await page.locator('#network-form [data-routes] tr').first().locator('[data-field="hop"]').selectOption('auv_02');
  await page.locator('[data-path="network.mac.protocol"]').selectOption('aloha');await page.getByRole('button',{name:'Apply to the next run'}).click();
  await expect(page.locator('#config-dialog')).toBeHidden();await expect(page.locator('#scenario-meta')).toContainText('ALOHA');
});

test('real-event presentation distinguishes pending, expired and delivered; filters and timeline work',async({page,request})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await fixturePage(page,request);
  await expect(page.locator('#delivery-rate')).toHaveText('50.0%');await expect(page.locator('#generated')).toHaveText('3');
  await page.locator('[data-node-choice]').selectOption('auv_02');await expect(page.locator('#context-title')).toHaveText('Drone 02');
  await page.locator('.app-header [data-view="messages"]').click();await expect(page.locator('#packet-rows tr[data-id]')).toHaveCount(3);
  await page.locator('#packet-status').selectOption('received');await expect(page.locator('#packet-rows tr[data-id]')).toHaveCount(1);await page.locator('#packet-rows tr[data-id]').click();
  await expect(page.locator('#packet-details')).toContainText('Network forwarding');await expect(page.locator('#packet-details')).toContainText('Delivered to the application');
  await page.locator('#packet-details summary').click();await expect(page.locator('#packet-details pre')).toBeVisible();await expect(page.locator('#packet-details pre')).toBeVisible({timeout:2000});
  await page.locator('#packet-status').selectOption('');await page.locator('#packet-destination').selectOption('auv_02');await expect(page.locator('#packet-rows tr[data-id]')).toHaveCount(1);
  await page.locator('#packet-type').selectOption('heartbeat');await expect(page.locator('#packet-rows')).toContainText('Transmission observed');
  await page.locator('.app-header [data-view="analysis"]').click();await page.locator('[data-group="channel"]').first().click();await expect(page.locator('#queue-chart')).toBeVisible();await expect(page.locator('#pdr-chart')).toBeHidden();
  await page.locator('[data-group="geometry"]').first().click();await expect(page.locator('#distance-chart')).toBeVisible();expect(errors).toEqual([]);
});

test('pause, resume and stop respect observable states',async({page,request})=>{
  await fixturePage(page,request);await expect(page.locator('#pause')).toHaveText('▶ Resume');await page.locator('#pause').click();await expect(page.locator('#run-status')).toHaveText('Simulation running');await page.locator('#pause').click();await expect(page.locator('#run-status')).toHaveText('Paused');await page.locator('#stop').click();await expect(page.locator('#run-status')).toHaveText('Simulation stopped');await expect(page.locator('#pause')).toBeHidden();await expect(page.locator('#rerun')).toBeVisible();
});

test('errors give a useful explanation and keep original diagnostics optional',async({page})=>{
  await page.route('**/api/start',route=>route.fulfill({status:422,json:{detail:'Docker CLI unavailable. Install Docker Desktop.'}}));await page.goto('/');await page.locator('#start').click();await expect(page.locator('#error-title')).toHaveText('DESERT is not ready');await expect(page.locator('#error-detail')).toBeHidden();await page.locator('#error summary').click();await expect(page.locator('#error-detail')).toContainText('Docker CLI unavailable');
});

for(const viewport of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:740,height:900},{width:390,height:844}]){
  test(`responsive ${viewport.width}×${viewport.height} keeps map, controls and dialogs usable`,async({page,request})=>{
    await page.setViewportSize(viewport);await fixturePage(page,request);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const box=await page.locator('#fleet-canvas').boundingBox();expect(box.width).toBeGreaterThan(250);expect(box.height).toBeGreaterThan(200);
    await expect(page.locator('#pause')).toBeInViewport();await page.locator('#guide-open').click();await expect(page.locator('#guide-dialog')).toBeVisible();expect(await page.locator('#guide-dialog').evaluate(el=>el.getBoundingClientRect().width<=innerWidth)).toBe(true);
  });
}
