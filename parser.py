# parser.py
import os
import asyncio
import re
import socks
from html import escape
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityTextUrl, MessageEntityUrl, MessageEntityBold,
    MessageEntityItalic, MessageEntityCode, MessageEntityPre,
    MessageEntityMentionName, MessageEntityStrike, MessageEntityUnderline,
    MessageEntityPhone, MessageEntityEmail, MessageEntityMention, MessageEntityBotCommand
)
from config import (
    api_id, api_hash, channels_to_parse, blacklist_words,
    AUTO_MODE, STOP_WORDS, ALERT_WORDS,
    TELEGRAM_PROXY_HOST, TELEGRAM_PROXY_PORT, TELEGRAM_PROXY_TYPE,
    DUPLICATE_WINDOW_HOURS, IMAGE_DUPLICATE_THRESHOLD
)
from database import (
    post_exists, save_post, update_media_paths,
    is_exact_duplicate_recent, is_similar_image_duplicate_recent,
    get_auto_mode
)
from bot import send_post_for_approval, publish_post, send_alert

MEDIA_DIR = "media"
_PROXY_TYPES = {
    "http": socks.HTTP,
    "socks4": socks.SOCKS4,
    "socks5": socks.SOCKS5,
}
client = TelegramClient(
    'parser_session',
    api_id,
    api_hash,
    proxy=(
        _PROXY_TYPES.get(TELEGRAM_PROXY_TYPE.lower(), socks.HTTP),
        TELEGRAM_PROXY_HOST,
        TELEGRAM_PROXY_PORT,
        True,   # DNS через прокси
    ),
)


# ===============================================================
# ============= УТИЛИТЫ =========================================
# ===============================================================

def ensure_media_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)


def remove_blacklist_phrases(full_text: str) -> str:
    """Удаляет все фразы из blacklist из всего текста безопасно."""
    if not full_text:
        return full_text

    cleaned = full_text
    for bad in blacklist_words:
        if not bad or not bad.strip():
            continue

        pattern = re.escape(bad)
        pattern = pattern.replace(r'\ ', r'[\s\u00A0]+')
        pattern = pattern.replace(r'\n', r'[\s\u00A0]*')
        try:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        except re.error:
            cleaned = cleaned.replace(bad, '')

    cleaned = re.sub(r'(\n\s*)+$', '', cleaned)
    return cleaned


def utf16_to_python_index(s, utf16_index):
    idx = 0
    count = 0
    while idx < len(s) and count < utf16_index:
        c = s[idx]
        code = ord(c)
        count += 2 if code >= 0x10000 else 1
        idx += 1
    return idx


def message_to_html(message):
    text = message.message or ""
    html = ""
    last = 0

    for ent in sorted(message.entities or [], key=lambda e: e.offset):
        start = utf16_to_python_index(text, ent.offset)
        end = utf16_to_python_index(text, ent.offset + ent.length)

        # --- FIX: защита от перекрывающихся/повторных сущностей ---
        if end <= last:
            continue
        if start < last:
            start = last
        # ---------------------------------------------------------


        html += escape(text[last:start])
        part = text[start:end]

        if isinstance(ent, MessageEntityTextUrl):
            html += f'<a href="{escape(ent.url)}">{escape(part)}</a>'
        elif isinstance(ent, MessageEntityUrl):
            html += f'<a href="{escape(part)}">{escape(part)}</a>'
        elif isinstance(ent, MessageEntityBold):
            html += f"<b>{escape(part)}</b>"
        elif isinstance(ent, MessageEntityItalic):
            html += f"<i>{escape(part)}</i>"
        elif isinstance(ent, MessageEntityCode):
            html += f"<code>{escape(part)}</code>"
        elif isinstance(ent, MessageEntityPre):
            html += f"<pre>{escape(part)}</pre>"
        elif isinstance(ent, MessageEntityMentionName):
            uid = getattr(ent, 'user_id', None)
            html += f'<a href="tg://user?id={uid}">{escape(part)}</a>' if uid else escape(part)
        elif isinstance(ent, MessageEntityMention):
            html += escape(part)
        elif isinstance(ent, MessageEntityPhone):
            html += f'<a href="tel:{escape(part)}">{escape(part)}</a>'
        elif isinstance(ent, MessageEntityEmail):
            html += f'<a href="mailto:{escape(part)}">{escape(part)}</a>'
        elif isinstance(ent, MessageEntityBotCommand):
            html += escape(part)
        elif isinstance(ent, MessageEntityStrike):
            html += f"<s>{escape(part)}</s>"
        elif isinstance(ent, MessageEntityUnderline):
            html += f"<u>{escape(part)}</u>"
        else:
            html += escape(part)
        last = end

    # html += escape(remove_blacklist_phrases(text[last:]))

    if last < len(text):
        html += escape(text[last:])

    return html


async def download_media_from_messages(msgs):
    paths = []
    for m in msgs:
        if not m.media:
            continue
        ext = ".jpg"
        try:
            mime = None
            if getattr(m.media, 'document', None) and getattr(m.media.document, 'mime_type', None):
                mime = m.media.document.mime_type
            elif getattr(m.media, 'photo', None):
                mime = 'image/jpeg'

            if mime:
                if 'png' in mime:
                    ext = '.png'
                elif 'webp' in mime:
                    ext = '.webp'
                elif 'gif' in mime:
                    ext = '.gif'
                elif 'mp4' in mime or 'video' in mime:
                    ext = '.mp4'
                else:
                    ext = '.jpg'
        except Exception:
            ext = '.jpg'

        path = os.path.join(MEDIA_DIR, f"{m.id}{ext}")
        try:
            await m.download_media(file=path)
            if os.path.exists(path):
                paths.append(path)
        except Exception:
            pass
    return paths


