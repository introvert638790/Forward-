# Telegram Forward Bot

A private owner-only Telegram bot that forwards messages between channels, normal groups, and forum topics — any combination of Channel, Normal Group, or Topic Wise Group as source and destination. Built with aiogram v3 and MongoDB Atlas.

> 🚀 **This bot can be deployed on Render, Heroku, Koyeb, Railway, Google Cloud Run, Google Colab, VPS, and Termux.** See [Deployment](#-deployment).

---

## Table of Contents

- [Features](#features)
- [Main Menu Overview](#main-menu-overview)
- [Environment Variables](#environment-variables)
- [GitHub Setup](#github-setup)
- [Deployment](#-deployment)
- [MongoDB Atlas Setup Notes](#mongodb-atlas-setup-notes)
- [Bot Setup Flow](#bot-setup-flow)
- [Anonymous Admin Setup](#anonymous-admin-setup)
- [Range Forwarding](#range-forwarding)
- [Commands Reference](#commands-reference)
- [After a Render Restart](#after-a-render-restart)
- [Project Structure](#project-structure)

---

## Features

- **Source types:** Channel, Normal Group, Topic Wise Group (specific topic or General topic)
- **Destination types:** Channel, Normal Group, Topic Wise Group (specific topic or General topic)
- Forward videos, documents (PDF, HTML), text messages, and photos
- Forum topic forwarding with automatic `message_thread_id` detection (both source and destination side)
- Two setup modes for every group/topic source or destination:
  - **Normal / Visible Setup** — for a regular member/admin whose identity is visible in the chat
  - **Anonymous Admin Setup** — for Telegram's "Remain Anonymous" admin mode, using a one-time setup code (see [Anonymous Admin Setup](#anonymous-admin-setup))
- Range forwarding:
  - **Channel source:** select start/end messages by forwarding them to the bot
  - **Normal Group / Topic Wise Group source:** select start/end messages by sending their **message links** to the bot
- Configurable per-message delay
- FloodWait handling with automatic retry
- Progress updates during forwarding
- Checkpoint-based resume after Render restarts
- Owner-only access, with an in-chat Allow/Ban approval flow for other users
- Per-user keep-alive self-pinger while a forwarding job is active (auto-detects Render's `RENDER_EXTERNAL_URL`; harmlessly disables itself on platforms without a public URL, e.g. Google Colab)

---

## Main Menu Overview

`/start` or `/menu` in the bot's private chat opens the main menu:

```
📢 Set Source
📍 Set Destination
▶️ Range Forward
⏹ Stop Forwarding      📊 Status
⚙️ Settings
🛡 Admin Panel           (owner only)
```

**Set Source** and **Set Destination** each open the same two-level picker:

```
📢 Set Source / 📍 Set Destination
   ├── 📢 Channel
   ├── 💬 Topic Wise Group   (includes General topic — no separate button)
   └── 👥 Normal Group
```

Choosing **Topic Wise Group** or **Normal Group** opens the setup-mode choice:

```
   ├── 👤 Normal / Visible Setup     (no code — you're visible in the chat)
   └── 🕵️ Anonymous Admin Setup      (generates a one-time setup code)
```

Choosing **Channel** (source or destination) skips straight to "forward a message from that channel" — no visible/anonymous split, since channel setup never needs anonymous handling.

When an Anonymous Admin Setup code is redeemed in a group/topic, the bot sends a private-chat confirmation card before saving anything:

```
🔗 Source/Destination detected

🏷 Group: <name>
📌 Topic: <name>          (only for Topic Wise Group)

Is this your source/destination?
[✅ Confirm]  [❌ Cancel]
```

Nothing is saved until you tap **Confirm** — see [Anonymous Admin Setup](#anonymous-admin-setup) below for the full flow.

---

## Environment Variables

Set these in Render Dashboard → Environment:

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `OWNER_ID` | ✅ | Your Telegram user ID |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | optional | Database name (default: `tgforwardbot`) |
| `DEFAULT_DELAY_SECONDS` | optional | Delay per message (default: `3.0`) |

To get your `OWNER_ID`, message [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## GitHub Setup

1. Create a new repository on GitHub (private recommended)
2. Clone it locally:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```
3. Copy all project files into the repository folder
4. Push to GitHub:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

---

## 🚀 Deployment

This bot uses long polling (not a Telegram webhook), so it doesn't strictly need a public URL to function — the included aiohttp server exists only as a health-check endpoint for platforms (like Render's free tier) that require the process to bind a port. It supports **Render, Heroku, Koyeb, Railway, Google Cloud Run, Google Colab, VPS, and Termux**.

### One-Click Deploy

| Platform | Deploy |
|---|---|
| Render | [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Alex638796/service-) |
| Heroku | [![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Alex638796/service-) |
| Koyeb | [![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/Alex638796/service-&branch=main&name=tg-forward-bot) |
| Google Colab | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Alex638796/service-/blob/main/colab_deploy.ipynb) |
| Google Cloud | [![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://ssh.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/Alex638796/service-&cloudshell_tutorial=.cloudshell/GCLOUD.md) |

> ⚠️ None of these badges fully automate deployment — each opens that platform's setup screen where you still need to fill in environment variables manually (see the [Environment Variables](#environment-variables) table above). They save the "find and configure a new app" step, not the "enter your credentials" step.

> ℹ️ **Railway**: this bot can also be deployed on Railway — it auto-detects the Python app via Nixpacks and picks up `requirements.txt` + `Procfile` with no extra configuration needed. There's no one-click badge here because Railway deploy buttons require a pre-registered Railway template (a manual one-time setup on Railway's side, separate from this repo). To deploy: create a new Railway project → "Deploy from GitHub repo" → select this repo → set the environment variables from the table above.

### Render (primary supported platform)

1. Log in to [Render](https://render.com)
2. Click **New → Web Service**
3. Connect your GitHub repository
4. Render will detect `render.yaml` automatically. If not, configure manually:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Plan:** Free
5. Add environment variables in the **Environment** tab:
   - `BOT_TOKEN`
   - `OWNER_ID`
   - `MONGO_URI`
6. Click **Deploy**

The bot uses long polling, so no public URL or webhook configuration is needed — Render's free tier just requires the process to bind `$PORT`, which the built-in health server already handles.

### Heroku

Uses the included `app.json` and `Procfile`. After clicking the badge above, fill in the prompted fields (`BOT_TOKEN`, `OWNER_ID`, `MONGO_URI`).

### Koyeb / Google Cloud Run

Both use the included `Dockerfile` directly — no extra build configuration needed. For manual Cloud Run deployment via `gcloud` CLI, see `.cloudshell/GCLOUD.md`.

### Google Colab (temporary/testing)

Click the Colab badge above to open `colab_deploy.ipynb`. Fill in the mandatory fields (`BOT_TOKEN`, `OWNER_ID`, `MONGO_URI`) — optional fields (`MONGO_DB_NAME`, `DEFAULT_DELAY_SECONDS`) come pre-filled — and run the single cell. It clones the repo, installs dependencies, and runs `python3 main.py`. Keep-alive pinging is automatically inactive here since Colab has no `RENDER_EXTERNAL_URL`. The cell blocks and streams logs live; press ■ to stop.

> ⚠️ Colab sessions are temporary (disconnect on tab close, inactivity, or after Colab's free-tier time limit — up to ~12 hours). Use this for quick testing only; for always-on hosting, use Render/Heroku/Koyeb/Railway above.

### VPS

```bash
git clone https://github.com/Alex638796/service-.git
cd service-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export OWNER_ID="your_telegram_user_id"
export MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net"
python3 main.py
```

Or via Docker, using the included `Dockerfile`:

```bash
git clone https://github.com/Alex638796/service-.git
cd service-
sudo apt install docker.io -y
sudo docker build -t tg-forward-bot .
sudo docker run -it --rm --env-file .env tg-forward-bot
```

No public URL is required — this bot works over long polling on any VPS with outbound internet access.

### Termux (Android)

```bash
pkg update && pkg upgrade -y
pkg install python git -y
git clone https://github.com/Alex638796/service-.git
cd service-
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export OWNER_ID="your_telegram_user_id"
export MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net"
python3 main.py
```

> If any MongoDB-related package fails to build on Termux, run `pkg install libffi openssl` first, then retry `pip install -r requirements.txt`. A remote MongoDB instance (e.g. MongoDB Atlas's free tier) is recommended over trying to run MongoDB on-device.

---

## MongoDB Atlas Setup Notes

Your Atlas connection string must allow connections from all IPs (`0.0.0.0/0`) in **Network Access**, because Render free tier uses dynamic IPs.

The bot will create all required collections automatically on first use.

---

## Bot Setup Flow

The bot must be an **admin** in any group, topic-group, or channel you use as a source or destination:
- **Channel source:** the bot only needs to be a member (not necessarily admin) to read/copy messages.
- **Channel destination, Normal Group (source or destination), Topic Wise Group (source or destination):** the bot must be an **admin** — required either to post (destination) or to reliably read messages (group/topic source).

Every source and destination type is configured from the main menu: **Set Source** / **Set Destination** → pick a type → pick **Normal / Visible Setup** or **Anonymous Admin Setup**.

### Channel (source or destination)

1. Add the bot to the channel:
   - Source: member is enough
   - Destination: admin with **Post Messages** permission
2. In the bot's private chat: **Set Source → Channel** (or **Set Destination → Channel**)
3. Forward any message from that channel to the bot — it's saved automatically, no code needed

### Normal Group (source or destination)

1. Add the bot as admin to the group
2. In the bot's private chat: **Set Source → Normal Group** (or **Set Destination → Normal Group**)
3. Choose a setup mode:
   - **Normal / Visible Setup** — if your identity is visible in the group, go to the group and send `/setsource` (or `/setdestination`) with no code
   - **Anonymous Admin Setup** — if you use Telegram's "Remain Anonymous" mode, the bot gives you a one-time command like `/setsource H7K9P2MX` (long-press to copy). Send it in the group. Confirm the detected group in your **private chat**.

### Topic Wise Group (source or destination) — specific topic or General

1. Add the bot as admin to the forum-enabled supergroup
2. In the bot's private chat: **Set Source → Topic Wise Group** (or **Set Destination → Topic Wise Group**)
3. Choose a setup mode:
   - **Normal / Visible Setup** — open the target topic (or the General topic) and send `/setsource` (or `/setdestination`) there, no code
   - **Anonymous Admin Setup** — get the one-time command from private chat, open the target topic (or General), send it there, then confirm in your **private chat**
4. General topic works exactly the same way as a named topic — there's no separate "General" button, the bot detects it automatically from where you send the command

> The bot always tells the token owner's private chat what was detected (group name + topic name) before saving anything — nothing is saved on an Anonymous Admin Setup until you tap **Confirm**.

---

## Anonymous Admin Setup

Telegram's "Remain Anonymous" admin mode hides your real identity from the bot — messages you send appear to come from the group itself, not from you personally. This means the bot has no way to know *which* admin is actually setting things up, so the usual "I recognize who's talking to me" logic can't work.

To solve this, group and topic setup (Normal Group and Topic Wise Group, for both source and destination) offers **Anonymous Admin Setup**:

1. In the bot's private chat, choose **Anonymous Admin Setup** for the type you're configuring.
2. The bot generates a one-time setup command, e.g.:
   ```
   /setsource H7K9P2MX
   ```
   or
   ```
   /setdestination H7K9P2MX
   ```
   Long-press the command to copy it — the whole line is copyable.
3. Go to the group (or the specific topic / General topic), with Remain Anonymous switched on, and send that exact command.
4. The bot detects the group/topic and sends a confirmation card **to your private chat only** — never into the group, so the destination/source details and your identity stay private even if the code is accidentally used in someone else's group.
5. Tap **✅ Confirm** to save it, or **❌ Cancel** to discard it.

Notes:
- The code is valid for **10 minutes** and can be used **only once**.
- A source code only works for source setup, and a destination code only works for destination setup — they can't be mixed up.
- A code generated for **Normal Group** won't work inside a **Topic Wise Group**, and vice versa.
- If your identity is visible in the group (not anonymous), just use **Normal / Visible Setup** instead — no code needed at all.

---

## Range Forwarding

1. In bot private chat, press **Range Forward** or type `/range`
2. Depending on your source type:
   - **Channel source:** forward the **first** message of your desired range from the source channel, then the **last** message
   - **Normal Group / Topic Wise Group source:** send the message **link** of the **first** message, then the link of the **last** message (e.g. `https://t.me/c/1234567890/123` or, for a topic, `https://t.me/c/1234567890/11/123`)
3. The bot checks both messages belong to the configured source (and, for Topic Wise Group, the same topic) before continuing
4. Confirm the range — forwarding starts immediately
5. The bot sends progress updates every 25 messages
6. When complete, the bot sends a summary

To stop mid-forwarding:
```
/stop
```

---

## Commands Reference

### Private chat (owner/allowed users)

| Command | Description |
|---|---|
| `/start` | Open main menu |
| `/menu` | Open main menu |
| `/setsource` | Legacy shortcut: arms Channel source capture directly (use the **Set Source** menu button for the full Channel/Normal Group/Topic Wise Group picker) |
| `/arm_topic_mode` | Legacy shortcut: arms Normal / Visible Setup directly (use the **Set Destination** / **Set Source** menu buttons instead) |
| `/setnormalgroup` | Legacy shortcut, same as `/arm_topic_mode` |
| `/range` | Start range forwarding |
| `/stop` | Stop active forwarding |
| `/status` | Show current configuration and status |
| `/setdelay` | Change forwarding delay |

### Sent inside a group or topic (not private chat)

| Command | Description |
|---|---|
| `/setsource` | Complete source setup for a Normal Group or Topic Wise Group. Send with no code if using Normal / Visible Setup; send `/setsource CODE` if using Anonymous Admin Setup. |
| `/setdestination` | Complete destination setup for a Normal Group or Topic Wise Group. Same no-code / `/setdestination CODE` distinction as above. |

For Topic Wise Group, send the command **inside the specific topic** you want to use (or inside the General topic) — the bot detects which one from where the command was sent.

### Owner-only (admin panel / user management)

| Command | Description |
|---|---|
| `/users` | List all users by access status |
| `/allow <user_id>` | Approve a pending user |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/tasks` | Show active forwarding tasks |
| `/broadcast` | Send a message to all allowed users |

---

## After a Render Restart

If Render restarts the bot while forwarding is active, the bot will:
1. Detect the interrupted task on startup
2. Send you a message with the last processed message ID
3. Tell you the exact start point to resume from

To resume, use `/range` and forward the next message as the new start.

---

## Project Structure

```
├── main.py                  # Entry point
├── config.py                # Environment variables
├── database.py              # MongoDB connection
├── requirements.txt
├── render.yaml
├── Procfile                 # Heroku process definition
├── Dockerfile                # Used by Koyeb, Railway, Google Cloud Run, VPS-via-Docker
├── app.json                 # Heroku one-click deploy manifest
├── colab_deploy.ipynb        # Google Colab one-click deploy notebook
├── .cloudshell/              # Google Cloud Shell walkthrough
│   ├── tutorial.yaml
│   └── GCLOUD.md
├── .env.example
├── handlers/
│   ├── private.py           # All private chat commands and FSM flows (Set Source/Destination menus, Range Forward, Settings)
│   ├── group.py             # /setdestination and /setsource sent inside groups/topics (visible + anonymous-admin token flows)
│   └── admin.py             # Owner-only: user approval, stats, active tasks, broadcast
├── services/
│   ├── forwarding.py        # Core forwarding engine (source-type agnostic — works by chat_id + message_id)
│   ├── keepalive.py         # Per-user keep-alive self-pinger
│   └── task_manager.py      # asyncio task lifecycle
├── keyboards/
│   └── main_menu.py         # Inline keyboard layouts, incl. Set Source/Destination submenus and Anonymous Admin confirm cards
├── models/
│   └── config_model.py      # MongoDB document schemas, incl. SetupSession (anonymous-admin token bridge)
└── utils/
    ├── auth.py              # Owner authorization
    └── helpers.py           # DB helpers, message ID/link extraction, setup-session token logic, formatting
```
