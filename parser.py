# parser.py
import os
import asyncio
import re
from html import escape
import regex  # pip install regex
from html import escape
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityTextUrl, MessageEntityUrl, MessageEntityBold,
    MessageEntityItalic, MessageEntityCode, MessageEntityPre,
    MessageEntityMentionName, MessageEntityStrike, MessageEntityUnderline,
    MessageEntityPhone, MessageEntityEmail, MessageEntityMention, MessageEntityBotCommand
)
from config import api_id, api_hash, channels_to_parse, blacklist_words
from database import post_exists, save_post, update_media_paths
from bot import send_post_for_approval

MEDIA_DIR = "media"
client = TelegramClient('parser_session', api_id, api_hash)


# ===============================================================
# ============= УТИЛИТЫ =========================================
# ===============================================================

def ensure_media_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)


def remove_blacklist_phrases(full_text: str) -> str:
    """
    Удаляет все фразы из blacklist из всего текста.
    Работает регистронезависимо и игнорирует пробелы/переносы между словами blacklist-фразы.
    Также убирает лишние пустые строки в конце текста.
    """
    if not full_text:
        return full_text

    cleaned = full_text
    for bad in blacklist_words:
        if not bad:
            continue

        # Экранируем шаблон и допускаем вариации пробелов/переносов
        pattern = re.escape(bad)
        pattern = pattern.replace(r'\ ', r'[\s\u00A0]+')  # обычные и неразрывные пробелы
        pattern = pattern.replace(r'\n', r'[\s\u00A0]*')
        try:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        except re.error:
            cleaned = cleaned.replace(bad, '')

    cleaned = re.sub(r'(\n\s*)+$', '', cleaned)

    return cleaned



def _remove_blacklist_from_segment(segment: str):
    """Лёгкая версия удаления blacklist — для работы внутри message_to_html."""
    return remove_blacklist_phrases(segment)


def utf16_to_python_index(s, utf16_index):
    """
    Конвертирует UTF-16 индекс в индекс Python строки.
    """
    idx = 0
    count = 0
    while idx < len(s) and count < utf16_index:
        c = s[idx]
        code = ord(c)
        if code >= 0x10000:  # символ вне BMP занимает 2 UTF-16 единицы
            count += 2
        else:
            count += 1
        idx += 1
    return idx

def message_to_html(message):
    text = message.message or ""
    html = ""
    last = 0

    for ent in sorted(message.entities, key=lambda e: e.offset):
        start = utf16_to_python_index(text, ent.offset)
        end = utf16_to_python_index(text, ent.offset + ent.length)

        # текст до сущности
        html += escape(text[last:start])
        part = text[start:end]

        # обработка сущностей
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

    html += escape(_remove_blacklist_from_segment(text[last:]))
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
        except Exception as e:
            print(f"[WARN] Не удалось скачать media {m.id}: {e}")
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

        # Удаляем blacklist-фразы из всего текста ДО форматирования
        raw_text = event.message.message or ""
        event.message.message = remove_blacklist_phrases(raw_text)

        # Конвертируем в HTML с сохранением форматирования
        text_html = message_to_html(event.message)
        cleaned_text = text_html.strip()

        if not cleaned_text.strip():
            print(f"[FILTERED] Пост из @{channel} удалён из-за blacklist")
            return

        if post_exists(channel, orig_message_id):
            return

        grouped_id = getattr(event.message, 'grouped_id', None)
        messages_for_post = [event.message]
        if grouped_id:
            recent = await client.get_messages(event.chat_id, limit=20)
            group_msgs = [m for m in recent if getattr(m, 'grouped_id', None) == grouped_id]
            group_msgs = sorted(group_msgs, key=lambda m: m.id)
            messages_for_post = group_msgs

        has_video = any(
            getattr(m, 'video', None) or (
                getattr(m, 'media', None)
                and getattr(m.media, 'document', None)
                and 'video' in getattr(m.media.document, 'mime_type', '')
            )
            for m in messages_for_post
        )

        media_paths = []
        if not has_video:
            media_paths = await download_media_from_messages(messages_for_post)

        # Добавляем источник в конец текста
        if getattr(chat, 'username', None):
            source = f"\n\n📢 Источник: @{chat.username}"
        else:
            source = f"\n\n📢 Источник: {getattr(chat, 'title', 'Неизвестный канал')}"
        cleaned_text = cleaned_text + source

        post_id = save_post(channel, orig_message_id, cleaned_text, media_paths or [], has_video)

        # Переименовываем медиа
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
