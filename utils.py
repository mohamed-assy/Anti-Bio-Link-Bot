import aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, enums

DB_PATH               = "bot_database.db"
CLEANUP_INTERVAL_HRS  = 24
INACTIVE_CHAT_DAYS    = 60

logger = logging.getLogger(__name__)

# ── Init ───────────────────────────────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whitelists (
                chat_id  INTEGER,
                user_id  INTEGER,
                added_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bans (
                chat_id   INTEGER,
                user_id   INTEGER,
                banned_at TEXT DEFAULT (datetime('now')),
                unban_at  TEXT,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kicks (
                chat_id    INTEGER,
                user_id    INTEGER,
                count      INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_links (
                link     TEXT PRIMARY KEY,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id       INTEGER PRIMARY KEY,
                ban_days      INTEGER DEFAULT 30,
                warn_in_group INTEGER DEFAULT 1,
                updated_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()
    logger.info("✅ Database initialized.")

# ── Admin check ────────────────────────────────────────────────────────────────

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user.id == user_id:
                return True
    except Exception:
        return False
    return False

# ── Chat settings ──────────────────────────────────────────────────────────────

async def get_chat_settings(chat_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT ban_days, warn_in_group FROM chat_settings WHERE chat_id = ?", (chat_id,)
        ) as c:
            row = await c.fetchone()
            if row:
                return {"ban_days": row[0], "warn_in_group": bool(row[1])}
            return {"ban_days": 30, "warn_in_group": True}

async def update_chat_settings(chat_id: int, **kwargs):
    s = await get_chat_settings(chat_id)
    s.update(kwargs)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, ban_days, warn_in_group, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                ban_days      = excluded.ban_days,
                warn_in_group = excluded.warn_in_group,
                updated_at    = datetime('now')
        """, (chat_id, s["ban_days"], int(s["warn_in_group"])))
        await db.commit()

# ── Whitelist ──────────────────────────────────────────────────────────────────

async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM whitelists WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ) as c:
            return await c.fetchone() is not None

async def add_whitelist(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO whitelists (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        await db.commit()

async def remove_whitelist(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whitelists WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

async def get_whitelist(chat_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM whitelists WHERE chat_id = ?", (chat_id,)) as c:
            return [r[0] for r in await c.fetchall()]

# ── Kicks ──────────────────────────────────────────────────────────────────────

async def increment_kick(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO kicks (chat_id, user_id, count, updated_at)
            VALUES (?, ?, 1, datetime('now'))
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                count = count + 1, updated_at = datetime('now')
        """, (chat_id, user_id))
        await db.commit()
        async with db.execute(
            "SELECT count FROM kicks WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ) as c:
            row = await c.fetchone()
            return row[0] if row else 1

async def reset_kicks(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM kicks WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

# ── Bans ───────────────────────────────────────────────────────────────────────

async def log_ban(chat_id: int, user_id: int, days: int):
    unban_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO bans (chat_id, user_id, banned_at, unban_at)
            VALUES (?, ?, datetime('now'), ?)
        """, (chat_id, user_id, unban_at))
        await db.commit()

async def remove_ban(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bans WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

# ── Allowed links ──────────────────────────────────────────────────────────────

async def add_allowed_link(link: str):
    link = link.strip().lower().rstrip("/")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO allowed_links (link) VALUES (?)", (link,))
        await db.commit()

async def remove_allowed_link(link: str) -> bool:
    link = link.strip().lower().rstrip("/")
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("DELETE FROM allowed_links WHERE link = ?", (link,))
        await db.commit()
        return c.rowcount > 0

async def get_allowed_links() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT link FROM allowed_links ORDER BY added_at") as c:
            return [r[0] for r in await c.fetchall()]

async def is_link_allowed(url: str) -> bool:
    url = url.strip().lower()
    return any(link in url for link in await get_allowed_links())

# ── Cleanup ────────────────────────────────────────────────────────────────────

async def cleanup_database():
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("DELETE FROM bans WHERE unban_at < datetime('now')")
        d_bans = c.rowcount
        c = await db.execute("DELETE FROM kicks WHERE updated_at < datetime('now', '-30 days')")
        d_kicks = c.rowcount
        cutoff = (datetime.utcnow() - timedelta(days=INACTIVE_CHAT_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        c = await db.execute("DELETE FROM whitelists WHERE added_at < ?", (cutoff,))
        d_wl = c.rowcount
        await db.execute("VACUUM")
        await db.commit()
    logger.info(f"🧹 Cleanup: {d_bans} bans | {d_kicks} kicks | {d_wl} whitelist entries removed.")

async def start_cleanup_scheduler():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_HRS * 3600)
        try:
            await cleanup_database()
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
