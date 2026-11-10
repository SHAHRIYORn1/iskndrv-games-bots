import asyncio
import logging
import html
import re
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

admin_bot = Bot(token=config.ADMIN_BOT_TOKEN)
admin_dp = Dispatcher()

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

# --- Klaviaturalar ---
def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Kanalga post joylash (O'yin/Ilova)")],
            [KeyboardButton(text="🔗 Majburiy obuna kanallari"), KeyboardButton(text="📢 Xabar tarqatish (Broadcast)")],
            [KeyboardButton(text="🎮 O'yin va Ilovalar ro'yxati"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="⚙️ Standart kanal sozlash")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

# --- Start & Auth ---
@admin_dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = html.escape(message.from_user.full_name or "")

    if db.is_admin(user_id):
        db.add_admin(user_id, username, full_name)
        await message.answer(
            f"Salom, Administrator <b>{full_name}</b>!\n\n"
            f"Boshqaruv paneliga xush kelibsiz. Bu yerdan o'yin/ilovalarni kanalga chiroyli formatda joylashingiz, "
            f"majburiy obuna kanallarini boshqarishingiz va foydalanuvchilarga xabar tarqatishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            "⛔ <b>Kechirasiz, bu bot faqat administratorlar uchun!</b>\n\n"
            "Agar siz bot egasi bo'lsangiz, parolni yuboring:\n"
            "<code>/setadmin PAROL</code>",
            parse_mode="HTML"
        )

@admin_dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip() == config.ADMIN_SECRET_KEY:
        db.add_admin(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
        await message.answer(
            "✅ <b>Tabriklaymiz! Siz muvaffaqiyatli administrator bo'ldingiz!</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Noto'g'ri parol!")

@admin_dp.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=get_admin_keyboard())

# --- Statistika ---
@admin_dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not db.is_admin(message.from_user.id):
        return
    users_cnt = db.count_users()
    games_cnt = db.count_items("game")
    apps_cnt = db.count_items("app")
    channels = db.get_mandatory_channels()

    text = (
        "📊 <b>Tizim Statistikasi:</b>\n\n"
        f"👥 Asosiy bot foydalanuvchilari: <b>{users_cnt}</b> ta\n"
        f"🎮 Qo'shilgan o'yinlar: <b>{games_cnt}</b> ta\n"
        f"📱 Qo'shilgan ilovalar: <b>{apps_cnt}</b> ta\n"
        f"🔗 Majburiy kanallar soni: <b>{len(channels)}</b> ta\n"
    )
    await message.answer(text, parse_mode="HTML")

# --- Majburiy Kanallar Boshqaruvi ---
@admin_dp.message(F.text == "🔗 Majburiy obuna kanallari")
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

@admin_dp.callback_query(F.data == "toggle_force_sub")
async def cb_toggle_force_sub(callback: CallbackQuery):
    current = db.get_setting("force_sub_enabled", "0")
    new_val = "0" if current == "1" else "1"
    db.set_setting("force_sub_enabled", new_val)
    
    msg = "Majburiy obuna yoqildi! Endi foydalanuvchilar kanallarga a'zo bo'lmaguncha botdan foydalana olmaydi." if new_val == "1" else "Majburiy obuna o'chirildi! Endi bot hech kimdan kanalga a'zo bo'lishni talab qilmaydi."
    await callback.answer(msg, show_alert=True)
    await callback.message.delete()
    # Yangilangan ko'rinishni qayta chiqarish
    await manage_channels(callback.message)

@admin_dp.callback_query(F.data == "add_new_channel")
async def cb_add_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ChannelManage.waiting_channel)
    await callback.message.answer(
        "Kanal username'ini yoki ID sini yuboring (Masalan: <code>@iskndrv_games</code> yoki <code>-1004300321035</code>):\n\n"
        "<i>Eslatma: Kanalga ikkala botni ham Admin qilib qo'shganingizga ishonch hosil qiling!</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@admin_dp.message(ChannelManage.waiting_channel)
async def process_channel_id(message: Message, state: FSMContext):
    chat_input = clean_channel_input(message.text.strip())
    try:
        chat = await admin_bot.get_chat(chat_input)
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
        await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi: <b>{html.escape(title)}</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())

    except Exception as e:
        await state.update_data(channel_id=chat_input, title=chat_input, username=chat_input if chat_input.startswith("@") else "")
        await state.set_state(ChannelManage.waiting_invite_link)
        await message.answer(
            f"⚠️ Bot bu kanalni to'g'ridan-to'g'ri o'qiy olmadi ({html.escape(str(e))}).\n"
            "Iltimos, ushbu kanalga taklif havolasini (link) yuboring:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

@admin_dp.message(ChannelManage.waiting_invite_link)
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
    await message.answer("✅ Kanal qo'shildi va majburiy ro'yxatga kiritildi!", reply_markup=get_admin_keyboard())

@admin_dp.callback_query(F.data.startswith("del_chan_"))
async def cb_delete_channel(callback: CallbackQuery):
    chan_db_id = callback.data.split("_")[2]
    db.remove_channel(chan_db_id)
    await callback.answer("Kanal o'chirildi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# --- Standart Kanal Sozlash ---
@admin_dp.message(F.text == "⚙️ Standart kanal sozlash")
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
@admin_dp.message(F.text == "📝 Kanalga post joylash (O'yin/Ilova)")
async def start_post_creation(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 O'yin (Game)", callback_data="type_game"),
         InlineKeyboardButton(text="📱 Ilova (App)", callback_data="type_app")]
    ])
    await message.answer("Qaysi turdagi post joylamoqchisiz?", reply_markup=kb)

@admin_dp.callback_query(F.data.in_(["type_game", "type_app"]))
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

@admin_dp.message(PostCreation.target_channel)
async def process_target_channel(message: Message, state: FSMContext):
    ch = clean_channel_input(message.text.strip())
    await state.update_data(target_channel=ch)
    db.set_setting("default_channel", ch)
    await state.set_state(PostCreation.photo)
    await message.answer("Ajoyib! Endi post uchun <b>rasm</b> yuboring (banner/screenshot):", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@admin_dp.message(PostCreation.photo, F.photo)
async def process_post_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(PostCreation.title)
    await message.answer(
        "O'yin / ilovaning <b>nomini</b> kiriting:\n"
        "(Masalan: <code>Construction Simulator 3</code>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.title)
async def process_post_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(PostCreation.description)
    await message.answer(
        "Qisqacha <b>ta'rif / ma'lumot</b> kiriting:\n"
        "(Masalan: <i>katta qurilish maydonini simulyatsiya qiluvchi ajoyib o'yin. Turli xil vazifalar, litsenziyali texnika va go'zal grafika.</i>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.description)
async def process_post_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(PostCreation.genre)
    await message.answer(
        "<b>Janr yoki rukn</b> kiriting:\n"
        "(Masalan: <code>simulyatorlar</code>, <code>poyga</code>, <code>jangari</code>, <code>foydali</code>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.genre)
async def process_post_genre(message: Message, state: FSMContext):
    genre = message.text.strip().replace("#", "")
    await state.update_data(genre=genre)
    await state.set_state(PostCreation.android_ver)
    await message.answer(
        "Kerakli <b>Android versiyasi</b>:\n"
        "(Masalan: <code>9.0+</code> yoki <code>7.0+</code> yoki <code>Barcha versiyalar</code>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.android_ver)
async def process_post_android_ver(message: Message, state: FSMContext):
    android_ver = message.text.strip()
    await state.update_data(android_ver=android_ver)
    await state.set_state(PostCreation.version)
    await message.answer(
        "O'yin / ilova <b>versiyasi</b>:\n"
        "(Masalan: <code>1.1.1473</code>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.version)
async def process_post_ver(message: Message, state: FSMContext):
    version = message.text.strip()
    await state.update_data(version=version)
    await state.set_state(PostCreation.mod_info)
    await message.answer(
        "<b>Modifikatsiyalar (Mod)</b> haqida ma'lumot:\n"
        "(Masalan: <code>xarid qilingan (449₽) - ko'p pul</code> yoki <code>Original / Bepul</code>)",
        parse_mode="HTML"
    )

@admin_dp.message(PostCreation.mod_info)
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

@admin_dp.message(PostCreation.apk_file, F.document)
async def process_post_apk(message: Message, state: FSMContext):
    file_id = message.document.file_id
    file_name = message.document.file_name or "app.apk"
    await state.update_data(file_id=file_id, file_name=file_name)
    await show_post_preview(message, state)

@admin_dp.message(PostCreation.apk_file, F.text == "⏩ Faylsiz (O'tkazib yuborish)")
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

@admin_dp.callback_query(PostCreation.confirm, F.data == "publish_post")
async def cb_publish_post(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Yuklanmoqda...")
    data = await state.get_data()
    target_ch = clean_channel_input(data['target_channel'])
    caption = data['final_caption']
    photo_id = data['photo']
    file_id = data.get('file_id')
    file_name = data.get('file_name')

    try:
        sent_post = await admin_bot.send_photo(
            chat_id=target_ch,
            photo=photo_id,
            caption=caption
        )
        post_msg_id = sent_post.message_id

        if file_id:
            await admin_bot.send_document(
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
            f"Asosiy bot (@IskndrvGames_bot) orqali ham buni ko'rish mumkin!",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Xatolik yuz berdi:</b> {html.escape(str(e))}\n\n"
            f"Eslatma: Bot <b>{html.escape(target_ch)}</b> kanalida Admin qilinganiga va xabar yozish huquqi borligiga ishonch hosil qiling!",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

@admin_dp.callback_query(PostCreation.confirm, F.data == "cancel_post")
async def cb_cancel_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Post bekor qilindi.", reply_markup=get_admin_keyboard())

# --- O'yinlar va Ilovalar ro'yxati ---
@admin_dp.message(F.text == "🎮 O'yin va Ilovalar ro'yxati")
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

@admin_dp.callback_query(F.data.startswith("del_item_"))
async def cb_delete_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    db.delete_item(item_id)
    await callback.answer("O'chirildi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# --- Broadcast (Foydalanuvchilarga xabar tarqatish) ---
@admin_dp.message(F.text == "📢 Xabar tarqatish (Broadcast)")
async def start_broadcast(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.waiting_message)
    await message.answer(
        "Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (Matn, rasm, video yoki havola bo'lishi mumkin):",
        reply_markup=get_cancel_keyboard()
    )

@admin_dp.message(BroadcastState.waiting_message)
async def process_broadcast(message: Message, state: FSMContext):
    users = db.get_all_users()
    await state.clear()

    if not users:
        await message.answer("Bazada hali foydalanuvchilar mavjud emas.", reply_markup=get_admin_keyboard())
        return

    status_msg = await message.answer(f"⏳ Xabar tarqatish boshlandi... Jami: {len(users)} ta foydalanuvchi.")
    sent_count = 0
    fail_count = 0

    from user_bot import user_bot
    for u in users:
        uid = u['user_id']
        try:
            await user_bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"Yetkazildi: <b>{sent_count}</b>\n"
        f"Yetib bormadi (bloklagan): <b>{fail_count}</b>",
        parse_mode="HTML"
    )
