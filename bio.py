"""
🛡️ Anti Bio Link Bot
Support: https://t.me/english_world_chatting
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from config import API_ID, API_HASH, BOT_TOKEN, URL_PATTERN
from utils import (
    init_db, start_cleanup_scheduler, is_admin,
    is_whitelisted, add_whitelist, remove_whitelist, get_whitelist,
    log_ban, remove_ban,
    increment_kick, reset_kicks,
    add_allowed_link, remove_allowed_link, get_allowed_links, is_link_allowed,
    get_chat_settings, update_chat_settings,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Client("anti_bio_link", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

KICK_LIMIT  = 3
GRACE_KICK  = 3   # minutes before kick
GRACE_BAN   = 5   # minutes before ban
BAN_NOTICE_TTL = 180  # seconds before ban notice is deleted

# Sets for tracking
_processing: set = set()
_in_grace:   set = set()

# ── Utility ────────────────────────────────────────────────────────────────────

def badge(count: int, limit: int) -> str:
    return "🔴" * count + "⚪️" * (limit - count)

def close_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Dismiss", callback_data="close")]])

async def safe_delete(msg) -> None:
    if msg is None:
        return
    try:
        await msg.delete()
    except Exception:
        pass

async def delete_after(msg, delay: int) -> None:
    await asyncio.sleep(delay)
    await safe_delete(msg)

async def delete_user_history(client: Client, chat_id: int, user_id: int) -> None:
    try:
        await client.delete_user_history(chat_id, user_id)
    except Exception:
        pass

async def kick_user(client: Client, chat_id: int, user_id: int) -> None:
    try:
        await client.ban_chat_member(chat_id, user_id)
        await client.unban_chat_member(chat_id, user_id)
    except Exception:
        pass

async def ban_user(client: Client, chat_id: int, user_id: int, days: int) -> None:
    try:
        until = datetime.now(timezone.utc) + timedelta(days=days)
        await client.ban_chat_member(chat_id, user_id, until_date=until)
        await log_ban(chat_id, user_id, days)
        await reset_kicks(chat_id, user_id)
    except Exception:
        pass

async def bio_has_violation(client: Client, user_id: int) -> bool:
    try:
        chat = await client.get_chat(user_id)
        bio  = chat.bio or ""
        for m in URL_PATTERN.finditer(bio):
            if not await is_link_allowed(m.group(0)):
                return True
        return False
    except Exception:
        return True

async def resolve_user(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        arg = message.command[1].lstrip("@")
        try:
            return await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception:
            await message.reply_text("❌ **User not found.**")
            return None
    await message.reply_text("ℹ️ **Reply to a user or provide a username / ID.**")
    return None

# ── Messages ───────────────────────────────────────────────────────────────────

async def msg_strike_warning(message: Message, user, strike: int, wait: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    text = (
        f"⚠️ **Bio Violation Detected**\n"
        f"{'─' * 22}\n"
        f"👤 **User ›** {mention}\n"
        f"📌 **Reason ›** Telegram promotion link in bio\n"
        f"📊 **Strike ›** {badge(strike, KICK_LIMIT)}  {strike}/{KICK_LIMIT}\n"
        f"⏳ **Grace period ›** {wait} min — remove the link to avoid action\n"
        f"{'─' * 22}\n"
        f"🛡️ **Anti Bio Link** is watching."
    )
    return await message.reply_text(text, reply_markup=close_kb(), disable_web_page_preview=True)

async def msg_final_warning(message: Message, user, wait: int, ban_days: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    text = (
        f"🚨 **Final Warning — Last Chance**\n"
        f"{'─' * 22}\n"
        f"👤 **User ›** {mention}\n"
        f"📌 **Reason ›** Telegram promotion link in bio\n"
        f"📊 **Strike ›** {badge(KICK_LIMIT, KICK_LIMIT)}  {KICK_LIMIT}/{KICK_LIMIT}\n"
        f"⏳ **Grace period ›** {wait} min — remove the link **now**\n"
        f"🔨 **Consequence ›** {ban_days}-day ban if link remains\n"
        f"{'─' * 22}\n"
        f"🛡️ **Anti Bio Link** — This is your final warning."
    )
    return await message.reply_text(text, reply_markup=close_kb(), disable_web_page_preview=True)

async def msg_ban_notice(message: Message, user, ban_days: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    text = (
        f"🚫 **User Banned**\n"
        f"{'─' * 22}\n"
        f"👤 **User ›** {mention}\n"
        f"📌 **Reason ›** Repeated bio promotion after warnings\n"
        f"⏳ **Duration ›** {ban_days} day(s)\n"
        f"{'─' * 22}\n"
        f"🛡️ This group is protected by **Anti Bio Link**."
    )
    return await message.reply_text(text, reply_markup=close_kb(), disable_web_page_preview=True)

# ── /start ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    bot  = await client.get_me()
    text = (
        f"🛡️ **Anti Bio Link**\n"
        f"{'─' * 22}\n\n"
        f"Automatically protects your group from users who\n"
        f"promote Telegram channels or groups via their bio.\n\n"
        f"**⚙️ How it works**\n"
        f"› Detects Telegram links in user bios\n"
        f"› Deletes messages instantly on detection\n"
        f"› Issues a warning with a grace period\n"
        f"› Any message during grace period is deleted\n"
        f"› Strike 1 & 2 → Kick after grace period\n"
        f"› Strike 3 → Ban after grace period\n\n"
        f"Use /help to see all commands."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{bot.username}?startgroup=true")],
        [
            InlineKeyboardButton("💬 Support", url="https://t.me/english_world_chatting"),
            InlineKeyboardButton("✖️ Close", callback_data="close"),
        ],
    ])
    await message.reply_text(text, reply_markup=kb)

# ── /help ──────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("help"))
async def cmd_help(client: Client, message: Message):
    text = (
        f"🛡️ **Anti Bio Link — Help**\n"
        f"{'─' * 22}\n\n"
        f"**👮 Admin Commands**\n"
        f"› `/settings` — configure bot for this group\n"
        f"› `/free` — whitelist a user (reply or @user)\n"
        f"› `/unfree` — remove from whitelist\n"
        f"› `/freelist` — view whitelisted users\n"
        f"› `/addlink <url>` — ignore a specific link\n"
        f"› `/removelink <url>` — remove ignored link\n"
        f"› `/linklist` — view all ignored links\n"
        f"› `/unban` — unban a user in this group\n\n"
        f"**🤖 Auto Protection Flow**\n"
        f"› Message deleted instantly on detection\n"
        f"› Warning issued with grace period\n"
        f"› Any new message during grace → deleted\n"
        f"› Strike 1 & 2 → {GRACE_KICK} min grace → **Kick**\n"
        f"› Strike 3 → {GRACE_BAN} min grace → **Ban**\n"
        f"› Link removed during grace → no action taken"
    )
    await message.reply_text(text, reply_markup=close_kb())

# ── /settings ──────────────────────────────────────────────────────────────────

def build_settings_kb(s: dict) -> InlineKeyboardMarkup:
    gw = "✅ Group Warn ON" if s["warn_in_group"] else "❌ Group Warn OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏳ Ban Duration: {s['ban_days']} day(s)", callback_data="noop")],
        [
            InlineKeyboardButton("➖ 5", callback_data="ban_days_dec"),
            InlineKeyboardButton("➕ 5", callback_data="ban_days_inc"),
        ],
        [InlineKeyboardButton(gw, callback_data="toggle_group_warn")],
        [InlineKeyboardButton("✖️ Close", callback_data="close")],
    ])

def build_settings_text(s: dict, title: str) -> str:
    return (
        f"⚙️ **Settings — {title}**\n"
        f"{'─' * 22}\n\n"
        f"⏳ **Ban duration ›** `{s['ban_days']} day(s)`\n"
        f"📢 **Group warning ›** {'Enabled ✅' if s['warn_in_group'] else 'Disabled ❌'}\n\n"
        f"**Strike flow (fixed)**\n"
        f"› Strike 1 & 2 → {GRACE_KICK} min grace → Kick\n"
        f"› Strike 3 → {GRACE_BAN} min grace → Ban"
    )

@app.on_message(filters.group & filters.command("settings"))
async def cmd_settings(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    s = await get_chat_settings(message.chat.id)
    await message.reply_text(build_settings_text(s, message.chat.title), reply_markup=build_settings_kb(s))

# ── /free /unfree /freelist ────────────────────────────────────────────────────

@app.on_message(filters.group & filters.command("free"))
async def cmd_free(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = await resolve_user(client, message)
    if not target:
        return
    await add_whitelist(message.chat.id, target.id)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚫 Remove", callback_data=f"unwl_{target.id}"),
        InlineKeyboardButton("✖️ Close",  callback_data="close"),
    ]])
    await message.reply_text(
        f"✅ **{target.mention} is now whitelisted.**\n"
        f"Their bio will no longer be scanned.",
        reply_markup=kb
    )

@app.on_message(filters.group & filters.command("unfree"))
async def cmd_unfree(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = await resolve_user(client, message)
    if not target:
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Re-add", callback_data=f"wl_{target.id}"),
        InlineKeyboardButton("✖️ Close",  callback_data="close"),
    ]])
    if await is_whitelisted(message.chat.id, target.id):
        await remove_whitelist(message.chat.id, target.id)
        await message.reply_text(f"🚫 **{target.mention} removed from whitelist.**", reply_markup=kb)
    else:
        await message.reply_text(f"ℹ️ **{target.mention} is not whitelisted.**", reply_markup=kb)

@app.on_message(filters.group & filters.command("freelist"))
async def cmd_freelist(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    ids = await get_whitelist(message.chat.id)
    if not ids:
        return await message.reply_text("📋 **Whitelist is empty.**")
    lines = []
    for i, uid in enumerate(ids, 1):
        try:
            u = await client.get_users(uid)
            lines.append(f"{i}. {u.mention} — `{uid}`")
        except Exception:
            lines.append(f"{i}. [Unknown] — `{uid}`")
    text = f"📋 **Whitelisted Users**\n{'─' * 22}\n\n" + "\n".join(lines)
    await message.reply_text(text, reply_markup=close_kb())

# ── /addlink /removelink /linklist ─────────────────────────────────────────────

@app.on_message(filters.group & filters.command("addlink"))
async def cmd_addlink(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/addlink t.me/example`")
    link = message.command[1].strip().lower().rstrip("/")
    await add_allowed_link(link)
    await message.reply_text(f"✅ **`{link}` added to ignored links.**\nBios containing this link will be ignored.")

@app.on_message(filters.group & filters.command("removelink"))
async def cmd_removelink(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/removelink t.me/example`")
    link = message.command[1].strip().lower().rstrip("/")
    if await remove_allowed_link(link):
        await message.reply_text(f"🗑️ **`{link}` removed from ignored links.**")
    else:
        await message.reply_text(f"⚠️ **`{link}` was not found in the list.**")

@app.on_message(filters.group & filters.command("linklist"))
async def cmd_linklist(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    links = await get_allowed_links()
    if not links:
        return await message.reply_text("📋 **No ignored links yet.**")
    text = f"📋 **Ignored Links**\n{'─' * 22}\n\n" + "\n".join(f"{i}. `{l}`" for i, l in enumerate(links, 1))
    await message.reply_text(text, reply_markup=close_kb())

# ── /unban ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.group & filters.command("unban"))
async def cmd_unban(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = await resolve_user(client, message)
    if not target:
        return
    try:
        await client.unban_chat_member(message.chat.id, target.id)
        await remove_ban(message.chat.id, target.id)
        await reset_kicks(message.chat.id, target.id)
        await message.reply_text(f"✅ **{target.mention} has been unbanned.**")
    except Exception as e:
        await message.reply_text(f"❌ **Failed:** `{e}`")

# ── Callbacks ──────────────────────────────────────────────────────────────────

@app.on_callback_query()
async def callback_handler(client, cq):
    data    = cq.data
    chat_id = cq.message.chat.id
    user_id = cq.from_user.id

    if data == "close":
        return await cq.message.delete()
    if data == "noop":
        return await cq.answer()

    if not await is_admin(client, chat_id, user_id):
        return await cq.answer("❌ Admins only.", show_alert=True)

    actions = {
        "toggle_group_warn": ("warn_in_group", None),
        "ban_days_inc":      ("ban_days",  5),
        "ban_days_dec":      ("ban_days", -5),
    }

    if data in actions:
        s = await get_chat_settings(chat_id)
        key, delta = actions[data]
        s[key] = not s[key] if delta is None else max(1, s[key] + delta)
        await update_chat_settings(chat_id, **s)
        s = await get_chat_settings(chat_id)
        await cq.message.edit_text(build_settings_text(s, cq.message.chat.title), reply_markup=build_settings_kb(s))
        return await cq.answer("✅ Saved!")

    if data.startswith("wl_"):
        tid = int(data.split("_")[1])
        await add_whitelist(chat_id, tid)
        u = await client.get_users(tid)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚫 Remove", callback_data=f"unwl_{tid}"),
            InlineKeyboardButton("✖️ Close",  callback_data="close"),
        ]])
        await cq.message.edit_text(f"✅ **{u.mention} is now whitelisted.**", reply_markup=kb)
        return await cq.answer()

    if data.startswith("unwl_"):
        tid = int(data.split("_")[1])
        await remove_whitelist(chat_id, tid)
        u = await client.get_users(tid)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Re-add", callback_data=f"wl_{tid}"),
            InlineKeyboardButton("✖️ Close",  callback_data="close"),
        ]])
        await cq.message.edit_text(f"🚫 **{u.mention} removed from whitelist.**", reply_markup=kb)
        return await cq.answer()

# ── Grace Period Handler ────────────────────────────────────────────────────────

@app.on_message(filters.group, group=1)
async def grace_period_handler(client: Client, message: Message):
    if not message.from_user:
        return
    if (message.chat.id, message.from_user.id) in _in_grace:
        await safe_delete(message)

# ── Core Violation Handler ─────────────────────────────────────────────────────

async def handle_violation(client: Client, message: Message, user, chat_id: int, settings: dict, strike: int):
    ban_days  = settings["ban_days"]
    show_warn = settings["warn_in_group"]

    # Delete triggering message immediately
    await safe_delete(message)

    if strike < KICK_LIMIT:
        warn_msg = await msg_strike_warning(message, user, strike, GRACE_KICK) if show_warn else None
        _in_grace.add((chat_id, user.id))
        await asyncio.sleep(GRACE_KICK * 60)
        _in_grace.discard((chat_id, user.id))

        await safe_delete(warn_msg)

        if not await bio_has_violation(client, user.id):
            return  # User fixed their bio — no action

        await delete_user_history(client, chat_id, user.id)
        await kick_user(client, chat_id, user.id)

    else:
        warn_msg = await msg_final_warning(message, user, GRACE_BAN, ban_days) if show_warn else None
        _in_grace.add((chat_id, user.id))
        await asyncio.sleep(GRACE_BAN * 60)
        _in_grace.discard((chat_id, user.id))

        await safe_delete(warn_msg)

        if not await bio_has_violation(client, user.id):
            await reset_kicks(chat_id, user.id)
            return  # User fixed their bio — no action

        await delete_user_history(client, chat_id, user.id)
        await ban_user(client, chat_id, user.id, ban_days)

        if show_warn:
            notice = await msg_ban_notice(message, user, ban_days)
            asyncio.create_task(delete_after(notice, BAN_NOTICE_TTL))

# ── Bio Scanner ─────────────────────────────────────────────────────────────────

@app.on_message(filters.group, group=0)
async def check_bio(client: Client, message: Message):
    if not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    key     = (chat_id, user_id)

    if key in _processing or key in _in_grace:
        return

    _processing.add(key)
    try:
        if await is_admin(client, chat_id, user_id):
            return
        if await is_whitelisted(chat_id, user_id):
            return

        try:
            bio = (await client.get_chat(user_id)).bio or ""
        except Exception:
            return

        violated = False
        for m in URL_PATTERN.finditer(bio):
            if not await is_link_allowed(m.group(0)):
                violated = True
                break
        if not violated:
            return

        settings = await get_chat_settings(chat_id)
        strike   = await increment_kick(chat_id, user_id)
        await handle_violation(client, message, message.from_user, chat_id, settings, strike)

    finally:
        _processing.discard(key)

# ── Entry Point ─────────────────────────────────────────────────────────────────

async def main():
    await init_db()
    asyncio.create_task(start_cleanup_scheduler())
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
