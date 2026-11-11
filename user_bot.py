import asyncio
import logging
import html
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
import config

user_bot = Bot(token=config.USER_BOT_TOKEN)
user_dp = Dispatcher()

# --- FSM States ---
class UserSearch(StatesGroup):
    waiting_query = State()

# --- Klaviaturalar ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 O'yinlar"), KeyboardButton(text="📱 Ilovalar")],
            [KeyboardButton(text="🔍 Qidiruv"), KeyboardButton(text="ℹ️ Ma'lumot")]
        ],
        resize_keyboard=True
    )

# --- Majburiy Obunani Tekshirish ---
async def check_user_subscriptions(user_id: int):
    # 1. Agar admin bo'lsa, obuna talab qilinmaydi
    if db.is_admin(user_id):
        return []

    # 2. Agar majburiy obuna sozlamalarda yoqilmagan bo'lsa, tekshirilmaydi
    is_sub_enabled = db.get_setting("force_sub_enabled", "0")
    if is_sub_enabled != "1":
        return []

    channels = db.get_mandatory_channels()
    if not channels:
        return []

    unsubscribed = []
    for ch in channels:
        cid = ch['channel_id']
        try:
            target_chat_id = int(cid) if (cid.startswith("-") or cid.isdigit()) else cid
            member = await user_bot.get_chat_member(chat_id=target_chat_id, user_id=user_id)
            if member.status in ['creator', 'administrator', 'member', 'restricted']:
                continue
            else:
                unsubscribed.append(ch)
        except TelegramBadRequest as e:
            logging.warning(f"Kanalni tekshirishda ogohlantirish ({cid}): {e}")
            continue
        except TelegramForbiddenError:
            logging.warning(f"Bot kanaldan chiqarilgan yoki huquqi yo'q ({cid})")
            continue
        except Exception as e:
            logging.warning(f"Kanal obunasini tekshirish xatosi ({cid}): {e}")
            continue

    return unsubscribed

