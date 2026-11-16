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
  const {handName,bestFive,logText,resultText}=PokerPresentation;
  const wins=[0,0];
  let game, bot, timer = null, generation = 0, reason, botAction, matchRecorded=false;

  function cards(element, values, count, hidden = false, winning=new Set()) {
    for (let i=0;i<count;i++) {
      let card=element.children[i];
      const value = values[i];
      const key=`${generation}:${game.handNumber}:${hidden?'back':value||'empty'}`;
      if(card && card.dataset.key===key) {
        card.classList.toggle('winning',!hidden && winning.has(value));
        continue;
      }
      const flipping=card && card.classList.contains('back') && !hidden &&
        card.dataset.key.startsWith(`${generation}:${game.handNumber}:`);
      const previous=card;
      card=document.createElement('span');
      if(previous)element.replaceChild(card,previous);else element.append(card);
      card.className = 'card';
      card.dataset.key=key;
      card.dataset.card=hidden?'':value||'';
      card.style.setProperty('--deal-delay',`${i*35}ms`);
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
      if(hidden || value)card.classList.add(flipping?'flip':'deal');
      card.classList.toggle('winning',!hidden && winning.has(value));
    }
  }
  function buttonLabel(id,text,key) {
    const badge=document.createElement('kbd');badge.textContent=key;badge.setAttribute('aria-hidden','true');
    $(id).replaceChildren(document.createTextNode(text+' '),badge);
  }
  function setRaise(value) {
    const slider = $('raise-slider');
    slider.value = Math.max(Number(slider.min),Math.min(Number(slider.max),Math.trunc(value)));
    $('raise-value').textContent = format(Number(slider.value));
    buttonLabel('raise',`Raise to ${format(Number(slider.value))}`,'R');
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
    const bets=game.handOver?[0,0]:game.contributions;
    // The engine's pot includes current bets; show them separately until collected.
    $('pot').textContent = format(game.pot-bets[0]-bets[1]);
    for (const [seat,label] of [[0,'human'],[1,'bot']]) {
      $(label+'-stack').textContent = format(game.stacks[seat]);
      $(label+'-bb').textContent = `${Number((game.stacks[seat]/game.bigBlind).toFixed(1))} BB`;
      $(label+'-blind').textContent = game.button===seat?'Small blind':'Big blind';
      $(label+'-bet-amount').textContent=format(bets[seat]);
      $(label+'-bet').classList.toggle('zero',bets[seat]===0);
      $(label+'-bet').setAttribute('aria-label',`${seat===0?'Your':'Bot'} current bet: ${bets[seat]}`);
      $(label+'-dealer').hidden = game.button !== seat;
      $(label+'-seat').classList.toggle('active',!game.handOver && game.actor===seat);
      $(label+'-status').textContent = !game.handOver && game.stacks[seat]===0 ? 'All-in' : '';
    }
    const winning=new Set();
    if(game.handOver && game.showdown) {
      for(const seat of game.tie?[0,1]:[game.winner]) {
        for(const card of bestFive(game.board.concat(game.hole[seat])))winning.add(card);
      }
    }
    cards($('human-cards'),game.hole[0],2,false,winning);
    cards($('bot-cards'),game.hole[1],2,!(game.handOver && game.showdown),winning);
    cards($('board'),game.board,5,false,winning);
    $('human-hand').textContent=handName(game.hole[0].concat(game.board));
    $('result').textContent = game.handOver ? resultText(game) : '';
    $('reason').textContent = reason;
    $('bot-action').textContent = botAction;
    const log=$('log');
    log.replaceChildren(...game.logs.slice(-70).map(text=>{
      const item=document.createElement('li'); item.textContent=logText(text); return item;
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
    buttonLabel('call',state && state.amount_to_call ? `Call ${format(Math.min(game.stacks[0],state.amount_to_call))}` : 'Call','C');
    const canRaise = state && state.legal_actions.includes('raise');
    for (const id of ['raise-slider','half-pot','full-pot','all-in']) $(id).disabled = !canRaise;
    if(canRaise) {
      $('raise-slider').min=state.min_raise_to;
      $('raise-slider').max=state.max_raise_to;
      setRaise(state.min_raise_to);
    } else { $('raise-value').textContent='—'; buttonLabel('raise','Raise to —','R'); }
    if(game.gameOver && !matchRecorded) {
      matchRecorded=true;wins[game.stacks[0]===4000?0:1]++;
      $('match-title').textContent=game.stacks[0]===4000?'You win!':'Bot wins this time';
      $('match-summary').textContent=`${game.handNumber} hand${game.handNumber===1?'':'s'} played · ${game.stacks[0]===4000?'You collected':'The bot collected'} all 4,000 chips.`;
      $('match-score').textContent=`Games won: You ${wins[0]} · Bot ${wins[1]}`;
      $('match-dialog').showModal();
    }
    $('scoreboard').textContent=`You ${wins[0]} · Bot ${wins[1]}`;
  }
  function applyAction(seat,action) {
    const street=game.street, state=game.stateFor(seat);
    const amounts=game.contributions.slice();
    const positions=['human-bet','bot-bet'].map(id=>$(id).getBoundingClientRect());
    const kind=typeof action==='string'?action:action.action;
    if(kind==='call')amounts[seat]+=Math.min(game.stacks[seat],state.amount_to_call);
    if(kind==='raise')amounts[seat]=action.amount;
    game.act(seat,action);
    const collected=game.handOver || game.street!==street;
    if(game.handOver)amounts.forEach((amount,index)=>{
      amounts[index]=Math.max(0,amount-(game.resultDetails.refunds[index]||0));
    });
    render();
    if(collected && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const pot=$('pot').getBoundingClientRect();
      positions.forEach((rect,index)=>{
        if(!amounts[index])return;
        const flight=document.createElement('span');flight.className='chip-flight';flight.setAttribute('aria-hidden','true');
        const chip=document.createElement('span');chip.className='chips';flight.append(chip,document.createTextNode(format(amounts[index])));
        flight.style.left=`${rect.left}px`;flight.style.top=`${rect.top}px`;
        flight.style.setProperty('--travel-x',`${pot.left-rect.left}px`);
        flight.style.setProperty('--travel-y',`${pot.top-rect.top}px`);
        document.body.append(flight);setTimeout(()=>flight.remove(),350);
      });
    }
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
        botAction=typeof action==='string' ? `Bot ${action==='call'?'calls':action==='check'?'checks':'folds'}` : `Bot ${Math.max(...Object.values(state.street_contributions))===0?'bets':'raises to'} ${format(action.amount)}`;
        applyAction(1,action);
        scheduleBot();
      } catch(error) {showError(error);}
    },BOT_DELAY_MS);
  }
  function act(action) {
    if(game.handOver || game.actor!==0) return;
    try {applyAction(0,action);scheduleBot();} catch(error) {showError(error);}
  }
  function start() {
    generation++;
    clearTimeout(timer);timer=null;
    $('match-dialog').close();matchRecorded=false;
    document.querySelectorAll('.chip-flight').forEach(node=>node.remove());
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
  $('play-again').addEventListener('click',start);
  $('view-hand').addEventListener('click',()=>$('match-dialog').close());
  document.addEventListener('keydown',event=>{
    if(event.repeat || event.altKey || event.ctrlKey || event.metaKey ||
      !matchMedia('(min-width: 671px)').matches || $('match-dialog').open ||
      event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
    const key=event.key.toLowerCase();
    const id=key==='f'?'fold':key==='r'?'raise':key==='c'?($('check').disabled?'call':'check'):null;
    if(id && !$(id).disabled && !game.handOver && game.actor===0){event.preventDefault();$(id).click();}
  });
  $('next-hand').addEventListener('click',()=>{
    if($('next-hand').dataset.restart==='true') return start();
    if(!game.handOver) return;
    try {game.newHand();render();scheduleBot();} catch(error) {showError(error);}
  });
  new ResizeObserver(entries=>{
    document.documentElement.style.setProperty('--dock-height',`${Math.ceil(entries[0].target.getBoundingClientRect().height)}px`);
  }).observe(document.querySelector('.controls'));
  start();
})();
