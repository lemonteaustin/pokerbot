#!/usr/bin/env node
// Optional UI test dependency: npm install --no-save playwright (outside demo).
// Set PLAYWRIGHT_MODULE to its absolute package directory if installed elsewhere.
'use strict';
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const url=process.env.DEMO_URL || pathToFileURL(path.join(__dirname,'index.html')).href;
const output=path.join(__dirname,'test_results');
fs.mkdirSync(output,{recursive:true});

(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const errors=[],requests=[],runs=[];
  try {
    for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:320,height:740}]) {
      const page=await browser.newPage({viewport,hasTouch:viewport.width<500});
      page.on('pageerror',e=>errors.push(String(e)));
      page.on('request',request=>requests.push(request.url()));
      // Deterministic decks and a virtual clock; the UI still schedules a real 600ms wait.
      await page.addInitScript(()=>{let seed=991;Math.random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);});
      await page.clock.install({time:new Date('2030-01-01T00:00:00Z')});
      await page.goto(url);
      await page.clock.pauseAt(new Date('2030-01-01T00:00:10Z'));
      assert.equal(await page.title(),'Play My Poker Bot');
      assert.equal(await page.locator('#bot-cards .back').count(),2);
      assert.equal(await page.locator('#check').isDisabled(),true);
      await page.locator('#half-pot').click();assert.equal(await page.locator('#raise-slider').inputValue(),'40');
      await page.locator('#full-pot').click();assert.equal(await page.locator('#raise-slider').inputValue(),'60');
      await page.locator('#all-in').click();assert.equal(await page.locator('#raise-slider').inputValue(),'2000');
      await page.locator('#raise-slider').fill('77');assert.equal(await page.locator('#raise-value').textContent(),'77');
      await page.locator('#call').click();
      assert.equal(await page.locator('#turn').textContent(),'Bot is thinking…');
      await page.clock.runFor(599);
      assert.equal(await page.locator('#bot-action').textContent(),'Waiting for the first move');
      await page.clock.runFor(1);
      assert.notEqual(await page.locator('#bot-action').textContent(),'Waiting for the first move');
      assert.ok((await page.locator('#reason').textContent()).length<200);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
      await page.screenshot({path:path.join(output,`browser-${viewport.width}.png`),fullPage:true});
      let matches=0,steps=0,reveals=0;
      while(matches<2 && steps++<1500) {
        assert.equal(await page.locator('#error').isVisible(),false);
        const chipTotal=await page.evaluate(()=>['human-stack','bot-stack','pot'].reduce((total,id)=>total+Number(document.getElementById(id).textContent.replaceAll(',','')),0));
        assert.equal(chipTotal,4000);
        if(await page.locator('#next-controls').isVisible()) {
          const log=await page.locator('#log').textContent();
          if(log.includes('Showdown')){assert.equal(await page.locator('#bot-cards .back').count(),0);reveals++;}
          else assert.equal(await page.locator('#bot-cards .back').count(),2);
          if(await page.locator('#next-hand').textContent()==='Play again')matches++;
          await page.locator('#next-hand').click();
          continue;
        }
        if(await page.locator('#turn').textContent()==='Bot is thinking…') {await page.clock.runFor(600);continue;}
        // First match calls down; second uses the actual slider and all-in button.
        if(matches && await page.locator('#raise').isEnabled()) {
          await page.locator('#all-in').click();await page.locator('#raise').click();
        } else if(await page.locator('#check').isEnabled())await page.locator('#check').click();
        else await page.locator('#call').click();
      }
      assert.equal(matches,2);assert.ok(reveals>0);
      assert.equal(await page.locator('#hand-number').textContent(),'1');
      assert.equal(await page.locator('#bot-action').textContent(),'Waiting for the first move');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow after play');
      runs.push({viewport,matches,steps,showdownReveals:reveals});
      await page.close();
    }
    assert.deepEqual(errors,[]);
    // The standalone game never loads scripts, fonts, equity, or assets over the network.
    const gameRequests=requests.filter(u=>!u.endsWith('/favicon.ico'));
    assert.ok(gameRequests.every(u=>u===url),`Unexpected external request: ${gameRequests}`);
    const report={passed:true,url,runs,pageErrors:errors,externalRequests:0};
    fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
