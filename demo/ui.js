/* Browser presentation. The engine and strategy also run without a DOM. */
(() => {
  'use strict';
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  const format = n => n.toLocaleString('en-US');
  const symbols = {c:'♣',d:'♦',h:'♥',s:'♠'};
  const suitNames = {c:'clubs',d:'diamonds',h:'hearts',s:'spades'};
  const rankNames = {T:'10',J:'Jack',Q:'Queen',K:'King',A:'Ace'};
  const BOT_DELAY_MS = 600;
  let game, bot, timer = null, generation = 0, reason, botAction;

  function cards(element, values, count, hidden = false) {
    element.replaceChildren();
    for (let i=0;i<count;i++) {
      const card = document.createElement('span');
      const value = values[i];
      card.className = 'card';
      if (hidden) {
        card.classList.add('back');
        card.setAttribute('aria-label','Face-down card');
      } else if (!value) {
        card.classList.add('empty');
        card.setAttribute('aria-label','Card not dealt yet');
      } else {
        if ('dh'.includes(value[1])) card.classList.add('red');
        const rank = document.createElement('span');
        rank.textContent = value[0] === 'T' ? '10' : value[0];
        const suit = document.createElement('span');
        suit.className = 'suit'; suit.textContent = symbols[value[1]];
        card.append(rank,suit);
        card.setAttribute('aria-label',`${rankNames[value[0]] || value[0]} of ${suitNames[value[1]]}`);
      }
      element.append(card);
    }
  }
  function setRaise(value) {
    const slider = $('raise-slider');
    slider.value = Math.max(Number(slider.min),Math.min(Number(slider.max),Math.trunc(value)));
    $('raise-value').textContent = format(Number(slider.value));
    $('raise').textContent = `Raise ${format(Number(slider.value))}`;
  }
  function showError(error) {
    clearTimeout(timer); timer = null;
    console.error(error);
    $('error').hidden = false;
    $('error').textContent = 'The hand could not continue. Use Play again to start a fresh match.';
    $('play-controls').hidden = true; $('next-controls').hidden = false;
    $('next-hand').textContent = 'Play again'; $('next-hand').dataset.restart = 'true';
    $('turn').textContent = 'Please start a new match';
  }
  function render() {
    $('hand-number').textContent = game.handNumber;
    $('blinds').textContent = `${format(game.smallBlind)} / ${format(game.bigBlind)}`;
    $('pot').textContent = format(game.pot);
    for (const [seat,label] of [[0,'human'],[1,'bot']]) {
      $(label+'-stack').textContent = format(game.stacks[seat]);
      $(label+'-dealer').hidden = game.button !== seat;
      $(label+'-seat').classList.toggle('active',!game.handOver && game.actor===seat);
      $(label+'-status').textContent = !game.handOver && game.stacks[seat]===0 ? 'All-in' : '';
    }
    cards($('human-cards'),game.hole[0],2);
    cards($('bot-cards'),game.hole[1],2,!(game.handOver && game.board.length===5 && game.showdown));
    cards($('board'),game.board,5);
    $('result').textContent = game.handOver ? game.lastResult : '';
    $('reason').textContent = reason;
    $('bot-action').textContent = botAction;
    const log=$('log');
    log.replaceChildren(...game.logs.slice(-70).map(text=>{
      const item=document.createElement('li'); item.textContent=text; return item;
    }));
    log.scrollTop = log.scrollHeight;
    $('play-controls').hidden = game.handOver;
    $('next-controls').hidden = !game.handOver;
    $('next-hand').dataset.restart = game.gameOver ? 'true' : 'false';
    $('next-hand').textContent = game.gameOver ? 'Play again' : 'Next hand';
    $('next-message').textContent = game.gameOver ? (game.stacks[0]===4000 ? 'You took all 4,000 chips. Well played!' : 'The bot takes this match. Try another?') : 'Ready for the next hand?';
    $('turn').textContent = game.gameOver ? (game.stacks[0]===4000 ? 'You win the match' : 'Bot wins the match') : game.handOver ? 'Hand complete' : game.actor===1 ? 'Bot is thinking…' : 'Your move';
    $('blind-hint').textContent = `Blinds rise in ${10-(game.handNumber-1)%10} hand${10-(game.handNumber-1)%10===1?'':'s'}`;
    const yourTurn = !game.handOver && game.actor===0;
    const state=yourTurn ? game.stateFor(0) : null;
    for(const action of ['fold','check','call','raise']) $(action).disabled = !state || !state.legal_actions.includes(action);
    $('call').textContent = state && state.amount_to_call ? `Call ${format(Math.min(game.stacks[0],state.amount_to_call))}` : 'Call';
    const canRaise = state && state.legal_actions.includes('raise');
    for (const id of ['raise-slider','half-pot','full-pot','all-in']) $(id).disabled = !canRaise;
    if(canRaise) {
      $('raise-slider').min=state.min_raise_to;
      $('raise-slider').max=state.max_raise_to;
      setRaise(state.min_raise_to);
    } else { $('raise-value').textContent='—'; $('raise').textContent='Raise'; }
  }
  function scheduleBot() {
    if(timer!==null || game.handOver || game.actor!==1) return;
    const turnGeneration=generation;
    timer=setTimeout(()=>{
      timer=null;
      if(turnGeneration!==generation || game.handOver || game.actor!==1) return;
      try {
        const state=game.stateFor(1);
        const action=bot.getAction(state);
        reason=bot.reason || 'Choosing a legal action based on hand strength, stack depth, and the price to continue.';
        botAction=typeof action==='string' ? `Bot ${action==='call'?'calls':action==='check'?'checks':'folds'}` : `Bot raises to ${format(action.amount)}`;
        game.act(1,action);
        render(); scheduleBot();
      } catch(error) {showError(error);}
    },BOT_DELAY_MS);
  }
  function act(action) {
    if(game.handOver || game.actor!==0) return;
    try {game.act(0,action);render();scheduleBot();} catch(error) {showError(error);}
  }
  function start() {
    generation++;
    clearTimeout(timer);timer=null;
    game=new PokerGame();bot=new PokerBot.Bot();
    reason='Take your seat. After each move, I’ll explain the bot’s decision here.';
    botAction='Waiting for the first move';
    $('error').hidden=true;
    render();scheduleBot();
  }
  for(const action of ['fold','check','call']) $(action).addEventListener('click',()=>act(action));
  $('raise').addEventListener('click',()=>act({action:'raise',amount:Number($('raise-slider').value)}));
  $('raise-slider').addEventListener('input',event=>setRaise(Number(event.target.value)));
  for(const [id,fraction] of [['half-pot',.5],['full-pot',1]]) $(id).addEventListener('click',()=>{
    if(game.actor!==0 || game.handOver) return;
    const state=game.stateFor(0),street=state.max_raise_to-game.stacks[0];
    setRaise(street+state.amount_to_call+Math.floor((game.pot+state.amount_to_call)*fraction));
  });
  $('all-in').addEventListener('click',()=>setRaise(Number($('raise-slider').max)));
  $('next-hand').addEventListener('click',()=>{
    if($('next-hand').dataset.restart==='true') return start();
    if(!game.handOver) return;
    try {game.newHand();render();scheduleBot();} catch(error) {showError(error);}
  });
  start();
})();
