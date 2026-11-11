import asyncio
import logging
import html
import re
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
import config

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

def clean_channel_input(inp: str) -> str:
    inp = inp.strip()
    m = re.match(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)/?$', inp)
    if m and not m.group(1).startswith('+'):
        return f"@{m.group(1)}"
    if inp.startswith('@'):
        return inp
    return inp

# --- FSM States ---
class PostCreation(StatesGroup):
    target_channel = State()
    item_type = State()
    photo = State()
    title = State()
    description = State()
    genre = State()
    android_ver = State()
    version = State()
    mod_info = State()
    apk_file = State()
    confirm = State()

class ChannelManage(StatesGroup):
    waiting_channel = State()
    waiting_invite_link = State()

class BroadcastState(StatesGroup):
    waiting_message = State()

class AdminAddState(StatesGroup):
    waiting_user_id = State()

class UserSearch(StatesGroup):
    waiting_query = State()

# --- Klaviaturalar ---
def get_user_menu(user_id: int):
    kb = [
        [KeyboardButton(text="🎮 O'yinlar"), KeyboardButton(text="📱 Ilovalar")],
        [KeyboardButton(text="🔍 Qidiruv"), KeyboardButton(text="ℹ️ Ma'lumot")]
    ]
    if db.is_admin(user_id):
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_menu(user_id: int):
    kb = [
        [KeyboardButton(text="📝 Kanalga post joylash (O'yin/Ilova)")],
        [KeyboardButton(text="🔗 Majburiy obuna kanallari"), KeyboardButton(text="📢 Xabar tarqatish (Broadcast)")],
        [KeyboardButton(text="👥 Adminlar boshqaruvi"), KeyboardButton(text="🎮 O'yin va Ilovalar ro'yxati")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⚙️ Standart kanal sozlash")],
        [KeyboardButton(text="⬅️ Foydalanuvchi menyusi")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

# --- Majburiy Obunani Tekshirish ---
async def check_user_subscriptions(user_id: int):
    if db.is_admin(user_id):
        return []

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
            member = await bot.get_chat_member(chat_id=target_chat_id, user_id=user_id)
            if member.status in ['creator', 'administrator', 'member', 'restricted']:
                continue
            else:
                unsubscribed.append(ch)
        except Exception as e:
            logging.warning(f"Kanal obunasini tekshirish ogohlantirishi ({cid}): {e}")
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
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = html.escape(message.from_user.full_name or "")

    # Bazaga foydalanuvchini qo'shish
    db.add_user(user_id, username, full_name)
    if user_id == config.OWNER_ID:
        db.add_admin(user_id, username, full_name)

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

    admin_hint = "\n<i>(Siz administratorsiz, boshqaruv uchun '👑 Admin Panel' tugmasini bosing)</i>" if db.is_admin(user_id) else ""
    await message.answer(
        f"Assalomu alaykum, <b>{full_name}</b>!\n\n"
        f"🎮 <b>Iskndrv Games</b> rasmiy botiga xush kelibsiz!{admin_hint}\n"
        "Bu yerda siz eng yangi modlangan o'yinlar, pullik ilovalar va dasturlarni bepul yuklab olishingiz mumkin.\n\n"
        "Kerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=get_user_menu(user_id)
    )

# --- Obunani qayta tekshirish tugmasi ---
@dp.callback_query(F.data == "check_sub")
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
            reply_markup=get_user_menu(user_id)
        )

# --- Admin Parol orqali kirish (/setadmin) ---
@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip() == config.ADMIN_SECRET_KEY:
        user_id = message.from_user.id
        username = message.from_user.username or ""
        full_name = html.escape(message.from_user.full_name or "")
        db.add_admin(user_id, username, full_name)
        await message.answer(
            "✅ <b>Tabriklaymiz! Siz muvaffaqiyatli administrator bo'ldingiz!</b>\n"
            "Pastdagi '👑 Admin Panel' tugmasi orqali boshqaruvga o'tishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=get_user_menu(user_id)
        )
    else:
        await message.answer("❌ Noto'g'ri maxfiy parol!")

# --- Bekor qilish ---
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if db.is_admin(user_id):
        await message.answer("Amal bekor qilindi.", reply_markup=get_admin_menu(user_id))
    else:
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_menu(user_id))

# --- Admin Panelga o'tish ---
@dp.message(F.text == "👑 Admin Panel")
@dp.message(Command("admin"))
@dp.message(Command("admins"))
async def open_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if not db.is_admin(user_id):
        await message.answer("⛔ Bu bo'lim faqat administratorlar uchun!")
        return

    role = "👑 Bosh Administrator" if user_id == config.OWNER_ID else "👮‍♂️ Administrator"
    await message.answer(
        f"Xush kelibsiz, {role}!\n\n"
        "Admin boshqaruv panelidasiz. Kerakli amalni tanlang:",
        reply_markup=get_admin_menu(user_id)
    )

@dp.message(F.text == "⬅️ Foydalanuvchi menyusi")
async def back_to_user_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy foydalanuvchi menyusiga qaytdingiz:", reply_markup=get_user_menu(message.from_user.id))

# --- 👥 Multi-Admin Boshqaruvi ---
@dp.message(F.text == "👥 Adminlar boshqaruvi")
async def manage_admins(message: Message):
    if not db.is_admin(message.from_user.id):
        return

    admins = db.get_all_admins()
    is_owner = (message.from_user.id == config.OWNER_ID)
    
    text = (
        "👥 <b>Administratorlar ro'yxati (Multi-Admin):</b>\n\n"
        f"🔐 <b>Joriy admin paroli:</b> <code>{config.ADMIN_SECRET_KEY}</code>\n"
        f"<i>Yangi admin qo'shish uchun unga shu buyruqni bering:</i>\n"
        f"<code>/setadmin {config.ADMIN_SECRET_KEY}</code>\n\n"
        "<b>Barcha adminlar:</b>\n"
    )

    buttons = []
    found_owner = False
    for idx, adm in enumerate(admins, 1):
        uid = adm['user_id']
        name = html.escape(adm['full_name'] or adm['username'] or str(uid))
        role_badge = "👑 Bosh Admin" if uid == config.OWNER_ID else "👮‍♂️ Admin"
        if uid == config.OWNER_ID:
            found_owner = True
        text += f"{idx}. {role_badge}: <b>{name}</b> (ID: <code>{uid}</code>)\n"

        if is_owner and uid != config.OWNER_ID:
            buttons.append([InlineKeyboardButton(text=f"🗑 O'chirish: {name[:15]}", callback_data=f"del_admin_{uid}")])

    if not found_owner and is_owner:
        text += f"👑 Bosh Admin: <b>Siz</b> (ID: <code>{config.OWNER_ID}</code>)\n"

    if is_owner:
        buttons.append([InlineKeyboardButton(text="➕ ID orqali admin qo'shish", callback_data="add_admin_by_id")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "add_admin_by_id")
async def cb_add_admin_by_id(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.OWNER_ID:
        await callback.answer("Faqat Bosh Admin yangi admin qo'sha oladi!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminAddState.waiting_user_id)
    await callback.message.answer(
        "Admin qilmoqchi bo'lgan foydalanuvchining <b>Telegram ID raqamini</b> yuboring (Masalan: <code>123456789</code>):\n\n"
        "<i>(Yoki unga maxfiy parolni berishingiz mumkin: <code>/setadmin " + config.ADMIN_SECRET_KEY + "</code>)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(AdminAddState.waiting_user_id)
async def process_admin_id(message: Message, state: FSMContext):
    inp = message.text.strip()
    if not inp.isdigit():
        await message.answer("Iltimos, faqat raqamlardan iborat Telegram ID yuboring:", reply_markup=get_cancel_keyboard())
        return

    new_admin_id = int(inp)
    db.add_admin(new_admin_id, "", f"Admin #{new_admin_id}")
    await state.clear()
    await message.answer(
        f"✅ <b>Yangi administrator muvaffaqiyatli qo'shildi!</b> (ID: <code>{new_admin_id}</code>)\n"
        "Endi u ham bot orqali kanalga post joylay oladi va boshqara oladi.",
        parse_mode="HTML",
        reply_markup=get_admin_menu(message.from_user.id)
    )

@dp.callback_query(F.data.startswith("del_admin_"))
async def cb_delete_admin(callback: CallbackQuery):
    if callback.from_user.id != config.OWNER_ID:
        await callback.answer("Faqat Bosh Admin adminlarni o'chira oladi!", show_alert=True)
        return
    target_id = int(callback.data.split("_")[2])
    if target_id == config.OWNER_ID:
        await callback.answer("Bosh Adminni o'chirib bo'lmaydi!", show_alert=True)
        return

    db.remove_admin(target_id)
    await callback.answer("Admin muvaffaqiyatli o'chirildi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# --- Statistika ---
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not db.is_admin(message.from_user.id):
        return
    users_cnt = db.count_users()
    games_cnt = db.count_items("game")
    apps_cnt = db.count_items("app")
    channels = db.get_mandatory_channels()
    admins = db.get_all_admins()

    text = (
        "📊 <b>Tizim Statistikasi:</b>\n\n"
        f"👥 Bot foydalanuvchilari soni: <b>{users_cnt}</b> ta\n"
        f"👮‍♂️ Administratorlar soni: <b>{len(admins)}</b> ta\n"
        f"🎮 Qo'shilgan o'yinlar: <b>{games_cnt}</b> ta\n"
        f"📱 Qo'shilgan ilovalar: <b>{apps_cnt}</b> ta\n"
        f"🔗 Majburiy kanallar soni: <b>{len(channels)}</b> ta\n"
    )
    await message.answer(text, parse_mode="HTML")

# --- Majburiy Kanallar Boshqaruvi ---
@dp.message(F.text == "🔗 Majburiy obuna kanallari")
async def manage_channels(message: Message):
    if not db.is_admin(message.from_user.id):
        return
    channels = db.get_mandatory_channels()
    buttons = []
    
    is_sub_enabled = db.get_setting("force_sub_enabled", "0")
    status_label = "🟢 YOQILGAN (Hamma obuna bo'lishi shart)" if is_sub_enabled == "1" else "🔴 O'CHIRILGAN (Hech kimdan so'ralmaydi)"
    toggle_text = "🔴 Obuna tekshiruvini o'chirish" if is_sub_enabled == "1" else "🟢 Obuna tekshiruvini yoqish"
    
    text = (
        f"🔗 <b>Majburiy obuna sozlamalari:</b>\n\n"
        f"Holat: <b>{status_label}</b>\n\n"
        f"<b>Kanallar ro'yxati:</b>\n"
    )

    if not channels:
        text += "<i>Hozircha kanallar qo'shilmagan.</i>\n"
    else:
        for idx, ch in enumerate(channels, 1):
            title = html.escape(ch['title'] or ch['username'] or ch['channel_id'])
            text += f"{idx}. <b>{title}</b> ({ch['channel_id']})\n"
            buttons.append([InlineKeyboardButton(text=f"🗑 O'chirish: {ch['title'][:20]}", callback_data=f"del_chan_{ch['id']}")])

    buttons.append([InlineKeyboardButton(text=toggle_text, callback_data="toggle_force_sub")])
    buttons.append([InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="add_new_channel")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "toggle_force_sub")
async def cb_toggle_force_sub(callback: CallbackQuery):
    current = db.get_setting("force_sub_enabled", "0")
    new_val = "0" if current == "1" else "1"
    db.set_setting("force_sub_enabled", new_val)
    
    msg = "Majburiy obuna yoqildi! Endi foydalanuvchilar kanallarga a'zo bo'lmaguncha botdan foydalana olmaydi." if new_val == "1" else "Majburiy obuna o'chirildi! Endi bot hech kimdan kanalga a'zo bo'lishni talab qilmaydi."
    await callback.answer(msg, show_alert=True)
    await callback.message.delete()
    await manage_channels(callback.message)

@dp.callback_query(F.data == "add_new_channel")
async def cb_add_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ChannelManage.waiting_channel)
    await callback.message.answer(
        "Kanal username'ini yoki ID sini yuboring (Masalan: <code>@iskndrv_games</code> yoki <code>-1004300321035</code>):\n\n"
        "<i>Eslatma: Kanalga botni Admin qilib qo'shganingizga ishonch hosil qiling!</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(ChannelManage.waiting_channel)
async def process_channel_id(message: Message, state: FSMContext):
    chat_input = clean_channel_input(message.text.strip())
    try:
        chat = await bot.get_chat(chat_input)
        title = chat.title or "Nomsiz kanal"
        username = chat.username or ""
        invite_link = chat.invite_link or ""
        if not invite_link and username:
            invite_link = f"https://t.me/{username}"

        db.add_channel(
            channel_id=str(chat.id),
            title=title,
            username=f"@{username}" if username else "",
            invite_link=invite_link or f"https://t.me/{username}",
            is_mandatory=1
        )
        await state.clear()
        await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi: <b>{html.escape(title)}</b>", parse_mode="HTML", reply_markup=get_admin_menu(message.from_user.id))

    except Exception as e:
        await state.update_data(channel_id=chat_input, title=chat_input, username=chat_input if chat_input.startswith("@") else "")
        await state.set_state(ChannelManage.waiting_invite_link)
        await message.answer(
            f"⚠️ Bot bu kanalni to'g'ridan-to'g'ri o'qiy olmadi ({html.escape(str(e))}).\n"
            "Iltimos, ushbu kanalga taklif havolasini (link) yuboring:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

@dp.message(ChannelManage.waiting_invite_link)
async def process_channel_invite(message: Message, state: FSMContext):
    invite_link = message.text.strip()
    data = await state.get_data()
    channel_id = data.get('channel_id')
    title = data.get('title')
    username = data.get('username')

    db.add_channel(
        channel_id=channel_id,
        title=title,
        username=username,
        invite_link=invite_link,
        is_mandatory=1
    )
    await state.clear()
    await message.answer("✅ Kanal qo'shildi va majburiy ro'yxatga kiritildi!", reply_markup=get_admin_menu(message.from_user.id))

@dp.callback_query(F.data.startswith("del_chan_"))
async def cb_delete_channel(callback: CallbackQuery):
    chan_db_id = callback.data.split("_")[2]
    db.remove_channel(chan_db_id)
    await callback.answer("Kanal o'chirildi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# --- Standart Kanal Sozlash ---
@dp.message(F.text == "⚙️ Standart kanal sozlash")
async def set_default_channel_prompt(message: Message):
    if not db.is_admin(message.from_user.id):
        return
    current = db.get_setting("default_channel", "@iskndrv_games")
    await message.answer(
        f"Hozirgi standart post kanali: <b>{html.escape(current)}</b>\n\n"
        "O'zgartirish uchun kanal username yoki ID sini yuboring (Masalan: <code>@iskndrv_games</code>):",
        parse_mode="HTML"
    )

# --- Post Yaratish va Joylash (Wizard) ---
@dp.message(F.text == "📝 Kanalga post joylash (O'yin/Ilova)")
async def start_post_creation(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 O'yin (Game)", callback_data="type_game"),
         InlineKeyboardButton(text="📱 Ilova (App)", callback_data="type_app")]
    ])
    await message.answer("Qaysi turdagi post joylamoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.in_(["type_game", "type_app"]))
async def cb_select_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    item_type = "game" if callback.data == "type_game" else "app"
    await state.update_data(item_type=item_type)
    
    default_ch = db.get_setting("default_channel", "@iskndrv_games")
    if default_ch:
        await state.update_data(target_channel=default_ch)
        await state.set_state(PostCreation.photo)
        await callback.message.answer(
            f"Tanlangan kanal: <b>{html.escape(default_ch)}</b>\n\n"
            f"Endi post uchun <b>rasm</b> yuboring (banner/screenshot):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    else:
        await state.set_state(PostCreation.target_channel)
        await callback.message.answer(
            "Post qaysi kanalga joylansin?\n"
            "Kanal username'ini yuboring (Masalan: <code>@iskndrv_games</code>):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )

@dp.message(PostCreation.target_channel)
async def process_target_channel(message: Message, state: FSMContext):
    ch = clean_channel_input(message.text.strip())
    await state.update_data(target_channel=ch)
    db.set_setting("default_channel", ch)
    await state.set_state(PostCreation.photo)
    await message.answer("Ajoyib! Endi post uchun <b>rasm</b> yuboring (banner/screenshot):", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(PostCreation.photo, F.photo)
async def process_post_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(PostCreation.title)
    await message.answer(
        "O'yin / ilovaning <b>nomini</b> kiriting:\n"
        "(Masalan: <code>Construction Simulator 3</code>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.title)
async def process_post_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(PostCreation.description)
    await message.answer(
        "Qisqacha <b>ta'rif / ma'lumot</b> kiriting:\n"
        "(Masalan: <i>katta qurilish maydonini simulyatsiya qiluvchi ajoyib o'yin. Turli xil vazifalar, litsenziyali texnika va go'zal grafika.</i>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.description)
async def process_post_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(PostCreation.genre)
    await message.answer(
        "<b>Janr yoki rukn</b> kiriting:\n"
        "(Masalan: <code>simulyatorlar</code>, <code>poyga</code>, <code>jangari</code>, <code>foydali</code>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.genre)
async def process_post_genre(message: Message, state: FSMContext):
    genre = message.text.strip().replace("#", "")
    await state.update_data(genre=genre)
    await state.set_state(PostCreation.android_ver)
    await message.answer(
        "Kerakli <b>Android versiyasi</b>:\n"
        "(Masalan: <code>9.0+</code> yoki <code>7.0+</code> yoki <code>Barcha versiyalar</code>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.android_ver)
async def process_post_android_ver(message: Message, state: FSMContext):
    android_ver = message.text.strip()
    await state.update_data(android_ver=android_ver)
    await state.set_state(PostCreation.version)
    await message.answer(
        "O'yin / ilova <b>versiyasi</b>:\n"
        "(Masalan: <code>1.1.1473</code>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.version)
async def process_post_ver(message: Message, state: FSMContext):
    version = message.text.strip()
    await state.update_data(version=version)
    await state.set_state(PostCreation.mod_info)
    await message.answer(
        "<b>Modifikatsiyalar (Mod)</b> haqida ma'lumot:\n"
        "(Masalan: <code>xarid qilingan (449₽) - ko'p pul</code> yoki <code>Original / Bepul</code>)",
        parse_mode="HTML"
    )

@dp.message(PostCreation.mod_info)
async def process_post_mod(message: Message, state: FSMContext):
    mod_info = message.text.strip()
    await state.update_data(mod_info=mod_info)
    await state.set_state(PostCreation.apk_file)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏩ Faylsiz (O'tkazib yuborish)")],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Endi ushbu o'yin/ilovaning <b>APK faylini</b> yuboring (Fayl/Document formatida):\n\n"
        "<i>Agar fayl juda katta bo'lsa yoki hozir yuklamoqchi bo'lmasangiz '⏩ Faylsiz (O'tkazib yuborish)' tugmasini bosing.</i>",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.message(PostCreation.apk_file, F.document)
async def process_post_apk(message: Message, state: FSMContext):
    file_id = message.document.file_id
    file_name = message.document.file_name or "app.apk"
    await state.update_data(file_id=file_id, file_name=file_name)
    await show_post_preview(message, state)

@dp.message(PostCreation.apk_file, F.text == "⏩ Faylsiz (O'tkazib yuborish)")
async def process_skip_apk(message: Message, state: FSMContext):
    await state.update_data(file_id=None, file_name=None)
    await show_post_preview(message, state)

async def show_post_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    desc = data['description']
    genre = data['genre']
    android_ver = data['android_ver']
    version = data['version']
    mod_info = data['mod_info']
    target_ch = data['target_channel']
    tag_channel = target_ch if target_ch.startswith("@") else "@iskndrv_games"

    caption = (
        f"{title} — {desc} #games {tag_channel}\n\n"
        f"ℹ️ Janr: #{genre}\n"
        f"📱 Android versiyasi: {android_ver}\n"
        f"✅ Versiya: {version}\n"
        f"🔑 Modifikatsiyalar: {mod_info}\n\n"
        f"Reaksiya bosamiz goo! @IskndrvGames_bot bizni bot"
    )
    await state.update_data(final_caption=caption)
    await state.set_state(PostCreation.confirm)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Kanalga va Bazaga joylash!", callback_data="publish_post")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_post")]
    ])

    await message.answer_photo(
        photo=data['photo'],
        caption=f"📋 <b>POST PREVIEW (Oldindan ko'rish):</b>\n\n{html.escape(caption)}\n\n"
                f"Kanal: <b>{html.escape(target_ch)}</b>\n"
                f"Fayl: <b>{html.escape(data.get('file_name') or 'Yo`q')}</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(PostCreation.confirm, F.data == "publish_post")
async def cb_publish_post(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Yuklanmoqda...")
    data = await state.get_data()
    target_ch = clean_channel_input(data['target_channel'])
    caption = data['final_caption']
    photo_id = data['photo']
    file_id = data.get('file_id')
    file_name = data.get('file_name')

    try:
        sent_post = await bot.send_photo(
            chat_id=target_ch,
            photo=photo_id,
            caption=caption
        )
        post_msg_id = sent_post.message_id

        if file_id:
            await bot.send_document(
                chat_id=target_ch,
                document=file_id,
                caption=f"📁 {data['title']} (v{data['version']})"
            )

        item_id = db.add_item(
            item_type=data['item_type'],
            title=data['title'],
            description=data['description'],
            genre=data['genre'],
            android_ver=data['android_ver'],
            version=data['version'],
            mod_info=data['mod_info'],
            photo_file_id=photo_id,
            file_id=file_id,
            file_name=file_name,
            channel_id=target_ch,
            post_message_id=post_msg_id
        )

        await state.clear()
        await callback.message.answer(
            f"✅ <b>Post muvaffaqiyatli kanalga joylandi va bazaga saqlandi!</b>\n\n"
            f"Post ID: #{item_id}\n"
            f"Kanal: {html.escape(target_ch)}\n"
            f"Foydalanuvchilar botning '🎮 O'yinlar' bo'limida buni darhol ko'rishlari mumkin!",
            parse_mode="HTML",
            reply_markup=get_admin_menu(callback.from_user.id)
        )

    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Xatolik yuz berdi:</b> {html.escape(str(e))}\n\n"
            f"Eslatma: Bot <b>{html.escape(target_ch)}</b> kanalida Admin qilinganiga va xabar yozish huquqi borligiga ishonch hosil qiling!",
            parse_mode="HTML",
            reply_markup=get_admin_menu(callback.from_user.id)
        )

@dp.callback_query(PostCreation.confirm, F.data == "cancel_post")
async def cb_cancel_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Post bekor qilindi.", reply_markup=get_admin_menu(callback.from_user.id))

# --- O'yinlar va Ilovalar ro'yxati ---
@dp.message(F.text == "🎮 O'yin va Ilovalar ro'yxati")
async def show_items_list(message: Message):
    if not db.is_admin(message.from_user.id):
        return
    items = db.get_items(limit=15)
    if not items:
        await message.answer("Bazada hali hech qanday o'yin yoki ilova yo'q.")
        return

    text = "📂 <b>Bazada mavjud so'nggi postlar:</b>\n\n"
    buttons = []
    for it in items:
        icon = "🎮" if it['item_type'] == "game" else "📱"
        text += f"{icon} <b>{html.escape(it['title'])}</b> (v{it['version']}) - #{html.escape(it['genre'])}\n"
        buttons.append([InlineKeyboardButton(text=f"🗑 O'chirish: {it['title'][:20]}", callback_data=f"del_item_{it['id']}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_item_"))
async def cb_delete_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    db.delete_item(item_id)
    await callback.answer("O'chirildi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# --- Broadcast (Foydalanuvchilarga xabar tarqatish) ---
@dp.message(F.text == "📢 Xabar tarqatish (Broadcast)")
async def start_broadcast(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.waiting_message)
    await message.answer(
        "Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (Matn, rasm, video yoki havola bo'lishi mumkin):\n\n"
        "<i>Ushbu xabar botga kirgan barcha foydalanuvchilarga to'g'ridan-to'g'ri yetkaziladi.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(BroadcastState.waiting_message)
async def process_broadcast(message: Message, state: FSMContext):
    users = db.get_all_users()
    await state.clear()

    if not users:
        await message.answer("Bazada hali foydalanuvchilar mavjud emas.", reply_markup=get_admin_menu(message.from_user.id))
        return

    status_msg = await message.answer(f"⏳ Xabar tarqatish boshlandi... Jami: {len(users)} ta foydalanuvchi.")
    sent_count = 0
    fail_count = 0

    for u in users:
        uid = u['user_id']
        try:
            if message.text:
                await bot.send_message(chat_id=uid, text=message.text)
            elif message.photo:
                await bot.send_photo(chat_id=uid, photo=message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(chat_id=uid, video=message.video.file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(chat_id=uid, document=message.document.file_id, caption=message.caption)
            elif message.audio:
                await bot.send_audio(chat_id=uid, audio=message.audio.file_id, caption=message.caption)
            elif message.voice:
                await bot.send_voice(chat_id=uid, voice=message.voice.file_id, caption=message.caption)
            else:
                await bot.send_message(chat_id=uid, text=message.text or "Yangi xabar!")
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"Yetkazildi: <b>{sent_count}</b> ta\n"
        f"Yetib bormadi (bloklagan): <b>{fail_count}</b> ta",
        parse_mode="HTML"
    )

# --- 🎮 O'yinlar bo'limi (User) ---
@dp.message(F.text == "🎮 O'yinlar")
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

# --- 📱 Ilovalar bo'limi (User) ---
@dp.message(F.text == "📱 Ilovalar")
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
@dp.callback_query(F.data.startswith("all_games_") | F.data.startswith("all_apps_"))
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
@dp.callback_query(F.data.startswith("genre_"))
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
@dp.callback_query(F.data.startswith("view_item_"))
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
@dp.callback_query(F.data.startswith("download_"))
async def cb_download_file(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    item = db.get_item(item_id)
    if not item:
        await callback.answer("Fayl topilmadi!", show_alert=True)
        return

    if item['file_id']:
        await callback.answer("Fayl yuborilmoqda, kuting...")
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=item['file_id'],
            caption=f"📁 <b>{html.escape(item['title'])} (v{html.escape(item['version'])})</b>\n\n@IskndrvGames_bot orqali yuklab olindi.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("Fayl kanalda joylashgan.", show_alert=True)

# --- 🔍 Qidiruv ---
@dp.message(F.text == "🔍 Qidiruv")
async def start_search(message: Message, state: FSMContext):
    await state.set_state(UserSearch.waiting_query)
    await message.answer("Qidirayotgan o'yin yoki dastur <b>nomini</b> yozing (Masalan: <code>Simulator</code> yoki <code>Minecraft</code>):", parse_mode="HTML")

@dp.message(UserSearch.waiting_query)
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
@dp.channel_post()
async def auto_capture_channel_post(message: Message):
    text = message.text or message.caption or ""
    photo_id = message.photo[-1].file_id if message.photo else None
    file_id = message.document.file_id if message.document else None
    file_name = message.document.file_name if message.document else None
    
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

    genre = "boshqa"
    for word in text.split():
        if word.startswith("#") and word.lower() not in ["#games", "#apk", "#app", "#mod", "#ilova"]:
            genre = word.replace("#", "").strip()
            break

    version = "1.0"
    m_ver = re.search(r'Versiya:\s*([^\n\r]+)', text, re.IGNORECASE)
    if m_ver:
        version = m_ver.group(1).strip()

    android_ver = "Barcha versiyalar"
    m_and = re.search(r'Android(?:\s*versiyasi)?:\s*([^\n\r]+)', text, re.IGNORECASE)
    if m_and:
        android_ver = m_and.group(1).strip()

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
@dp.message(F.text == "ℹ️ Ma'lumot")
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