# ===============================================================
# ============= ОБРАБОТЧИК НОВЫХ СООБЩЕНИЙ ======================
# ===============================================================

@client.on(events.NewMessage(chats=channels_to_parse))
async def handler(event):
    try:
        chat = await event.get_chat()
        channel = getattr(chat, 'username', None) or getattr(chat, 'title', 'unknown')
        orig_message_id = event.message.id

        if event.message.fwd_from:
            print(f"[SKIP] Пересланное сообщение в @{channel}")
            return

        # чистим blacklist
        raw_text = event.message.message or ""
        event.message.message = remove_blacklist_phrases(raw_text)
        text_html = message_to_html(event.message)
        cleaned_text = text_html.strip()

        if not cleaned_text.strip():
            return

        # стоп-слова
        if any(word.lower() in cleaned_text.lower() for word in STOP_WORDS):
            return

        for word in ALERT_WORDS:
            if word.lower() in cleaned_text.lower():
                alert_text = f"⚠️ Найдено ключевое слово <b>{word}</b> в посте из @{channel or 'неизвестного канала'}:\n\n{cleaned_text}"
                try:
                    send_alert(alert_text, None)
                except Exception as e:
                    print(f"[ALERT ERROR] {e}")
                break

        if post_exists(channel, orig_message_id):
            return



        grouped_id = getattr(event.message, 'grouped_id', None)
        messages_for_post = [event.message]
        if grouped_id:
            recent = await client.get_messages(event.chat_id, limit=20)
            group_msgs = [m for m in recent if getattr(m, 'grouped_id', None) == grouped_id]
            messages_for_post = sorted(group_msgs, key=lambda m: m.id)


        # --- ПРОВЕРКА: пропускать посты без ссылок и без фото ---
        has_link = any(isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl))
                    for m in messages_for_post
                    for ent in (m.entities or []))

        has_photo = any(
            getattr(m, 'photo', None) or
            (getattr(m, 'media', None) and getattr(m.media, 'photo', None))
            for m in messages_for_post
        )

        # если нет ссылок И нет фото — пропускаем
        if not has_link and not has_photo:
            print(f"[SKIP] Нет ссылок и фото — @{channel}")
            return
        # ----------------------------------------------------------

        has_video = any(
            getattr(m, 'video', None) or (
                getattr(m, 'media', None)
                and getattr(m.media, 'document', None)
                and 'video' in getattr(m.media.document, 'mime_type', '')
            )
            for m in messages_for_post
        )


        # если есть видео — пропускаем
        if  has_video:
            print(f"[SKIP] Виде в посте — @{channel}")
            return

        media_paths = []
        if not has_video:
            media_paths = await download_media_from_messages(messages_for_post)


        duplicate_window_seconds = max(1, int(DUPLICATE_WINDOW_HOURS * 3600))

        # проверка по изображению только в недавнем окне
        if media_paths and is_similar_image_duplicate_recent(
            media_paths,
            threshold=IMAGE_DUPLICATE_THRESHOLD,
            within_seconds=duplicate_window_seconds
        ):
            print(f"[SKIP] Похожее изображение найдено — @{channel}")
            return

        # источник
        # if getattr(chat, 'username', None):
        #     source = f"\n\n📢 Источник: @{chat.username}"
        # else:
        #     source = f"\n\n📢 Источник: {getattr(chat, 'title', 'Неизвестный канал')}"
        # cleaned_text += source

        # проверка на точный дубликат только в недавнем окне
        if is_exact_duplicate_recent(cleaned_text, within_seconds=duplicate_window_seconds):
            print(f"[SKIP] Точный дубликат — @{channel}")
            return


        # проверка на 92%+ похожий дубликат
        # if is_similar_duplicate(cleaned_text, threshold=0.92):
        #     print(f"[SKIP] Похожий на 92%+ дубликат — @{channel}")
        #     return

        # сохраняем
        post_id = save_post(channel, orig_message_id, cleaned_text, media_paths or [], has_video)

        # переименование медиа
        if media_paths:
            new_paths = []
            for idx, p in enumerate(media_paths):
                if not os.path.exists(p):
                    continue
                ext = os.path.splitext(p)[1].lower()
                new_name = os.path.join(MEDIA_DIR, f"post_{post_id}_{idx}{ext}")
                try:
                    os.replace(p, new_name)
                except Exception:
                    import shutil
                    shutil.copy2(p, new_name)
                    try:
                        os.remove(p)
                    except:
                        pass
                new_paths.append(new_name)
            update_media_paths(post_id, new_paths)
            media_paths = new_paths

        # публикация / отправка на модерацию
        if get_auto_mode(default=AUTO_MODE):
            publish_post(post_id)
        else:
            send_post_for_approval(post_id, cleaned_text, media_paths)

    except Exception as e:
        print(f"[ERROR parser handler] {e}")


# ===============================================================
# ============= ЗАПУСК ПАРСЕРА =================================
# ===============================================================

async def run_parser():
    ensure_media_dir()
    await client.start()
    print("✅ Парсер запущен и слушает каналы...")
    await client.run_until_disconnected()
