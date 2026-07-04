# 🤖 Group Admin Bot

A feature-rich Telegram Group Admin Bot with **65+ commands**, MongoDB persistence, Render deployment support, and UptimeRobot keep-alive.

---

## ✨ Features

| Category | Commands |
|---|---|
| **Moderation** | ban, unban, tban, kick, mute, unmute, tmute |
| **Warnings** | warn, unwarn, resetwarn, warnings, warnlimit |
| **Admin Tools** | promote, demote, title, pin, unpin, unpinall, purge, del |
| **Chat Settings** | lock, unlock, locktypes, slowmode, setdesc, settitle |
| **Welcome/Goodbye** | setwelcome, clearwelcome, setgoodbye, cleargoodbye |
| **Rules** | rules, setrules, clearrules |
| **Notes** | note, get, notes, clearnote, clearallnotes |
| **Filters** | filter, filters, stop, stopall |
| **Blacklist** | blacklist, unblacklist, blmode |
| **Anti-Flood** | antiflood, floodmode |
| **Security** | captcha, antispam, stickerban, nightmode |
| **Info** | id, info, chatinfo, adminlist, invite, report |
| **Utility** | start, help, ping, stats, broadcast |

---

## 🚀 Deploy on Render (Step-by-Step)

### Step 1 — Push to GitHub

```bash
cd telegram-admin-bot
git init
git add .
git commit -m "Initial commit — Group Admin Bot"
git remote add origin https://github.com/YOUR_USERNAME/group-admin-bot.git
git push -u origin main
```

### Step 2 — Create Render Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Set these fields:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free

### Step 3 — Add Environment Variables in Render

In your Render service → **Environment** tab, add:

| Key | Value |
|---|---|
| `BOT_TOKEN` | Your token from [@BotFather](https://t.me/BotFather) |
| `MONGO_URI` | Your MongoDB Atlas connection string |
| `OWNER_IDS` | Your Telegram user ID (comma-separated for multiple) |

### Step 4 — Deploy

Click **Deploy** — Render will build and start the bot.
Your service URL will look like: `https://group-admin-bot.onrender.com`

---

## ⏰ UptimeRobot Setup (Always-On)

Render free tier sleeps after 15 minutes of inactivity. UptimeRobot prevents this.

1. Go to [uptimerobot.com](https://uptimerobot.com) → **Add New Monitor**
2. Set:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Group Admin Bot
   - **URL:** `https://your-app-name.onrender.com/health`
   - **Monitoring Interval:** 5 minutes
3. Click **Create Monitor**

The bot will now stay alive 24/7. ✅

---

## 📦 MongoDB Atlas Setup

1. Go to [mongodb.com/atlas](https://www.mongodb.com/cloud/atlas) → Create free cluster
2. **Database Access** → Add user with read/write permissions
3. **Network Access** → Allow access from anywhere (`0.0.0.0/0`)
4. **Connect** → **Connect your application** → Copy the URI
5. Replace `<password>` with your actual password

Your `MONGO_URI` will look like:
```
mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/admin_bot?retryWrites=true&w=majority
```

---

## 📋 Welcome Message Placeholders

| Placeholder | Replaces with |
|---|---|
| `{name}` | Clickable user mention |
| `{username}` | @username |
| `{chat}` | Group name |
| `{id}` | User's Telegram ID |

Example: `/setwelcome Welcome {name} to {chat}! 🎉`

---

## 🔒 Permission Levels

- **Owner** — Full access (OWNER_IDS in env)
- **Admin** — Group admin commands
- **User** — Basic commands (rules, notes, report, verify)

---

## 🛠 Local Development

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_token"
export MONGO_URI="your_mongo_uri"
export OWNER_IDS="your_telegram_id"
python bot.py
```

---

## 📝 Text Formatting

All bot messages use Telegram HTML formatting:
- **Bold** — command names, important info
- *Italic* — descriptions, hints
- `Monospace` — IDs, codes, values

---

*Built with python-telegram-bot v21 + Motor (async MongoDB)*
