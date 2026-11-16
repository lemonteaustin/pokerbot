#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const page=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
vm.runInThisContext(page.match(/<script id="poker-code">([\s\S]*?)<\/script>/)[1]);
const {handName,bestFive,logText,resultText}=PokerPresentation;
const cases=[
  ['Jh 2s','Jack high'],['Jh Jc','Pair of jacks'],
  ['Ah Ad Kh Kc 2d 3c 4s','Two pair, aces and kings'],
  ['Ah Ad Ac 7h 2d','Three aces'],['As 2c 3d 4h 5s','Five-high straight'],
  ['Jh 9h 7h 5h 2h','Jack-high flush'],['Jh Jc Js 2c 2d','Full house, jacks over twos'],
  ['Jh Jc Js Jd 2c','Four jacks'],['9s 8s 7s 6s 5s','Nine-high straight flush'],
  ['As Ks Qs Js Ts','Royal flush']
];
for(const [text,name] of cases)assert.equal(handName(text.split(' ')),name);
const board=['As','Ks','Qs','Js','Ts'];assert.deepEqual(bestFive(board.concat(['2h','3h'])),board);
assert.deepEqual(bestFive(['Jh','2s']),[]);
for(const cards of [
  'Ah Ad 7s 3s 2h Ac Kd', 'As 2c 3d 4h 8s 5s Kh', 'Jh Jc Js Qd Qs Qc 9s',
  'As 8s 7s 4s 2h Ks 3s','Ah Ad Kh Kd Qh Qd Js'
]) {
  const all=cards.split(' '),five=bestFive(all);
  assert.equal(five.length,5);assert.equal(new Set(five).size,5);
  assert.ok(five.every(c=>all.includes(c)));assert.equal(PokerBot.compareScores(PokerBot.score(five),PokerBot.score(all)),0);
}
for(const verb of ['posts','calls','raises','bets','checks','folds','receives','wins']){
  assert.equal(logText(`You ${verb} 10.`),`You ${verb.slice(0,-1)} 10.`);
  assert.equal(logText(`Bot ${verb} 10.`),`Bot ${verb} 10.`);
}
assert.equal(resultText({resultDetails:{reason:'fold',winner:0,pot:40}}),'You win 40 chips · Bot folds');
assert.equal(resultText({board,hole:[['2h','3h'],['4c','5c']],resultDetails:{tie:true,payouts:[40,40],pot:80,reason:'showdown'}}),'Split pot · Royal flush · You 40, bot 40');
console.log('Presentation checks passed: hand names, best five, tied board, fold result, log grammar.');
