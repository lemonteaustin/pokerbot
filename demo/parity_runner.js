#!/usr/bin/env node
// JSON stdin: {states, score_cases} or {collect_engine: 50, seed: 7}.
// Evaluate the shipped inline bundle without a DOM: UI code must guard document.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const hash = text => crypto.createHash('sha256').update(text).digest('hex');

function load() {
  const page = path.join(__dirname, 'index.html');
  let filename, code, artifact;
  if (fs.existsSync(page)) {
    filename = page;
    artifact = fs.readFileSync(page, 'utf8');
    const scripts = [...artifact.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
    const matches = scripts.filter(m => /\bid\s*=\s*(?:"poker-code"|'poker-code'|poker-code(?=\s|$))/i.test(m[1]));
    if (matches.length !== 1) throw new Error('index.html must contain exactly one inline <script id="poker-code">');
    code = matches[0][2];
  } else {
    filename = path.join(__dirname, 'bot.js');
    artifact = code = fs.readFileSync(filename, 'utf8');
  }
  const context = vm.createContext({console: {
    log: (...args) => console.error(...args),
    warn: (...args) => console.error(...args),
    error: (...args) => console.error(...args),
  }});
  try {
    vm.runInContext(code, context, {filename, timeout: 10000});
  } catch (error) {
    throw new Error(`${path.basename(filename)} failed without document; UI must guard typeof document: ${error.message}`);
  }
  if (typeof context.PokerBot?.Bot !== 'function') throw new Error('Missing globalThis.PokerBot.Bot');
  return {context, source: {
    artifact: path.basename(filename), artifact_sha256: hash(artifact),
    code_sha256: hash(code), final_artifact: filename === page,
    document_undefined: vm.runInContext('typeof document === "undefined"', context),
  }};
}

function collectEngine(context, count, seed, source) {
  if (!context.PokerGame && !source.final_artifact) {
    const engine = path.join(__dirname, 'engine.js');
    if (fs.existsSync(engine)) {
      const code = fs.readFileSync(engine, 'utf8');
      vm.runInContext(code, context, {filename: engine, timeout: 10000});
      source.engine_sha256 = hash(code);
    }
  }
  if (!context.PokerGame) return {states: [], unavailable: 'PokerGame is not available', source};
  const Game = typeof context.PokerGame === 'function' ? context.PokerGame : context.PokerGame.Game;
  if (typeof Game !== 'function') throw new Error('PokerGame constructor is not exported');
  let value = seed >>> 0;
  const rng = () => ((value = (Math.imul(value, 1664525) + 1013904223) >>> 0) / 4294967296);
  let game = new Game({rng});
  const states = [];
  for (let step = 0; states.length < count && step < count * 100; step++) {
    if (game.gameOver) game = new Game({rng});
    if (game.handOver || game.actor == null || !game.hole?.length) game.newHand();
    if (game.handOver || game.gameOver || game.actor == null) continue;
    const seat = game.actor;
    const state = game.stateFor(seat);
    states.push(JSON.parse(JSON.stringify(state)));
    const legal = state.legal_actions;
    const roll = rng();
    let action = legal.includes('check') ? 'check' : 'call';
    if (legal.includes('raise') && roll < 0.18) {
      const low = state.min_raise_to, high = state.max_raise_to;
      const target = roll < 0.025 ? high : Math.max(low, Math.min(high, low + Math.floor(state.pot / 2)));
      action = {action: 'raise', amount: target};
    } else if (!legal.includes('check') && roll > 0.94) action = 'fold';
    game.act(seat, action);
  }
  if (states.length !== count) throw new Error(`Engine produced only ${states.length}/${count} decisions`);
  return {states, source};
}

function run(input) {
  const {context, source} = load();
  if (input.collect_engine) return collectEngine(context, input.collect_engine, input.seed || 1, source);
  // Parse inside the VM so plain-object validation sees the browser's own realm.
  context.serializedInput = JSON.stringify(input);
  input = vm.runInContext('JSON.parse(serializedInput)', context);
  delete context.serializedInput;
  // One instance for the entire ordered sequence; never reset its private RNG.
  const bot = new context.PokerBot.Bot();
  const actions = input.states.map(state => {
    try {
      const action = bot.getAction(state);
      return {action: action ?? null, reason: typeof bot.reason === 'string' ? bot.reason : null};
    } catch (error) {
      return {action: null, error: String(error.stack || error)};
    }
  });
  const scores = (input.score_cases || []).map(cards => {
    try {
      const score = typeof context.PokerBot.score === 'function'
        ? context.PokerBot.score(cards) : bot.score(cards);
      return {score};
    } catch (error) {
      return {error: String(error.stack || error)};
    }
  });
  return {source, actions, scores};
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify(run(input)) + '\n');
} catch (error) {
  process.stdout.write(JSON.stringify({error: String(error.stack || error)}) + '\n');
  process.exitCode = 1;
}
