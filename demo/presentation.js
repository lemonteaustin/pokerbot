/* Read-only descriptions and winning-card selection. Never chooses game actions. */
(() => {
  'use strict';
  const ranks=['','','two','three','four','five','six','seven','eight','nine','ten','jack','queen','king','ace'];
  const plurals=['','','twos','threes','fours','fives','sixes','sevens','eights','nines','tens','jacks','queens','kings','aces'];
  const capitalize=text=>text[0].toUpperCase()+text.slice(1);
  function handName(cards) {
    const [kind,a,b]=PokerBot.score(cards);
    const descriptions=[`${ranks[a]} high`,`pair of ${plurals[a]}`,`two pair, ${plurals[a]} and ${plurals[b]}`,
      `three ${plurals[a]}`,`${ranks[a]}-high straight`,`${ranks[a]}-high flush`,
      `full house, ${plurals[a]} over ${plurals[b]}`,`four ${plurals[a]}`,
      a===14?'royal flush':`${ranks[a]}-high straight flush`];
    return capitalize(descriptions[kind]);
  }
  function bestFive(cards) {
    if(cards.length<5) return [];
    const target=PokerBot.score(cards);
    // Board cards come first, so board-only wins highlight the shared five.
    for(let a=0;a<cards.length-4;a++)for(let b=a+1;b<cards.length-3;b++)
      for(let c=b+1;c<cards.length-2;c++)for(let d=c+1;d<cards.length-1;d++)
        for(let e=d+1;e<cards.length;e++) {
          const hand=[cards[a],cards[b],cards[c],cards[d],cards[e]];
          if(PokerBot.compareScores(PokerBot.score(hand),target)===0)return hand;
        }
    return [];
  }
  function logText(text) {
    return text.replace(/\bYou (posts|calls|raises|bets|checks|folds|receives|wins)\b/g,
      (_,verb)=>`You ${verb.slice(0,-1)}`);
  }
  function resultText(game) {
    const r=game.resultDetails;
    if(!r)return '';
    const chips=n=>n.toLocaleString('en-US');
    if(r.reason==='fold')return `${r.winner===0?'You win':'Bot wins'} ${chips(r.pot)} chips · ${r.winner===0?'Bot folds':'You fold'}`;
    if(r.tie)return `Split pot · ${handName(game.board.concat(game.hole[0]))} · You ${chips(r.payouts[0])}, bot ${chips(r.payouts[1])}`;
    return `${r.winner===0?'You win':'Bot wins'} ${chips(r.pot)} chips · ${handName(game.board.concat(game.hole[r.winner]))}`;
  }
  globalThis.PokerPresentation={handName,bestFive,logText,resultText};
})();
