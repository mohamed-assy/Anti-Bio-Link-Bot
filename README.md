<div align="center">

# 🛡️ Anti Bio Link

**Automatically protects Telegram groups from users promoting channels or groups via their bio.**

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-2.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://pyrogram.org)
[![SQLite](https://img.shields.io/badge/SQLite-Local_DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)

[**💬 Support Group**](https://t.me/english_world_chatting) · [**🤖 Try the Bot**](https://t.me/anti_bio_link_bot)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Bio Scanner** | Scans every user's bio when they send a message |
| 🗑️ **Instant Delete** | Deletes the offending message immediately |
| ⏳ **Grace Period** | Gives the user time to fix their bio before action |
| 🔄 **Strike System** | 3 strikes — kick on 1 & 2, ban on 3 |
| 🔇 **Grace Deletion** | Any message sent during grace period is deleted |
| 🔗 **Link Whitelist** | Admins can whitelist specific links to ignore |
| 👥 **User Whitelist** | Exempt trusted users from scanning |
| ⚙️ **Per-Group Settings** | Each group has its own configurable settings |
| 🧹 **Auto Cleanup** | Purges expired data every 24 hours |

---

## 🚀 Setup

### 1 · Clone

```bash
git clone https://github.com/yourname/AntiBioLink
cd AntiBioLink
```

### 2 · Install

```bash
pip install -r requirements.txt
```

### 3 · Configure `.env`

```env
API_ID=your_api_id        # from my.telegram.org
API_HASH=your_api_hash    # from my.telegram.org
BOT_TOKEN=your_bot_token  # from @BotFather
```

### 4 · Run

```bash
python bio.py
```

---

## 📁 Project Structure

```
AntiBioLink/
├── bio.py            ← Main bot (entry point)
├── config.py         ← Configuration loader
├── utils.py          ← Database & helpers
├── requirements.txt
├── .env              ← Your credentials
└── bot_database.db   ← Auto-created on first run
```

---

## ⚙️ Group Setup

1. Add the bot to your group
2. Grant **Admin** rights with **Delete Messages** + **Ban Users**
3. Use `/settings` to configure per-group options

---

## 🛠️ Commands

### 👮 Admin Commands *(in group)*

| Command | Description |
|---|---|
| `/settings` | Open the settings panel |
| `/free` | Whitelist a user (reply or `/free @user`) |
| `/unfree` | Remove from whitelist |
| `/freelist` | View all whitelisted users |
| `/addlink <url>` | Ignore a specific link |
| `/removelink <url>` | Remove an ignored link |
| `/linklist` | View all ignored links |
| `/unban @user` | Unban a user in this group |

---

## 🤖 Auto Protection Flow

```
User sends a message
        ↓
Bio scanned for Telegram links
        ↓
Link found → message deleted instantly
        ↓
Warning posted in group with grace period
        ↓
Any new message during grace → deleted automatically
        ↓
Strike 1 & 2 → 3 min grace → Kick
Strike 3     → 5 min grace → Ban (configurable days)
        ↓
User removed link during grace → no action, warning deleted
```

---

## 🧹 Auto Cleanup (every 24h)

- Expired bans removed
- Old kick records (30+ days) cleared
- Inactive whitelist entries (60+ days) cleared
- Database vacuumed to reclaim space

---

<div align="center">

Made with ❤️ · [💬 Support](https://t.me/english_world_chatting)

</div>
