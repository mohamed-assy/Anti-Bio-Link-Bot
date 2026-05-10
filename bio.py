"""
🛡️ Anti Bio Link Bot
Group: https://t.me/english_world_chatting
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters, errors
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)

from config import API_ID, API_HASH, BOT_TOKEN, URL_PATTERN
from utils import (
    init_db, start_cleanup_scheduler, is_admin,
    is_whitelisted, add_whitelist, remove_whitelist, get_whitelist,
    log_ban, remove_ban,
    increment_kick, reset_kicks, get_kick_count,
    add_allowed_link, remove_allowed_link, get_allowed_links, is_link_allowed,
    get_chat_settings, update_chat_settings,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Client(
    "anti_bio_link",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def strike_badge(count: int, limit: int) -> str:
    return "🔴" * count + "⚪️" * (limit - count)


async def delete_message_safe(message: Message):
    try:
        await message.delete()
    except errors.MessageDeleteForbidden:
        pass
    except Exception:
        pass


async def delete_user_messages(client: Client, chat_id: int, user_id: int):
    try:
        await client.delete_user_history(chat_id, user_id)
    except Exception:
        pass


async def _delete_after(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def kick_user_safe(client: Client, chat_id: int, user_id: int):
    try:
        await client.ban_chat_member(chat_id, user_id)
        await client.unban_chat_member(chat_id, user_id)
    except errors.ChatAdminRequired:
        pass
    except Exception:
        pass


async def ban_user_safe(client: Client, chat_id: int, user_id: int, days: int):
    try:
        until_date = datetime.now(timezone.utc) + timedelta(days=days)
        await client.ban_chat_member(chat_id, user_id, until_date=until_date)
        await log_ban(chat_id, user_id, days)
        await reset_kicks(chat_id, user_id)
    except errors.ChatAdminRequired:
        pass
    except Exception:
        pass


async def get_user_bio(client: Client, user_id: int) -> str:
    """
    FIX: get_chat() on a user ID does NOT return bio reliably.
    Must use get_users() to fetch the UserFull object which contains bio.
    """
    try:
        user = await client.get_users(user_id)
        return user.bio or ""
    except Exception:
        return ""


# ── Warning Messages ───────────────────────────────────────────────────────────

async def send_group_warn_strike(message: Message, user, strike: int, limit: int, wait_mins: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    badge   = strike_badge(strike, limit)

    text = (
        f"⚠️ **Warning — Promotional Bio Detected**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"👤 **User:** {mention}\n"
        f"📌 **Reason:** Bio contains a Telegram promotion link\n"
        f"📊 **Strikes:** {badge}  `{strike} / {limit}`\n"
        f"⏱️ **Action in:** {wait_mins} minute(s) — remove the link to avoid it\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🛡️ Powered by **Anti Bio Link**"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Dismiss", callback_data="close")]])
    sent = await message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
    return sent


async def send_group_final_warning(message: Message, user, wait_mins: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"

    text = (
        f"🚨 **Final Warning**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"👤 **User:** {mention}\n"
        f"📌 **Reason:** Bio contains a Telegram promotion link\n"
        f"⏱️ **You have {wait_mins} minute(s)** to remove the link from your bio\n"
        f"🔨 **Failure to do so will result in a 30-day ban**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🛡️ Powered by **Anti Bio Link**"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Dismiss", callback_data="close")]])
    sent = await message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
    return sent


async def send_group_ban_notice(message: Message, user, ban_days: int):
    mention = f"[{user.first_name}](tg://user?id={user.id})"

    text = (
        f"🚫 **User Banned**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"👤 **User:** {mention}\n"
        f"📌 **Reason:** Repeated promotion via bio\n"
        f"⏳ **Duration:** {ban_days} day(s)\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🛡️ This group is protected by **Anti Bio Link**"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Dismiss", callback_data="close")]])
    sent = await message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
    return sent


async def send_pm_warn_strike(client: Client, user, chat_title: str, strike: int, limit: int, wait_mins: int):
    badge = strike_badge(strike, limit)
    text = (
        f"⚠️ **Warning — {chat_title}**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📌 **Reason:** Your bio contains a Telegram promotion link\n"
        f"📊 **Strikes:** {badge}  `{strike} / {limit}`\n"
        f"⏱️ **You have {wait_mins} minute(s)** to remove the link from your bio\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"✅ Remove the link now to avoid being kicked."
    )
    try:
        await client.send_message(user.id, text)
    except Exception:
        pass


async def send_pm_kick_notice(client: Client, user, chat_title: str):
    text = (
        f"👢 **You have been removed from {chat_title}**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📌 **Reason:** Your bio still contained a Telegram promotion link\n\n"
        f"✅ Remove the link from your bio before rejoining.\n"
        f"⚠️ Further violations will result in a permanent ban."
    )
    try:
        await client.send_message(user.id, text)
    except Exception:
        pass


async def send_pm_final_warning(client: Client, user, chat_title: str, wait_mins: int):
    text = (
        f"🚨 **Final Warning — {chat_title}**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📌 **Reason:** Your bio contains a Telegram promotion link\n"
        f"⏱️ **You have {wait_mins} minute(s)** to remove it\n"
        f"🔨 **If not removed, you will be banned for 30 days**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"This is your last chance. Act now."
    )
    try:
        await client.send_message(user.id, text)
    except Exception:
        pass


async def send_pm_ban_notice(client: Client, user, chat_title: str, ban_days: int):
    text = (
        f"🚫 **You have been banned from {chat_title}**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📌 **Reason:** Repeated promotion via bio\n"
        f"⏳ **Duration:** {ban_days} day(s)\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"To appeal, contact the group admins."
    )
    try:
        await client.send_message(user.id, text)
    except Exception:
        pass


# ── /start ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    bot  = await client.get_me()
    text = (
        f"🛡️ **Anti Bio Link**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
        f"I keep your group safe by detecting and removing users\n"
        f"who advertise Telegram channels or groups via their bio.\n\n"
        f"**⚙️ How it works:**\n"
        f"› Scans user bios for Telegram promotion links\n"
        f"› Warns the user and gives them time to fix their bio\n"
        f"› Kicks on strike 1 & 2 after the grace period\n"
        f"› Bans for 30 days on the 3rd strike\n\n"
        f"Type /help to see all available commands."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{bot.username}?startgroup=true")],
        [
            InlineKeyboardButton("💬 Support", url="https://t.me/english_world_chatting"),
            InlineKeyboardButton("❌ Close", callback_data="close"),
        ]
    ])
    await message.reply_text(text, reply_markup=kb)


# ── /help ──────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    text = (
        f"🛡️ **Anti Bio Link — Commands**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
        f"**👮 Admin Commands:**\n"
        f"› `/settings` — view & adjust bot settings\n"
        f"› `/free` — exempt a user from scanning\n"
        f"› `/unfree` — remove exemption\n"
        f"› `/freelist` — list exempted users\n"
        f"› `/addlink` — whitelist a specific link\n"
        f"› `/removelink` — remove a whitelisted link\n"
        f"› `/linklist` — view all whitelisted links\n"
        f"› `/unban` — unban a user in this group\n\n"
        f"**⚙️ Configurable per group:**\n"
        f"› Ban duration (days)\n"
        f"› Group warning on/off\n"
        f"› Private message warning on/off\n\n"
        f"**🤖 Auto protection flow:**\n"
        f"› **Strike 1 & 2:** Warning → 3 min grace → Kick\n"
        f"› **Strike 3:** Final warning → 5 min grace → Ban (30 days)"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])
    await message.reply_text(text, reply_markup=kb)


# ── /settings ──────────────────────────────────────────────────────────────────

def settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    group_btn = f"{'✅' if settings['warn_in_group'] else '❌'} Group Warn"
    pm_btn    = f"{'✅' if settings['warn_in_pm']    else '❌'} PM Warn"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏳ Ban duration: {settings['ban_days']} day(s)", callback_data="noop")],
        [
            InlineKeyboardButton("➖", callback_data="ban_days_dec"),
            InlineKeyboardButton("➕", callback_data="ban_days_inc"),
        ],
        [
            InlineKeyboardButton(group_btn, callback_data="toggle_group_warn"),
            InlineKeyboardButton(pm_btn,    callback_data="toggle_pm_warn"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close")],
    ])


def settings_text(settings: dict, chat_title: str) -> str:
    return (
        f"⚙️ **Bot Settings**\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📍 **Group:** {chat_title}\n\n"
        f"⏳ **Ban duration:** `{settings['ban_days']} day(s)`\n"
        f"📢 **Group warning:** {'Enabled ✅' if settings['warn_in_group'] else 'Disabled ❌'}\n"
        f"📩 **PM warning:** {'Enabled ✅' if settings['warn_in_pm'] else 'Disabled ❌'}\n\n"
        f"**Strike system (fixed):**\n"
        f"› Strike 1 & 2 → Warning + 3 min grace → Kick\n"
        f"› Strike 3 → Final warning + 5 min grace → Ban"
    )


@app.on_message(filters.group & filters.command("settings"))
async def settings_handler(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    settings = await get_chat_settings(message.chat.id)
    await message.reply_text(
        settings_text(settings, message.chat.title),
        reply_markup=settings_keyboard(settings)
    )


# ── /free /unfree /freelist ────────────────────────────────────────────────────

@app.on_message(filters.group & filters.command("free"))
async def cmd_free(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1].lstrip("@")
        try:
            target = await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception:
            return await message.reply_text("❌ **User not found.**")
    else:
        return await message.reply_text("**Usage:** `/free @username` or reply to a user.")

    await add_whitelist(message.chat.id, target.id)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚫 Remove", callback_data=f"unwhitelist_{target.id}"),
        InlineKeyboardButton("❌ Close",  callback_data="close"),
    ]])
    await message.reply_text(
        f"✅ **{target.mention} has been whitelisted.**\n"
        f"The bot will ignore this user's bio.",
        reply_markup=kb
    )


@app.on_message(filters.group & filters.command("unfree"))
async def cmd_unfree(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1].lstrip("@")
        try:
            target = await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception:
            return await message.reply_text("❌ **User not found.**")
    else:
        return await message.reply_text("**Usage:** `/unfree @username` or reply to a user.")

    if await is_whitelisted(message.chat.id, target.id):
        await remove_whitelist(message.chat.id, target.id)
        text = f"🚫 **{target.mention} removed from whitelist.**"
    else:
        text = f"ℹ️ **{target.mention} is not whitelisted.**"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Re-add", callback_data=f"whitelist_{target.id}"),
        InlineKeyboardButton("❌ Close",  callback_data="close"),
    ]])
    await message.reply_text(text, reply_markup=kb)


@app.on_message(filters.group & filters.command("freelist"))
async def cmd_freelist(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    ids = await get_whitelist(message.chat.id)
    if not ids:
        return await message.reply_text("📋 **No whitelisted users in this group.**")
    text = "📋 **Whitelisted Users:**\n\n"
    for i, uid in enumerate(ids, 1):
        try:
            u = await client.get_users(uid)
            text += f"{i}. {u.mention} `{uid}`\n"
        except Exception:
            text += f"{i}. [Unknown] `{uid}`\n"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])
    await message.reply_text(text, reply_markup=kb)


# ── /addlink /removelink /linklist ─────────────────────────────────────────────

@app.on_message(filters.group & filters.command("addlink"))
async def cmd_addlink(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/addlink t.me/example`")
    link = message.command[1].strip().lower().rstrip("/")
    await add_allowed_link(link)
    await message.reply_text(f"✅ **`{link}` added to ignored links.**")


@app.on_message(filters.group & filters.command("removelink"))
async def cmd_removelink(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/removelink t.me/example`")
    link = message.command[1].strip().lower().rstrip("/")
    removed = await remove_allowed_link(link)
    if removed:
        await message.reply_text(f"🗑️ **`{link}` removed from ignored links.**")
    else:
        await message.reply_text(f"⚠️ **`{link}` not found in the list.**")


@app.on_message(filters.group & filters.command("linklist"))
async def cmd_linklist(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    links = await get_allowed_links()
    if not links:
        return await message.reply_text("📋 **No ignored links yet.**")
    text = "📋 **Ignored Links:**\n\n" + "\n".join(f"{i}. `{lnk}`" for i, lnk in enumerate(links, 1))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])
    await message.reply_text(text, reply_markup=kb)


# ── /unban ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.group & filters.command("unban"))
async def cmd_unban(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1].lstrip("@")
        try:
            target = await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception:
            return await message.reply_text("❌ **User not found.**")
    else:
        return await message.reply_text("**Usage:** `/unban @username` or reply to a user.")

    try:
        await client.unban_chat_member(message.chat.id, target.id)
        await remove_ban(message.chat.id, target.id)
        await reset_kicks(message.chat.id, target.id)
        await message.reply_text(f"✅ **{target.mention} has been unbanned.**")
    except Exception as e:
        await message.reply_text(f"❌ **Failed to unban:** `{e}`")


# ── Callbacks ──────────────────────────────────────────────────────────────────

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data    = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if data == "close":
        return await callback_query.message.delete()

    if data == "noop":
        return await callback_query.answer()

    if not await is_admin(client, chat_id, user_id):
        return await callback_query.answer("❌ Admins only.", show_alert=True)

    settings_actions = {
        "toggle_group_warn": ("warn_in_group", None),
        "toggle_pm_warn":    ("warn_in_pm",    None),
        "ban_days_inc":      ("ban_days",       5),
        "ban_days_dec":      ("ban_days",      -5),
    }

    if data in settings_actions:
        settings = await get_chat_settings(chat_id)
        key, delta = settings_actions[data]
        if delta is None:
            settings[key] = not settings[key]
        else:
            settings[key] = max(1, settings[key] + delta)
        await update_chat_settings(chat_id, **settings)
        settings = await get_chat_settings(chat_id)
        await callback_query.message.edit_text(
            settings_text(settings, callback_query.message.chat.title),
            reply_markup=settings_keyboard(settings)
        )
        return await callback_query.answer("✅ Updated!")

    if data.startswith("whitelist_"):
        target_id = int(data.split("_")[1])
        await add_whitelist(chat_id, target_id)
        user = await client.get_users(target_id)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚫 Remove", callback_data=f"unwhitelist_{target_id}"),
            InlineKeyboardButton("❌ Close",  callback_data="close"),
        ]])
        await callback_query.message.edit_text(
            f"✅ **{user.mention} has been whitelisted.**", reply_markup=kb
        )
        return await callback_query.answer()

    if data.startswith("unwhitelist_"):
        target_id = int(data.split("_")[1])
        await remove_whitelist(chat_id, target_id)
        user = await client.get_users(target_id)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Re-add", callback_data=f"whitelist_{target_id}"),
            InlineKeyboardButton("❌ Close",  callback_data="close"),
        ]])
        await callback_query.message.edit_text(
            f"🚫 **{user.mention} removed from whitelist.**", reply_markup=kb
        )
        return await callback_query.answer()


# ── Core Logic ─────────────────────────────────────────────────────────────────

async def handle_violation(client: Client, message: Message, user, chat_id: int, settings: dict, strike: int):
    """Handle a bio violation based on the current strike count."""
    ban_days   = settings["ban_days"]
    KICK_LIMIT = 3

    if strike < KICK_LIMIT:
        # ── Strike 1 or 2: warn → 3 min grace → kick ──
        wait_mins = 3
        warn_msg  = None

        if settings["warn_in_group"]:
            warn_msg = await send_group_warn_strike(message, user, strike, KICK_LIMIT, wait_mins)
        if settings["warn_in_pm"]:
            await send_pm_warn_strike(client, user, message.chat.title, strike, KICK_LIMIT, wait_mins)

        await asyncio.sleep(wait_mins * 60)

        # Check if the user removed the link during the grace period
        # FIX: use get_users() instead of get_chat() to reliably fetch bio
        bio = await get_user_bio(client, user.id)
        found = [m.group(0) for m in URL_PATTERN.finditer(bio)]
        all_ok = all(await is_link_allowed(url) for url in found) if found else True

        if all_ok:
            if warn_msg:
                try:
                    await warn_msg.delete()
                except Exception:
                    pass
            return

        # Link still present — delete warning, delete user messages, kick
        if warn_msg:
            try:
                await warn_msg.delete()
            except Exception:
                pass
        await delete_message_safe(message)
        await delete_user_messages(client, chat_id, user.id)
        await kick_user_safe(client, chat_id, user.id)
        if settings["warn_in_pm"]:
            await send_pm_kick_notice(client, user, message.chat.title)

    else:
        # ── Strike 3+: final warning → 5 min grace → ban ──
        wait_mins = 5
        warn_msg  = None

        if settings["warn_in_group"]:
            warn_msg = await send_group_final_warning(message, user, wait_mins)
        if settings["warn_in_pm"]:
            await send_pm_final_warning(client, user, message.chat.title, wait_mins)

        await asyncio.sleep(wait_mins * 60)

        # Check if the user removed the link
        # FIX: use get_users() instead of get_chat() to reliably fetch bio
        bio = await get_user_bio(client, user.id)
        found = [m.group(0) for m in URL_PATTERN.finditer(bio)]
        all_ok = all(await is_link_allowed(url) for url in found) if found else True

        if all_ok:
            await reset_kicks(chat_id, user.id)
            if warn_msg:
                try:
                    await warn_msg.delete()
                except Exception:
                    pass
            return

        # Link still present — delete warning, delete user messages, ban
        if warn_msg:
            try:
                await warn_msg.delete()
            except Exception:
                pass
        await delete_message_safe(message)
        await delete_user_messages(client, chat_id, user.id)
        await ban_user_safe(client, chat_id, user.id, ban_days)
        if settings["warn_in_group"]:
            ban_notice = await send_group_ban_notice(message, user, ban_days)
            if ban_notice:
                asyncio.create_task(_delete_after(ban_notice, 180))
        if settings["warn_in_pm"]:
            await send_pm_ban_notice(client, user, message.chat.title, ban_days)


# ── Bio Scanner ──────────────────────────────────────────────────────────────────

# Track ongoing operations to prevent duplicate processing
_processing: set = set()


@app.on_message(filters.group)
async def check_bio(client: Client, message: Message):
    if not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Prevent processing the same user in the same group concurrently
    key = (chat_id, user_id)
    if key in _processing:
        return
    _processing.add(key)

    try:
        if await is_admin(client, chat_id, user_id):
            return
        if await is_whitelisted(chat_id, user_id):
            return

        # FIX: use get_users() to reliably fetch bio
        bio = await get_user_bio(client, user_id)
        if not bio:
            return

        found_urls = [m.group(0) for m in URL_PATTERN.finditer(bio)]
        if not found_urls:
            return

        all_allowed = all(await is_link_allowed(url) for url in found_urls)
        if all_allowed:
            return

        settings = await get_chat_settings(chat_id)
        strike   = await increment_kick(chat_id, user_id)
        user     = message.from_user

        await handle_violation(client, message, user, chat_id, settings, strike)

    finally:
        _processing.discard(key)


# ── Bot Entry Point ──────────────────────────────────────────────────────────────

async def main():
    await init_db()
    # FIX: start the bot first, THEN create tasks that need a running event loop
    await app.start()
    asyncio.create_task(start_cleanup_scheduler())
    await asyncio.Event().wait()


if __name__ == "__main__":
    # FIX: use asyncio.run() instead of app.run() for proper async lifecycle
    asyncio.run(main())
