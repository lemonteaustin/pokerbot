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
    for(const viewport of [{width:1440,height:900},{width:390,height:844},{width:320,height:740}]) {
      const page=await browser.newPage({viewport,hasTouch:viewport.width<500});
      page.on('pageerror',e=>errors.push(String(e)));
      page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
      page.on('request',request=>requests.push(request.url()));
      // Deterministic decks and a virtual clock; the UI still schedules a real 600ms wait.
      await page.addInitScript(()=>{let seed=991;Math.random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);});
      await page.clock.install({time:new Date('2030-01-01T00:00:00Z')});
      await page.goto(url);
      await page.clock.pauseAt(new Date('2030-01-01T00:00:10Z'));
      assert.equal(await page.title(),'Play My Poker Bot');
      assert.equal(await page.locator('#start-dialog').isVisible(),true);
      await page.locator('#play').click();
      assert.equal(await page.locator('#reason').textContent(),'Waiting for your move');
      await page.locator('#about-open').click();
      assert.equal(await page.locator('#about-dialog').isVisible(),true);
      await page.locator('#about-close').click();
      assert.equal(await page.locator('#scoreboard').textContent(),'You 0 · Bot 0');
      assert.equal(await page.locator('#bot-seat .seat-name').textContent(),"Austin's bot");
      assert.ok(!(await page.locator('body').innerText()).includes('· v7'));
      assert.ok(!(await page.locator('footer').innerText()).includes('AI coding tools'));
      assert.ok((await page.locator('#log').innerText()).includes('You post 10'));
      assert.equal(await page.locator('#raise').textContent(),'Raise to 40 R');
      assert.equal(await page.locator('label[for=raise-slider]').textContent(),'Raise to');
      assert.equal(await page.locator('#bot-bb').textContent(),'99 BB');
      assert.equal(await page.locator('#human-bet-amount').textContent(),'10');
      assert.equal(await page.locator('#bot-bet-amount').textContent(),'20');
      assert.equal(await page.locator('#pot').textContent(),'30');
      assert.equal(await page.locator('#human-blind').textContent(),'Small blind');
      assert.equal(await page.locator('#bot-blind').textContent(),'Big blind');
      assert.ok((await page.locator('#human-hand').textContent()).length>3);
      assert.equal(await page.locator('#bot-cards .back').count(),2);
      assert.equal(await page.locator('#call').textContent(),'Call 10 C');
      await page.locator('#half-pot').click();assert.equal(await page.locator('#raise-slider').inputValue(),'40');
      await page.locator('#full-pot').click();assert.equal(await page.locator('#raise-slider').inputValue(),'60');
      await page.locator('#all-in').click();assert.equal(await page.locator('#raise-slider').inputValue(),'2000');
      await page.locator('#raise-slider').fill('77');assert.equal(await page.locator('#raise-value').textContent(),'77');
      if(viewport.width>670){await page.locator('#call').focus();await page.keyboard.press('c');}
      else await page.locator('#call').click();
      assert.equal(await page.locator('#turn').textContent(),'Bot is thinking…');
      await page.clock.runFor(599);
      assert.equal(await page.locator('#bot-action').textContent(),'New hand');
      await page.clock.runFor(1);
      assert.notEqual(await page.locator('#bot-action').textContent(),'New hand');
      assert.ok((await page.locator('#reason').textContent()).length<200);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
      async function checkLayout() {
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
        if(viewport.width>670) assert.ok(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),'Laptop page scrolls');
        const box=await page.locator('.controls').boundingBox();
        assert.ok(box.y>=0 && box.y+box.height<=viewport.height+1,'Controls outside viewport');
        if(viewport.width<671)assert.ok(Math.abs(box.y+box.height-viewport.height)<1,'Phone controls are not pinned');
      }
      await checkLayout();
      if(viewport.width===390) {
        const cards=await page.locator('#human-cards').boundingBox(),strip=await page.locator('#thinking-panel').boundingBox();
        assert.ok(cards.y+cards.height<=strip.y,'Cards hidden behind dock');
      }
      await page.screenshot({path:path.join(output,`browser-${viewport.width}.png`),fullPage:true,animations:'disabled'});
      let matches=0,steps=0,reveals=0;
      const won=[0,0];
      while(matches<2 && steps++<1500) {
        assert.equal(await page.locator('#error').isVisible(),false);
        const chipTotal=await page.evaluate(()=>['human-stack','bot-stack','pot'].reduce((total,id)=>total+Number(document.getElementById(id).textContent.replaceAll(',','')),0));
        assert.equal(chipTotal,4000);
        if(await page.locator('#next-controls').isVisible()) {
          const log=await page.locator('#log').textContent();
          if(log.includes('Showdown')){
            assert.equal(await page.locator('#bot-cards .back').count(),0);reveals++;
            const highlighted=await page.locator('.card.winning').count();
            assert.ok(highlighted>=5 && highlighted<=7,'Winning five not highlighted');
            if(!(await page.locator('#result').textContent()).includes('Split pot'))assert.equal(highlighted,5);
            assert.ok(/high|pair|Pair|flush|Flush|house|Three|Four|straight|Royal/.test(await page.locator('#result').textContent()),'Missing winning hand name');
          }
          else assert.equal(await page.locator('#bot-cards .back').count(),0);
          await checkLayout();
          if(await page.locator('#next-hand').textContent()==='Play again') {
            assert.ok((await page.locator('#biggest-pot').textContent()).includes('Biggest pot:'));
            await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copiedShare=text;}}}));
            await page.locator('#share-result').click();
            assert.ok((await page.evaluate(()=>window.copiedShare)).includes('https://play-my-poker-bot.vercel.app/'));
            matches++;
            won[(await page.locator('#human-stack').textContent())==='4,000'?0:1]++;
            assert.equal(await page.locator('#match-dialog').isVisible(),true);
            assert.ok((await page.locator('#match-summary').textContent()).includes('hands played'));
            assert.equal(await page.locator('#scoreboard').textContent(),`You ${won[0]} · Bot ${won[1]}`);
            await page.clock.runFor(350);
            if(matches===1)await page.screenshot({path:path.join(output,`match-end-${viewport.width}.png`),fullPage:true,animations:'disabled'});
            await page.locator('#view-hand').click();
            assert.equal(await page.locator('#match-dialog').isVisible(),false);
            await page.screenshot({path:path.join(output,`showdown-${viewport.width}.png`),fullPage:true,animations:'disabled'});
            if(matches===1) {
              // Reopen the same native dialog to test its actual Play again control.
              await page.evaluate(()=>document.getElementById('match-dialog').showModal());
              await page.locator('#play-again').click();
            } else {
            await page.locator('#next-hand').click();
            assert.ok(['Waiting for your move','Bot is thinking…'].includes(await page.locator('#reason').textContent()));
          }
          } else {
            await page.locator('#next-hand').click();
            assert.ok(['Waiting for your move','Bot is thinking…'].includes(await page.locator('#reason').textContent()));
          }
          continue;
        }
        if(await page.locator('#turn').textContent()==='Bot is thinking…') {await page.clock.runFor(600);continue;}
        // First match calls down; second uses the actual slider and all-in button.
        if(matches && await page.locator('#raise').isEnabled()) {
          await page.locator('#all-in').click();
          if(viewport.width>670)await page.keyboard.press('r');else await page.locator('#raise').click();
        } else await page.locator('#call').click();
      }
      assert.equal(matches,2);assert.ok(reveals>0);
      assert.equal(await page.locator('#hand-number').textContent(),'1');
      assert.equal(await page.locator('#bot-action').textContent(),'New hand');
      assert.equal(await page.locator('#scoreboard').textContent(),`You ${won[0]} · Bot ${won[1]}`);
      if(viewport.width>670){
        await page.locator('#call').focus();await page.keyboard.press('f');
        assert.ok((await page.locator('#result').textContent()).includes('You fold'));
      } else {
        await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
        await checkLayout();
      }
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
