<div align="center">

# 🛡️ Anti Bio Link

**A smart Telegram bot that silently protects your group from users promoting channels or groups via their bio.**

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-2.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://pyrogram.org)
[![SQLite](https://img.shields.io/badge/SQLite-Local_DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[**💬 Support Group**](https://t.me/english_world_chatting) · [**➕ Add to Group**](https://t.me/anti_bio_link_bot)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Bio Scanner** | Automatically scans every user's bio when they send a message |
| ⚠️ **Strike System** | Warns & kicks users, bans after reaching the strike limit |
| 📩 **PM Warnings** | Sends a private message to the user explaining the action |
| ⚙️ **Per-Group Settings** | Each group configures its own rules via `/settings` |
| 🔗 **Link Whitelist** | Admins can whitelist specific links to be ignored |
| 👥 **User Whitelist** | Exempt trusted users from bio scanning |
| 🧹 **Auto Cleanup** | Automatically purges old data every 24 hours |
| 🚫 **Silent Actions** | Deletes messages quietly — no unnecessary noise |

---

## 🚀 Getting Started

### 1 · Clone the repository

```bash
git clone https://github.com/yourname/AntiBioLink
cd AntiBioLink
```

### 2 · Install dependencies

```bash
pip install -r requirements.txt
```

### 3 · Configure environment

Copy `.env` and fill in your credentials:

```env
API_ID=your_api_id           # from my.telegram.org
API_HASH=your_api_hash       # from my.telegram.org
BOT_TOKEN=your_bot_token     # from @BotFather
BAN_DURATION_DAYS=30         # default ban duration
```

> 🔑 Get your `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org)
> 🤖 Get your `BOT_TOKEN` from [@BotFather](https://t.me/BotFather)

### 4 · Run the bot

```bash
python bio.py
```

---

## 📁 Project Structure

```
AntiBioLink/
├── bio.py            ← Main bot file (entry point)
├── config.py         ← Configuration & environment loader
├── utils.py          ← Database helpers & scheduler
├── requirements.txt  ← Python dependencies
├── .env              ← Your secret credentials
└── bot_database.db   ← Auto-created on first run
```

---

## ⚙️ Group Setup

1. Add the bot to your group
2. Grant it **Admin** rights with:
   - ✅ Delete Messages
   - ✅ Ban Users
3. Use `/settings` to configure the bot for your group

---

## 🛠️ Commands

### 👮 Admin Commands *(in group)*

| Command | Description |
|---|---|
| `/settings` | Open the settings panel |
| `/free` | Whitelist a user — reply or use `/free @username` |
| `/unfree` | Remove a user from the whitelist |
| `/freelist` | View all whitelisted users |
| `/addlink <url>` | Whitelist a specific link |
| `/removelink <url>` | Remove a link from the whitelist |
| `/linklist` | View all whitelisted links |
| `/unban @user` | Unban a user in this group |

### 🤖 Auto Protection

When a non-whitelisted user sends a message with a Telegram promotion link in their bio:

```
Strike 1 → Warning (group + PM) → 3 min grace period → Kick
Strike 2 → Warning (group + PM) → 3 min grace period → Kick
Strike 3 → Final warning        → 5 min grace period → 30-day Ban
```

> ✅ If the user removes the link during the grace period, no action is taken.

---

## 📊 Settings Panel

Use `/settings` in your group to access the interactive settings panel:

```
⚙️ Bot Settings
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
📍 Group: My Group

⚡ Strikes before ban:  [ ➖  2  ➕ ]
⏳ Ban duration:        [ ➖ 30d ➕ ]
📢 Group warning:       [ ✅ Enabled ]
📩 PM warning:          [ ✅ Enabled ]
```

All settings are saved **per group** — changing settings in one group does not affect others.

---

## 🧹 Auto Cleanup

Every **24 hours**, the bot automatically removes:

- Expired bans (past their unban date)
- Old kick records (older than 30 days)
- Whitelist entries from inactive chats (older than 60 days)

Then runs `VACUUM` to keep the database lean.

---

## 📦 Requirements

```
pyrofork
tgcrypto
aiosqlite
python-dotenv
```

- Python **3.8+**
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- API credentials from [my.telegram.org](https://my.telegram.org)

---

## 🌐 Hosting on Wispbyte

1. Upload all files to your container
2. Set the startup command to:
   ```
   python bio.py
   ```
3. Make sure `.env` has your credentials filled in

---

<div align="center">

Made with ❤️ · [💬 Support](https://t.me/english_world_chatting)

</div>
