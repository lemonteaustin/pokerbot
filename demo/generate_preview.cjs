// Screenshot the actual demo for social previews; no game changes are saved.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const path=require('node:path');const {pathToFileURL}=require('node:url');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1200,height:630},deviceScaleFactor:1});
 await page.addInitScript(()=>{let seed=991;Math.random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);});
 await page.clock.install();await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
 await page.locator('#play').click();await page.locator('#call').click();await page.clock.runFor(600);
 await page.addStyleTag({content:'.sidebar,.controls,.help-panel,footer,.result{display:none!important}.shell{max-width:none;padding:24px 60px}.layout{display:block}.table{height:475px;width:100%}.header{margin-bottom:16px}h1{font-size:34px}.table-meta{padding-bottom:12px}'});
 await page.screenshot({path:path.join(__dirname,'preview.png'),animations:'disabled'});
 console.log('Saved demo/preview.png (1200 x 630)');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
