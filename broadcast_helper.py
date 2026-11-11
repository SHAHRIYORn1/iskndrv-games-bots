async def send_to_user(bot: Bot, chat_id: int, message: Message):
    if message.text:
        return await bot.send_message(chat_id=chat_id, text=message.text, parse_mode=None)
    elif message.photo:
        return await bot.send_photo(chat_id=chat_id, photo=message.photo[-1].file_id, caption=message.caption, parse_mode=None)
    elif message.video:
        return await bot.send_video(chat_id=chat_id, video=message.video.file_id, caption=message.caption, parse_mode=None)
    elif message.document:
        return await bot.send_document(chat_id=chat_id, document=message.document.file_id, caption=message.caption, parse_mode=None)
    elif message.audio:
        return await bot.send_audio(chat_id=chat_id, audio=message.audio.file_id, caption=message.caption, parse_mode=None)
    elif message.voice:
        return await bot.send_voice(chat_id=chat_id, voice=message.voice.file_id, caption=message.caption)
    elif message.animation:
        return await bot.send_animation(chat_id=chat_id, animation=message.animation.file_id, caption=message.caption)
    else:
        return await bot.send_message(chat_id=chat_id, text=message.text or "Yangi e'lon!", parse_mode=None)
