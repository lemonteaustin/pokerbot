/* Heads-up no-limit Hold'em. Load bot.js before a showdown; no DOM or imports.
 * Public cards are rank+suit strings. Raises are TOTAL street contributions.
 * stateFor(seat) is a detached, seat-relative Python-compatible bot state.
 */
(function (root) {
  'use strict';

  const STREETS = ['preflop', 'flop', 'turn', 'river'];
  const label = seat => seat === 0 ? 'You' : 'Bot';
  const compare = (a, b) => {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const difference = (a[i] || 0) - (b[i] || 0);
      if (difference) return Math.sign(difference);
    }
    return 0;
  };

  class PokerGame {
    constructor({ rng = Math.random } = {}) {
      if (typeof rng !== 'function') throw new TypeError('rng must be a function');
      this.rng = rng;
      this.stacks = [2000, 2000];
      this.button = 0;
      this.handNumber = 0;
      this.handOver = true;
      this.gameOver = false;
      this.winner = null;
      this.tie = false;
      this.lastResult = '';
      this.resultDetails = null;
      this._history = [];
      this.newHand();
    }

    newHand() {
      if (this.gameOver) throw new Error('The match is over');
      if (!this.handOver) throw new Error('The current hand is still in progress');
      // Shuffle before changing any hand state, including when rng is invalid.
      const deck = [];
      for (const rank of '23456789TJQKA') {
        for (const suit of 'cdhs') deck.push(rank + suit);
      }
      for (let i = deck.length - 1; i > 0; i--) {
        const random = this.rng();
        if (!Number.isFinite(random) || random < 0 || random >= 1) {
          throw new RangeError('rng must return a number in [0, 1)');
        }
        const j = Math.floor(random * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
      }
      if (this.handNumber) this.button = 1 - this.button;
      this.handNumber++;
      this.bigBlind = Math.min(4000, 20 * 2 ** Math.min(8, Math.floor((this.handNumber - 1) / 10)));
      this.smallBlind = this.bigBlind / 2;
      this.hole = [[], []];
      this.board = [];
      this.pot = 0;
      this.street = 'preflop';
      this.contributions = [0, 0];
      this.totalContributions = [0, 0];
      this.startingStacks = this.stacks.slice();
      this.handOver = false;
      this.winner = null;
      this.tie = false;
      this.lastResult = '';
      this.resultDetails = null;
      this.showdown = false;
      this.logs = [`Hand ${this.handNumber} — blinds ${this.smallBlind}/${this.bigBlind}.`];
      this._deck = deck;
      this._burned = [];
      this._folded = [false, false];
      this._refunds = [0, 0];
      this._unopened = true;
      this._lastRaiser = null;
      this._actedAt = [null, null];
      this._lastFullRaise = this.bigBlind;
      // The big blind is clockwise from the button and receives the first card.
      for (let round = 0; round < 2; round++) {
        for (const seat of [1 - this.button, this.button]) this.hole[seat].push(this._deck.pop());
      }
      for (const [seat, blind] of [[this.button, this.smallBlind], [1 - this.button, this.bigBlind]]) {
        const paid = this._post(seat, blind);
        this.logs.push(`${label(seat)} posts ${paid}${this.stacks[seat] === 0 ? ' (all-in)' : ''}.`);
      }
      this._currentBet = Math.max(...this.contributions);
      this._pending = new Set([0, 1].filter(seat => this.stacks[seat] > 0));
      this._proceed(this.button);
      return this;
    }

    stateFor(seat) {
      this._validateSeat(seat);
      const other = 1 - seat;
      const name = index => index === seat ? 'my_bot' : 'opponent';
      const relative = values => ({ my_bot: values[seat], opponent: values[other] });
      const cost = Math.max(0, this._currentBet - this.contributions[seat]);
      const maximum = this.contributions[seat] + this.stacks[seat];
      const minimum = Math.min(this._currentBet + this._lastFullRaise, maximum);
      const legal = [];
      if (!this.handOver && this.actor === seat) {
        legal.push('fold', cost === 0 ? 'check' : 'call');
        const reopened = this._actedAt[seat] === null ||
          this._currentBet - this._actedAt[seat] >= this._lastFullRaise;
        if (reopened && maximum > this._currentBet && this.stacks[other] > 0) legal.push('raise');
      }
      return {
        hole_cards: this.hole[seat].slice(),
        board: this.board.slice(),
        pot: this.pot,
        stacks: relative(this.stacks),
        blinds: { small: this.smallBlind, big: this.bigBlind },
        amount_to_call: cost,
        legal_actions: legal,
        min_raise_to: minimum,
        max_raise_to: maximum,
        hand_number: this.handNumber,
        position: seat === this.button ? 'small_blind' : 'big_blind',
        folded_to_me: this.street === 'preflop' && this._unopened,
        players_remaining: 2,
        active_players: [0, 1].filter(index => !this._folded[index]).map(name),
        street_contributions: relative(this.contributions),
        total_contributions: relative(this.totalContributions),
        starting_stacks: relative(this.startingStacks),
        self_name: 'my_bot',
        players_left_to_act: [...this._pending].filter(index => index !== seat).length,
        last_raiser: this._lastRaiser === null ? null : name(this._lastRaiser),
        opponent_all_in: this.stacks[other] === 0 && !this._folded[other],
        action_history: this._history.map(entry => [entry[0], name(entry[1]), ...entry.slice(2)]),
        payouts: [1, 0],
        max_hands: null,
        street: this.street
      };
    }

    act(seat, response) {
      this._validateSeat(seat);
      if (this.handOver) throw new Error('The hand is over');
      if (seat !== this.actor) throw new Error('It is not this seat\'s turn');
      const action = typeof response === 'string' ? response : response && response.action;
      const state = this.stateFor(seat);
      if (!state.legal_actions.includes(action)) throw new Error(`Illegal action: ${String(action)}`);
      const amount = response && typeof response === 'object' ? response.amount : undefined;
      if (action === 'raise' && (!Number.isSafeInteger(amount) ||
          amount < state.min_raise_to || amount > state.max_raise_to)) {
        throw new RangeError(`Raise total must be an integer from ${state.min_raise_to} to ${state.max_raise_to}`);
      }
      // All validation precedes mutation, including history and log updates.
      const previousBet = this._currentBet;
      if (this.street === 'preflop') {
        this._history.push([this.handNumber, seat, action,
          action === 'raise' && amount === state.max_raise_to, previousBet > this.bigBlind]);
        this._history = this._history.slice(-96);
        if (action !== 'fold') this._unopened = false;
      }
      this._pending.delete(seat);
      if (action === 'fold') {
        this._folded[seat] = true;
        this.logs.push(`${label(seat)} folds.`);
        this._refundUncalled();
        this._award(1 - seat, 'fold', null);
        return this;
      }
      if (action === 'raise') {
        this._post(seat, amount - this.contributions[seat]);
        this._currentBet = amount;
        if (amount - previousBet >= this._lastFullRaise) this._lastFullRaise = amount - previousBet;
        this._lastRaiser = seat;
        this._pending = new Set([1 - seat].filter(index => this.stacks[index] > 0));
        this.logs.push(`${label(seat)} ${previousBet === 0 ? 'bets' : 'raises to'} ${amount}${this.stacks[seat] === 0 ? ' (all-in)' : ''}.`);
      } else if (action === 'call') {
        const paid = this._post(seat, state.amount_to_call);
        this.logs.push(`${label(seat)} calls ${paid}${this.stacks[seat] === 0 ? ' (all-in)' : ''}.`);
      } else {
        this.logs.push(`${label(seat)} checks.`);
      }
      this._actedAt[seat] = this._currentBet;
      this._proceed(1 - seat);
      return this;
    }

    _validateSeat(seat) {
      if (seat !== 0 && seat !== 1) throw new RangeError('Seat must be 0 or 1');
    }

    _post(seat, amount) {
      const paid = Math.min(amount, this.stacks[seat]);
      this.stacks[seat] -= paid;
      this.contributions[seat] += paid;
      this.totalContributions[seat] += paid;
      this.pot += paid;
      return paid;
    }

    _proceed(next) {
      const able = [0, 1].filter(seat => this.stacks[seat] > 0);
      if (able.length < 2) {
        // A lone player only gets a decision when facing an outstanding bet.
        const seat = able[0];
        if (seat !== undefined && this.contributions[seat] < this.contributions[1 - seat]) {
          this._pending = new Set([seat]);
          this.actor = seat;
          return;
        }
        this._refundUncalled();
        while (this.board.length < 5) this._dealStreet();
        this._showdown();
        return;
      }
      if (this._pending.size) {
        this.actor = this._pending.has(next) ? next : 1 - next;
        return;
      }
      if (this.street === 'river') {
        this._showdown();
      } else {
        this._dealStreet();
        this._pending = new Set([0, 1]);
        this.actor = 1 - this.button;
      }
    }

    _dealStreet() {
      this.street = STREETS[STREETS.indexOf(this.street) + 1];
      this.contributions = [0, 0];
      this._currentBet = 0;
      this._lastFullRaise = this.bigBlind;
      this._actedAt = [null, null];
      this._burned.push(this._deck.pop());
      const count = this.street === 'flop' ? 3 : 1;
      for (let i = 0; i < count; i++) this.board.push(this._deck.pop());
      // Even public board cards are omitted from the log until showdown.
      this.logs.push(`${this.street[0].toUpperCase() + this.street.slice(1)}.`);
    }

    _refundUncalled() {
      const difference = this.totalContributions[0] - this.totalContributions[1];
      this._refunds = [0, 0];
      if (!difference) return;
      const seat = difference > 0 ? 0 : 1;
      const amount = Math.abs(difference);
      this.stacks[seat] += amount;
      this.contributions[seat] -= amount;
      this.totalContributions[seat] -= amount;
      this.pot -= amount;
      this._refunds[seat] = amount;
      this.logs.push(`${label(seat)} receives ${amount} uncalled chips back.`);
    }

    _showdown() {
      if (!root.PokerBot || typeof root.PokerBot.score !== 'function') {
        throw new Error('Load PokerBot.score before playing a showdown');
      }
      const scores = this.hole.map(cards => root.PokerBot.score(cards.concat(this.board)));
      if (scores.some(score => !Array.isArray(score) || !score.length || score.some(n => !Number.isFinite(n)))) {
        throw new TypeError('PokerBot.score must return a numeric score array');
      }
      const result = compare(scores[0], scores[1]);
      this.showdown = true;
      this.logs.push(`Showdown — board ${this.board.join(' ')}; You: ${this.hole[0].join(' ')}; Bot: ${this.hole[1].join(' ')}.`);
      this._award(result > 0 ? 0 : result < 0 ? 1 : null, 'showdown', scores);
    }

    _payouts(pot, winner) {
      if (winner !== null) return winner === 0 ? [pot, 0] : [0, pot];
      const payouts = [Math.floor(pot / 2), Math.floor(pot / 2)];
      payouts[1 - this.button] += pot % 2; // First seat clockwise from button.
      return payouts;
    }

    _award(winner, reason, scores) {
      const pot = this.pot;
      const payouts = this._payouts(pot, winner);
      for (let seat = 0; seat < 2; seat++) this.stacks[seat] += payouts[seat];
      this.winner = winner;
      this.tie = winner === null;
      this.handOver = true;
      this.gameOver = this.stacks.some(stack => stack === 0);
      this.actor = null;
      this._pending.clear();
      this.pot = 0;
      this.resultDetails = {
        handNumber: this.handNumber, reason, winner, tie: this.tie, pot,
        payouts, refunds: (this._refunds || [0, 0]).slice(),
        scores: scores && scores.map(score => score.slice())
      };
      this.lastResult = this.tie ? `Split pot: ${payouts[0]} / ${payouts[1]}.` : `${label(winner)} wins ${pot}.`;
      this.logs.push(this.lastResult);
      if (this.gameOver) this.logs.push(`${label(this.stacks[0] > 0 ? 0 : 1)} wins the match.`);
    }
  }

  root.PokerGame = PokerGame;
})(globalThis);
