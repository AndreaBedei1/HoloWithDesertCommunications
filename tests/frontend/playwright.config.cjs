const {defineConfig}=require('@playwright/test');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const port=Number(process.env.HOLO_UI_PORT||8011);
const python=process.env.HOLO_PYTHON||(process.platform==='win32'?path.join(root,'.venv/Scripts/python.exe'):'python');
module.exports=defineConfig({
  testDir:__dirname,testMatch:'*.spec.cjs',workers:1,timeout:30000,
  outputDir:path.join(root,'.local/ui-test-results'),reporter:'list',
  use:{baseURL:`http://127.0.0.1:${port}`,headless:true,channel:process.platform==='win32'?'msedge':undefined,viewport:{width:1440,height:900},screenshot:'only-on-failure'},
  webServer:{command:`"${python}" -m holo_desert dashboard --port ${port}`,cwd:root,url:`http://127.0.0.1:${port}/api/state`,reuseExistingServer:false,timeout:60000,
    env:{HOLO_DESERT_SCENARIOS_DIR:path.join(root,'.local/ui-test-library')}},
});