def get_subscription_keyboard(unsubscribed_channels):
    buttons = []
    for ch in unsubscribed_channels:
        title = ch['title'] or ch['username'] or "Kanalga o'tish"
        link = ch['invite_link'] or (f"https://t.me/{ch['username'].replace('@', '')}" if ch['username'] else "https://t.me/iskndrv_games")
        buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
    
    buttons.append([InlineKeyboardButton(text="✅ A'zo bo'ldim (Tekshirish)", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Start Komandasi ---
@user_dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = html.escape(message.from_user.full_name or "")

    # Bazaga qo'shish
    db.add_user(user_id, username, full_name)

    # Parametr bormi (deep link: /start item_12)
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("item_"):
        try:
            item_id = int(args[1].replace("item_", ""))
            item = db.get_item(item_id)
            if item:
                await send_item_card(message, item)
                return
        except Exception:
            pass

    # Majburiy obuna tekshiruvi
    unsub = await check_user_subscriptions(user_id)
    if unsub:
        await message.answer(
            f"Assalomu alaykum, <b>{full_name}</b>!\n\n"
            "⚠️ Botdan to'liq foydalanish va eng sara o'yin hamda ilovalarni yuklab olish uchun "
            "quyidagi homiy kanallarga a'zo bo'ling:",
            parse_mode="HTML",
            reply_markup=get_subscription_keyboard(unsub)
        )
        return

    await message.answer(
        f"Assalomu alaykum, <b>{full_name}</b>!\n\n"
        "🎮 <b>Iskndrv Games</b> rasmiy botiga xush kelibsiz!\n"
        "Bu yerda siz eng yangi modlangan o'yinlar, pullik ilovalar va dasturlarni bepul yuklab olishingiz mumkin.\n\n"
        "Kerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

# --- Obunani qayta tekshirish tugmasi ---
@user_dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    user_id = callback.from_user.id
    unsub = await check_user_subscriptions(user_id)

    if unsub:
        await callback.answer("❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
        try:
            await callback.message.edit_text(
                "⚠️ <b>Iltimos, avval barcha kanallarga a'zo bo'ling:</b>",
                parse_mode="HTML",
                reply_markup=get_subscription_keyboard(unsub)
            )
        except Exception:
            pass
    else:
        await callback.answer("✅ Rahmat! Obuna tasdiqlandi.", show_alert=False)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>Xush kelibsiz!</b>\n\nQuyidagi menyu orqali kerakli bo'limni tanlang:",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )

# --- 🎮 O'yinlar bo'limi ---
@user_dp.message(F.text == "🎮 O'yinlar")
async def menu_games(message: Message):
    unsub = await check_user_subscriptions(message.from_user.id)
    if unsub:
        await message.answer("⚠️ Botdan foydalanish uchun homiy kanallarga a'zo bo'ling:", reply_markup=get_subscription_keyboard(unsub))
        return

    genres = db.get_genres("game")
    buttons = []
    
    row = []
    for g in genres:
        row.append(InlineKeyboardButton(text=f"🎲 #{g}", callback_data=f"genre_game_{g}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="🔥 Barcha so'nggi o'yinlar", callback_data="all_games_0")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("🎮 <b>O'yinlar bo'limi</b>\n\nKerakli janrni tanlang yoki barcha o'yinlarni ko'ring:", parse_mode="HTML", reply_markup=kb)

# --- 📱 Ilovalar bo'limi ---
@user_dp.message(F.text == "📱 Ilovalar")
async def menu_apps(message: Message):
    unsub = await check_user_subscriptions(message.from_user.id)
    if unsub:
        await message.answer("⚠️ Botdan foydalanish uchun homiy kanallarga a'zo bo'ling:", reply_markup=get_subscription_keyboard(unsub))
        return

    genres = db.get_genres("app")
    buttons = []
    row = []
    for g in genres:
        row.append(InlineKeyboardButton(text=f"📁 #{g}", callback_data=f"genre_app_{g}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="⚡ Barcha so'nggi ilovalar", callback_data="all_apps_0")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("📱 <b>Ilovalar bo'limi</b>\n\nKerakli ruknni tanlang yoki barcha ilovalarni ko'ring:", parse_mode="HTML", reply_markup=kb)

# --- Ro'yxatni ko'rsatish (O'yinlar yoki Ilovalar) ---
@user_dp.callback_query(F.data.startswith("all_games_") | F.data.startswith("all_apps_"))
async def cb_list_items(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    item_type = "game" if parts[1] == "games" else "app"
    offset = int(parts[2])

    items = db.get_items(item_type=item_type, limit=8, offset=offset)
    if not items:
        await callback.message.answer("Hozircha ushbu bo'limda hech narsa yo'q.")
        return

    buttons = []
    for it in items:
        buttons.append([InlineKeyboardButton(text=f"🔹 {it['title']} (v{it['version']})", callback_data=f"view_item_{it['id']}")])

    nav_row = []
    if offset > 0:
        prev_offset = max(0, offset - 8)
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"all_{parts[1]}_{prev_offset}"))
    if len(items) == 8:
        next_offset = offset + 8
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"all_{parts[1]}_{next_offset}"))
    if nav_row:
        buttons.append(nav_row)

    title_str = "🎮 O'yinlar ro'yxati:" if item_type == "game" else "📱 Ilovalar ro'yxati:"
    await callback.message.answer(f"<b>{title_str}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# --- Janr bo'yicha ko'rsatish ---
@user_dp.callback_query(F.data.startswith("genre_"))
async def cb_genre_items(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_", 2)
    item_type = parts[1]
    genre = parts[2]

    items = db.get_items(item_type=item_type, genre=genre, limit=10)
    if not items:
        await callback.message.answer(f"#{genre} janrida hali fayl qo'shilmagan.")
        return

    buttons = []
    for it in items:
        buttons.append([InlineKeyboardButton(text=f"🔹 {it['title']} (v{it['version']})", callback_data=f"view_item_{it['id']}")])

    await callback.message.answer(
        f"🏷 <b>#{html.escape(genre)}</b> ruknidagi fayllar:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

# --- O'yin / Ilova kartochkasini chiqarish ---
@user_dp.callback_query(F.data.startswith("view_item_"))
async def cb_view_item(callback: CallbackQuery):
    await callback.answer()
    item_id = int(callback.data.split("_")[2])
    item = db.get_item(item_id)
    if not item:
        await callback.message.answer("Kechirasiz, bu fayl topilmadi.")
        return

    await send_item_card(callback.message, item)

async def send_item_card(message: Message, item: dict):
    title = html.escape(item['title'])
    desc = html.escape(item['description'])
    genre = html.escape(item['genre'])
    android_ver = html.escape(item['android_ver'])
    version = html.escape(item['version'])
    mod_info = html.escape(item['mod_info'])

    caption = (
        f"🎮 <b>{title}</b>\n\n"
        f"📝 <b>Ta'rif:</b> {desc}\n\n"
        f"ℹ️ <b>Janr:</b> #{genre}\n"
        f"📱 <b>Android:</b> {android_ver}\n"
        f"✅ <b>Versiya:</b> {version}\n"
        f"🔑 <b>Mod:</b> {mod_info}\n"
    )

    buttons = []
    if item['file_id']:
        buttons.append([InlineKeyboardButton(text="📥 Faylni yuklab olish (APK)", callback_data=f"download_{item['id']}")])
    
    if item['channel_id'] and str(item['channel_id']).startswith("@") and item['post_message_id']:
        ch_name = item['channel_id'].replace("@", "")
        post_url = f"https://t.me/{ch_name}/{item['post_message_id']}"
        buttons.append([InlineKeyboardButton(text="↗️ Kanaldagi postni ko'rish", url=post_url)])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    if item['photo_file_id']:
        await message.answer_photo(photo=item['photo_file_id'], caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text=caption, parse_mode="HTML", reply_markup=kb)

# --- Faylni yuklab berish ---
@user_dp.callback_query(F.data.startswith("download_"))
async def cb_download_file(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    item = db.get_item(item_id)
    if not item:
        await callback.answer("Fayl topilmadi!", show_alert=True)
        return

    if item['file_id']:
        await callback.answer("Fayl yuborilmoqda, kuting...")
        await user_bot.send_document(
            chat_id=callback.from_user.id,
            document=item['file_id'],
            caption=f"📁 <b>{html.escape(item['title'])} (v{html.escape(item['version'])})</b>\n\n@IskndrvGames_bot orqali yuklab olindi.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("Fayl kanalda joylashgan.", show_alert=True)

# --- 🔍 Qidiruv ---
@user_dp.message(F.text == "🔍 Qidiruv")
async def start_search(message: Message, state: FSMContext):
    await state.set_state(UserSearch.waiting_query)
    await message.answer("Qidirayotgan o'yin yoki dastur <b>nomini</b> yozing (Masalan: <code>Simulator</code> yoki <code>Minecraft</code>):", parse_mode="HTML")

@user_dp.message(UserSearch.waiting_query)
async def process_search(message: Message, state: FSMContext):
    query = message.text.strip()
    await state.clear()
    items = db.get_items(query=query, limit=10)

    if not items:
        await message.answer(f"🔍 '<b>{html.escape(query)}</b>' bo'yicha hech qanday natija topilmadi.", parse_mode="HTML")
        return

    buttons = []
    for it in items:
        icon = "🎮" if it['item_type'] == "game" else "📱"
        buttons.append([InlineKeyboardButton(text=f"{icon} {it['title']} (v{it['version']})", callback_data=f"view_item_{it['id']}")])

    await message.answer(
        f"🔍 '<b>{html.escape(query)}</b>' bo'yicha topilgan natijalar:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

# --- Kanaldan Avtomatik O'yin/Ilovalarni Qabul Qilish ---
@user_dp.channel_post()
async def auto_capture_channel_post(message: Message):
    text = message.text or message.caption or ""
    photo_id = message.photo[-1].file_id if message.photo else None
    file_id = message.document.file_id if message.document else None
    file_name = message.document.file_name if message.document else None
    
    # Agar faqat fayl (APK) yuborilgan bo'lsa va avvalgi postga biriktirish kerak bo'lsa:
    if file_id and (not text or len(text) < 15):
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM items WHERE file_id IS NULL ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE items SET file_id = ?, file_name = ? WHERE id = ?", (file_id, file_name, row['id']))
            conn.commit()
            logging.info(f"Fayl #{row['id']} postiga avtomatik biriktirildi: {file_name}")
        conn.close()
        return

    if not text:
        return

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return

    first_line = lines[0]
    title = first_line.split("—")[0].split("-")[0].strip()
    desc = first_line[len(title):].lstrip("— -").strip() if len(title) < len(first_line) else "Ajoyib o'yin"
    if not desc:
        desc = "Ajoyib o'yin"

    # Janrni topish
    genre = "boshqa"
    for word in text.split():
        if word.startswith("#") and word.lower() not in ["#games", "#apk", "#app", "#mod", "#ilova"]:
            genre = word.replace("#", "").strip()
            break

    # Versiya
    version = "1.0"
    m_ver = re.search(r'Versiya:\s*([^\n\r]+)', text, re.IGNORECASE)
    if m_ver:
        version = m_ver.group(1).strip()

    # Android
    android_ver = "Barcha versiyalar"
    m_and = re.search(r'Android(?:\s*versiyasi)?:\s*([^\n\r]+)', text, re.IGNORECASE)
    if m_and:
        android_ver = m_and.group(1).strip()

    # Mod
    mod_info = "Mod / To'liq versiya"
    m_mod = re.search(r'Mod(?:ifikatsiyalar)?:\s*([^\n\r]+)', text, re.IGNORECASE)
    if m_mod:
        mod_info = m_mod.group(1).strip()

    item_type = "app" if any(w in text.lower() for w in ["dastur", "ilova", "#app", "program"]) else "game"

    db.add_item(
        item_type=item_type,
        title=title,
        description=desc,
        genre=genre,
        android_ver=android_ver,
        version=version,
        mod_info=mod_info,
        photo_file_id=photo_id,
        file_id=file_id,
        file_name=file_name,
        channel_id=f"@{message.chat.username}" if message.chat.username else str(message.chat.id),
        post_message_id=message.message_id
    )
    logging.info(f"Kanaldan avtomatik yangi {item_type} qo'shildi: {title}")

# --- ℹ️ Ma'lumot ---
@user_dp.message(F.text == "ℹ️ Ma'lumot")
async def menu_info(message: Message):
    text = (
        "ℹ️ <b>Iskndrv Games Ekotizimi</b>\n\n"
        "• Eng sara APK o'yinlar va ilovalar ✅\n"
        "• Premium va mod versiyalar mutlaqo bepul ✅\n"
        "• Yangi o'yinlar doimiy joylab boriladi 🎮\n\n"
        "📢 <b>Rasmiy kanal:</b> @iskndrv_games\n"
        "🤖 <b>Rasmiy bot:</b> @IskndrvGames_bot\n"
        "👨‍💻 <b>Administrator:</b> @iskandarov_developer"
    )
    await message.answer(text, parse_mode="HTML")
