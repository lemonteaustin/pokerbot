#!/usr/bin/env node
// Exercise the actual standalone artifact, not a second engine implementation.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const crypto = require('node:crypto');
const html = fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
vm.runInThisContext(html.match(/<script id="poker-code">([\s\S]*?)<\/script>/)[1]);
const rngFor = seed => () => ((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
const fresh = seed => new PokerGame({rng:rngFor(seed)});
let checks=0, decisions=0, hands=0, showdowns=0, ties=0;
function invariant(g) {
  assert.equal(g.stacks[0]+g.stacks[1]+g.pot,4000);
  assert.ok([...g.stacks,g.pot,...g.contributions,...g.totalContributions].every(n=>Number.isSafeInteger(n)&&n>=0));
  const cards=[...g.hole.flat(),...g.board,...g._burned,...g._deck];
  assert.equal(cards.length,52); assert.equal(new Set(cards).size,52);
  if(!g.handOver) {
    assert.equal(g.pot,g.totalContributions[0]+g.totalContributions[1]);
    assert.ok([0,1].includes(g.actor)); assert.ok(g.stacks[g.actor]>0);
    const state=g.stateFor(g.actor);
    assert.ok(state.legal_actions.length>=2);
    assert.equal(state.legal_actions.includes('check'),state.amount_to_call===0);
    assert.equal(state.legal_actions.includes('call'),state.amount_to_call>0);
    assert.ok(!state.legal_actions.includes('raise') || g.stacks[1-g.actor]>0);
    for(let i=0;i<2;i++) assert.equal(g.stacks[i]+g.totalContributions[i],g.startingStacks[i]);
  } else {
    assert.equal(g.actor,null); assert.equal(g.pot,0);
    if(g.showdown) assert.equal(g.board.length,5);
    if(g.gameOver) assert.ok(g.stacks.includes(4000)&&g.stacks.includes(0));
  }
  checks++;
}
// Initial action order, blind option, and alternating button.
let g=fresh(1);
assert.equal(g.actor,0); assert.deepEqual(g.stacks,[1990,1980]);
assert.equal(g.stateFor(0).position,'small_blind');
g.act(0,'call'); assert.equal(g.actor,1); assert.ok(g.stateFor(1).legal_actions.includes('raise'));
g.act(1,'check'); assert.equal(g.street,'flop'); assert.equal(g.actor,1); assert.equal(g.board.length,3);
g.act(1,'check'); assert.equal(g.actor,0); g.act(0,'check'); assert.equal(g.street,'turn'); assert.equal(g.actor,1);
g.act(1,'fold'); assert.equal(g.showdown,false); g.newHand(); assert.equal(g.button,1); assert.equal(g.actor,1);
// Invalid actions must fail before they touch chips, history, or the turn.
g=fresh(4);
for(const [seat,action] of [[1,'call'],[0,'check'],[0,{action:'raise',amount:39}],
  [0,{action:'raise',amount:2001}],[0,{action:'raise',amount:40.5}],[0,{action:'raise',amount:NaN}],[0,'dance']]) {
  const before=JSON.stringify(g);assert.throws(()=>g.act(seat,action));assert.equal(JSON.stringify(g),before);
}
// State snapshots cannot reveal the opponent's hole cards or mutate the engine.
const snapshot=g.stateFor(0); snapshot.stacks.my_bot=0;snapshot.hole_cards[0]='??';
assert.equal(g.stacks[0],1990);assert.ok(!g.hole[0].includes('??'));assert.equal(snapshot.opponent_cards,undefined);
// Minimum raises after an opening raise and a full re-raise.
g.act(0,{action:'raise',amount:60});assert.equal(g.stateFor(1).min_raise_to,100);
g.act(1,{action:'raise',amount:150});assert.equal(g.stateFor(0).min_raise_to,240);
// Unequal all-ins: the excess belongs back to the covering stack, not a side pot.
g=fresh(2);g.handOver=true;g.stacks=[3500,500];g.newHand();
const rich=0; if(g.actor!==rich) g.act(g.actor,'call');
g.act(rich,{action:'raise',amount:g.stateFor(rich).max_raise_to});
assert.deepEqual(g.stateFor(1).legal_actions,['fold','call']);g.act(1,'call');
assert.equal(g.resultDetails.pot,1000);assert.equal(g.resultDetails.refunds[0],3000);invariant(g);
// A tiny blind stack runs out without asking an all-in player to act.
g=fresh(3);g.handOver=true;g.stacks=[3995,5];g.newHand();
assert.ok(g.handOver);assert.ok(g.showdown);assert.equal(g.resultDetails.pot,10);invariant(g);
// An all-in under-raise is allowed, but there is no further raise into an all-in.
g=fresh(5);g.handOver=true;g.stacks=[3970,30];g.newHand();
assert.equal(g.actor,1);assert.equal(g.stateFor(1).min_raise_to,30);
g.act(1,{action:'raise',amount:30});assert.deepEqual(g.stateFor(0).legal_actions,['fold','call']);g.act(0,'call');invariant(g);
// Blinds increase at hand 11, not at hand 10. Fold-only play lasts beyond that.
g=fresh(9);while(g.handNumber<11){g.act(g.actor,'fold');g.newHand();}
assert.equal(g.bigBlind,40);assert.equal(g.smallBlind,20);
// Independent known scores, including ace-low straight and board-only ties.
const scoreTests=[
  ['As Ks Qs Js Ts 2d 3h',[8,14]],['As 2s 3s 4s 5s Kh Kd',[8,5]],
  ['Ah Ad Ac As Kd 2d 3d',[7,14,13]],['Ah Ad Ac Kh Kd Ks 2d',[6,14,13]],
  ['Ah Jh 9h 6h 3h Kd Qd',[5,14,11,9,6,3]],['As 2d 3h 4c 5c Kd Qd',[4,5]],
  ['Ah Ad Ac Kh Qd 2s 3s',[3,14,13,12]],['Ah Ad Kh Kd Qd 2s 3s',[2,14,13,12]],
  ['Ah Ad Kh Qd Jd 2s 3s',[1,14,13,12,11]],['Ah Kd Qh Jd 9c 2s 3s',[0,14,13,12,11,9]]
];
for(const [cards,score] of scoreTests) assert.deepEqual(PokerBot.score(cards.split(' ')),score);
assert.equal(PokerBot.compareScores(PokerBot.score('As Ks Qs Js Ts 2d 3h'.split(' ')),PokerBot.score('As Ks Qs Js Ts 4d 5h'.split(' '))),0);
g=fresh(7);g.button=0;assert.deepEqual(g._payouts(41,null),[20,21]);
// A scripted royal-flush board splits the pot at an actual showdown.
g=fresh(8);g.hole=[['2c','3d'],['4c','5d']];g._deck=['Ts','9d','Js','8d','Qs','Ks','As','7d'];
g.act(0,{action:'raise',amount:2000});g.act(1,'call');
assert.ok(g.tie);assert.deepEqual(g.stacks,[2000,2000]);assert.equal(g.gameOver,false);

// Run 2,000 complete matches through six realistic visitor policies versus v7.
const policies=['passive','random','push','fold','small_raise','bot'];
const wins=[0,0];let maxHands=0;
for(let seed=1;seed<=2000;seed++) {
  const rng=rngFor(seed*997), policy=policies[(seed-1)%policies.length];
  const bots=[new PokerBot.Bot(),new PokerBot.Bot()];g=new PokerGame({rng});let steps=0;
  while(!g.gameOver) {
    invariant(g);
    if(g.handOver){hands++;showdowns+=Number(g.showdown);ties+=Number(g.tie);g.newHand();continue;}
    const seat=g.actor,s=g.stateFor(seat),legal=s.legal_actions;
    let action;
    if(seat===1 || policy==='bot') action=bots[seat].getAction(s);
    else if(policy==='fold') action=legal.includes('check')?'check':'fold';
    else if(policy==='passive') action=legal.includes('check')?'check':'call';
    else if(policy==='push') action=legal.includes('raise')?{action:'raise',amount:s.max_raise_to}:legal.includes('call')?'call':'check';
    else if(policy==='small_raise') action=legal.includes('raise')&&rng()<.45?{action:'raise',amount:s.min_raise_to}:legal.includes('check')?'check':'call';
    else {
      action=legal[Math.floor(rng()*legal.length)];
      if(action==='raise')action={action,amount:s.min_raise_to+Math.floor(rng()*(s.max_raise_to-s.min_raise_to+1))};
    }
    if(seat===1) assert.ok(bots[1].reason && !/failed validation|not a plain object|processed safely|outside the legal actions/.test(bots[1].reason));
    g.act(seat,action);decisions++;
    if(++steps>50000 || g.handNumber>500) throw new Error(`Match failed to finish, seed ${seed}`);
  }
  invariant(g);hands++;showdowns+=Number(g.showdown);ties+=Number(g.tie);
  wins[g.stacks[0]===4000?0:1]++;maxHands=Math.max(maxHands,g.handNumber);
}
const report={passed:true,matches:2000,policies,decisions,hands,showdowns,ties,maxHands,invariantChecks:checks,
  illegalActions:0,errors:0,wins,artifact_sha256:crypto.createHash('sha256').update(html).digest('hex')};
fs.mkdirSync(path.join(__dirname,'test_results'),{recursive:true});
fs.writeFileSync(path.join(__dirname,'test_results','engine.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
