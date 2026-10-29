const {test,expect}=require('@playwright/test');
const {default:AxeBuilder}=require('@axe-core/playwright');
const {fixturePage}=require('./fixtures.cjs');

// WCAG 2.2 A/AA rules checked by axe-core, including 1.4.3 text contrast (4.5:1, 3:1 for large text).
const WCAG=['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22a','wcag22aa'];
async function audit(page,name){
  const {violations}=await new AxeBuilder({page}).withTags(WCAG).analyze();
  const report=violations.map(v=>v.id+': '+v.nodes.slice(0,5).map(n=>n.target.join(' ')+(n.any[0]?.message?' — '+n.any[0].message:'')).join(' | '));
  expect(report,name).toEqual([]);
}
// Small text is the main readability complaint: nothing rendered below 12 px, body text at least 16 px.
async function sizes(page,name){
  const tooSmall=await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(el=>{
    if(!el.checkVisibility?.()||![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))return false;
    return parseFloat(getComputedStyle(el).fontSize)<12}).slice(0,8).map(el=>el.tagName.toLowerCase()+'.'+[...el.classList].join('.')+' '+getComputedStyle(el).fontSize));
  expect(tooSmall,name).toEqual([]);
  expect(await page.evaluate(()=>parseFloat(getComputedStyle(document.body).fontSize))).toBeGreaterThanOrEqual(16);
}

test('home screen meets WCAG 2.2 AA and minimum text sizes',async({page})=>{
  await page.goto('/');await expect(page.locator('[data-scenario]')).toHaveCount(9);
  await audit(page,'home');await sizes(page,'home');
});

test('simulation, messages and analysis meet WCAG 2.2 AA and minimum text sizes',async({page,request})=>{
  await fixturePage(page,request);
  await audit(page,'simulation');await sizes(page,'simulation');
  await page.locator('.app-header [data-view="messages"]').click();await page.locator('#packet-rows tr[data-id="received-001"]').click();
  await expect(page.locator('#packet-details')).toContainText('Delivered to the application');
  await audit(page,'messages');await sizes(page,'messages');
  await page.locator('.app-header [data-view="analysis"]').click();
  await audit(page,'analysis');await sizes(page,'analysis');
});

test('settings and guide dialogs meet WCAG 2.2 AA',async({page})=>{
  await page.goto('/');await page.locator('[data-scenario="e05_multihop"]').click();await page.locator('#configure').click();
  await expect(page.locator('#config-dialog')).toBeVisible();await audit(page,'settings');await sizes(page,'settings');
  await page.keyboard.press('Escape');await page.locator('#guide-open').click();await expect(page.locator('#guide-dialog')).toBeVisible();
  await audit(page,'guide');
});
