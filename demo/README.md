# Play My Poker Bot

**[Open the live demo](https://play-my-poker-bot.vercel.app)**

Heads-up No-Limit Texas Hold’em against the v7 strategy. Each player starts with 2,000 play chips. Blinds start at 10/20 and double every ten hands, capped at 2,000/4,000. The match ends when one player has all 4,000 chips. No account or backend is needed.

## Open it locally

Double-click `index.html`, or open it in a browser. Everything it needs—styles, game engine, strategy, and equity data—is inline. No internet connection is required to play locally.

## What was tested

| Check | Result |
|---|---|
| Python v7 vs JavaScript, 500 valid states | 500/500 identical actions, including raise amounts |
| Hand scoring against Python | 300/300 identical scores |
| Complete simulated matches | 2,000; zero errors or illegal actions |
| Chip conservation and game-state checks | 223,216 passed |
| Browser games | Six complete matches at desktop, 390px, and 320px widths |
| Existing Python regression suite | 70 passed |

Browser checks cover the 600ms bot delay, raise controls, displayed bets and chip totals, hidden cards, winning-card highlights, hand results, replay, session scores, keyboard shortcuts, and horizontal overflow. The desktop check uses 1440×900 with no page scrolling; phone controls stay pinned at 390px and 320px widths. Reports are in [`test_results/`](test_results/). The comparison covers actual simulator states, browser-engine states, all streets and stack depths, and targeted draw decisions. The JavaScript implementation reproduces Python’s seeded random stream as well as its equity lookup data. The explanations describe the selected strategy branch without naming the bot’s hidden cards.

Use **F** to fold, **C** to check/call, and **R** to raise to the selected amount on desktop. Shortcuts are disabled while editing the slider or when it is not your turn. The scoreboard lasts until the page is closed or reloaded. At showdown, gold outlines mark a winning five-card hand; in a split pot, both players’ best five are highlighted. Current bets appear in front of each seat, separate from the collected pot. These are presentation features; the strategy and game engine are unchanged by the visual polish.

## Edit and rebuild

From the repository folder:

```sh
python3 demo/generate_bot_data.py --check
python3 demo/build.py
python3 demo/test_parity.py
node demo/test_engine.js
node demo/test_presentation.js
python3 -m unittest discover -q
```

Edit `template.html` for markup, `style.css` for styling, `ui.js` for controls and animations, and `presentation.js` for hand descriptions and highlights. `engine.js` contains the game rules and `bot.js` the ported strategy. `build.py` combines them into the deployable `index.html`. If Python strategy constants or equity data change, run `python3 demo/generate_bot_data.py` before rebuilding; strategy logic changes must also be ported manually.

The optional browser test uses Playwright and an installed Google Chrome. Install its test dependency from the repository folder, then run:

```sh
npm install --no-save --package-lock=false playwright
node demo/test_browser.cjs
```

Playwright is only a test tool; the shipped page has no dependencies. Browser screenshots and local packages are ignored by Git.

## Deploy to Vercel, step by step

The first deployment is already complete. The Vercel project is `play-my-poker-bot` in the `austin-le-monte` team. These steps let you publish later edits yourself.

1. Open **Terminal** on your Mac (Command–Space, type “Terminal,” press Return).
2. Go to the repository and rebuild after editing:

   ```sh
   cd ~/Downloads/pokerbot
   python3 demo/build.py
   python3 demo/test_parity.py
   node demo/test_engine.js
   ```

3. Check Node.js is installed with `node --version`. It is already installed on this Mac. On another computer, install the LTS release from [nodejs.org](https://nodejs.org/) first.
4. Enter the demo folder and sign in. The command downloads the Vercel CLI if needed; you do not need a global installation:

   ```sh
   cd demo
   npx --yes vercel login
   ```

   Open the URL printed in Terminal and approve the sign-in in your browser. Return to Terminal when it confirms success. Your visitors do not need a Vercel account.
5. This folder is already linked on this Mac. On a fresh checkout, link the existing project:

   ```sh
   npx --yes vercel link --yes --scope austin-le-monte --project play-my-poker-bot
   ```

6. Publish the page:

   ```sh
   npx --yes vercel deploy --prod --yes
   ```

   Wait for the ready message, then open [the production link](https://play-my-poker-bot.vercel.app) in a private browser window to confirm it opens without signing in. `vercel.json` specifies a static site with no build step; `.vercelignore` uploads only the page and deployment configuration. The folder you deploy must be `demo`, not the repository root.
7. Save your source changes to GitHub from the repository folder:

   ```sh
   cd ..
   git add README.md demo
   git commit -m "Update poker demo"
   git push origin main
   ```

The initial attempt to connect automatic GitHub deployments was rejected because the Vercel account lacked a GitHub login connection. Direct CLI deployment works and the public site is live. For now, deploy with step 6 after each update; a Git push alone does not publish it. To enable automatic deployments later, connect GitHub in Vercel’s account settings, connect this repository in the project’s Git settings, and set its root directory to `demo`.

If npm reports `EACCES` for its existing cache on this Mac, use a separate cache for the same command, for example:

```sh
npm --cache /tmp/pokerbot-npm-cache exec --yes --package=vercel -- vercel deploy --prod --yes
```

See Vercel’s [CLI deployment guide](https://vercel.com/docs/projects/deploy-from-cli) and [deploy command documentation](https://vercel.com/docs/cli/deploy) for its command options.
