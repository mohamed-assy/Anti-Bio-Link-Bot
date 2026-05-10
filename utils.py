import aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, enums

DB_PATH = "bot_database.db"
CLEANUP_INTERVAL_HOURS = 24
INACTIVE_CHAT_DAYS     = 60

logger = logging.getLogger(__name__)

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
                warn_in_pm    INTEGER DEFAULT 1,
                updated_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()
    logger.info("✅ Database initialized.")

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        async for member in client.get_chat_members(
            chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
        ):
            if member.user.id == user_id:
                return True
    except Exception:
        return False
    return False

async def get_chat_settings(chat_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT ban_days, warn_in_group, warn_in_pm FROM chat_settings WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"ban_days": row[0], "warn_in_group": bool(row[1]), "warn_in_pm": bool(row[2])}
            return {"ban_days": 30, "warn_in_group": True, "warn_in_pm": True}

async def update_chat_settings(chat_id: int, **kwargs):
    s = await get_chat_settings(chat_id)
    s.update(kwargs)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, ban_days, warn_in_group, warn_in_pm, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                ban_days      = excluded.ban_days,
                warn_in_group = excluded.warn_in_group,
                warn_in_pm    = excluded.warn_in_pm,
                updated_at    = datetime('now')
        """, (chat_id, s["ban_days"], int(s["warn_in_group"]), int(s["warn_in_pm"])))
        await db.commit()

async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM whitelists WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        ) as cursor:
            return await cursor.fetchone() is not None

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
        async with db.execute("SELECT user_id FROM whitelists WHERE chat_id = ?", (chat_id,)) as cursor:
            return [row[0] for row in await cursor.fetchall()]

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
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

async def reset_kicks(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM kicks WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

async def get_kick_count(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM kicks WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

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

async def add_allowed_link(link: str):
    link = link.strip().lower().rstrip("/")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO allowed_links (link) VALUES (?)", (link,))
        await db.commit()

async def remove_allowed_link(link: str):
    link = link.strip().lower().rstrip("/")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM allowed_links WHERE link = ?", (link,))
        await db.commit()
        return cursor.rowcount > 0

async def get_allowed_links() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT link FROM allowed_links ORDER BY added_at") as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def is_link_allowed(url: str) -> bool:
    links = await get_allowed_links()
    url = url.strip().lower()
    return any(allowed in url for allowed in links)

async def cleanup_database():
    async with aiosqlite.connect(DB_PATH) as db:
        # Remove expired bans
        c = await db.execute("DELETE FROM bans WHERE unban_at < datetime('now')")
        d_bans = c.rowcount

        # Remove kick records older than 30 days
        c = await db.execute("DELETE FROM kicks WHERE updated_at < datetime('now', '-30 days')")
        d_kicks = c.rowcount

        # FIX: Do NOT auto-delete whitelists by date — admins whitelist users intentionally.
        # Whitelist entries should only be removed via /unfree or the remove button.

        await db.execute("VACUUM")
        await db.commit()
    logger.info(f"🧹 Cleanup: {d_bans} expired bans | {d_kicks} old kick records removed.")

async def start_cleanup_scheduler():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)
        try:
            await cleanup_database()
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
