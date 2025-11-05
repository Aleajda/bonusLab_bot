# parser.py
import os
import asyncio
import re
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


def ensure_media_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)


def _remove_blacklist_from_segment(segment: str):
    """Удаляет все фразы из blacklist из данного фрагмента (регистронезависимо)."""
    if not segment:
        return segment
    cleaned = segment
    for bad in blacklist_words:
        if not bad:
            continue
        # Use regex for case-insensitive replacement
        try:
            cleaned = re.sub(re.escape(bad), '', cleaned, flags=re.IGNORECASE)
        except re.error:
            # fallback to simple replace if regex fails
            cleaned = cleaned.replace(bad, '')
    return cleaned


def message_to_html(message):
    """
    Convert Telethon Message and its entities to safe HTML.
    Removes blacklist phrases only from visible text parts (not whole message blocking).
    """
    text = message.message or ""
    if not getattr(message, 'entities', None):
        # no entities — just remove blacklist and escape
        return escape(_remove_blacklist_from_segment(text))

    html = ""
    last = 0
    for ent in sorted(message.entities, key=lambda e: e.offset):
        # plain text before entity
        plain = text[last:ent.offset]
        plain = _remove_blacklist_from_segment(plain)
        html += escape(plain)

        part = text[ent.offset:ent.offset + ent.length]
        part = _remove_blacklist_from_segment(part)

        # handle entity types
        if isinstance(ent, MessageEntityTextUrl):
            url = getattr(ent, 'url', None) or ''
            html += f'<a href="{escape(url)}">{escape(part)}</a>'
        elif isinstance(ent, MessageEntityUrl):
            # the entity contains a URL inside the text part
            url = part
            html += f'<a href="{escape(url)}">{escape(part)}</a>'
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
            if uid:
                html += f'<a href="tg://user?id={uid}">{escape(part)}</a>'
            else:
                html += escape(part)
        elif isinstance(ent, MessageEntityMention):
            html += f"{escape(part)}"  # @username as plain text
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

        last = ent.offset + ent.length

    tail = text[last:]
    tail = _remove_blacklist_from_segment(tail)
    html += escape(tail)
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

@client.on(events.NewMessage(chats=channels_to_parse))
async def handler(event):
    try:
        chat = await event.get_chat()
        channel = getattr(chat, 'username', None) or getattr(chat, 'title', 'unknown')
        orig_message_id = event.message.id

        # Convert to HTML, removing only blacklist phrases
        text_html = message_to_html(event.message)
        cleaned_text = ' '.join(text_html.split())

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

        # ✅ Добавляем источник в конец текста
        if getattr(chat, 'username', None):
            source = f"\n\n📢 Источник: @{chat.username}"
        else:
            source = f"\n\n📢 Источник: {getattr(chat, 'title', 'Неизвестный канал')}"
        cleaned_text = cleaned_text + source

        post_id = save_post(channel, orig_message_id, cleaned_text, media_paths or [], has_video)

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



async def run_parser():
    ensure_media_dir()
    await client.start()
    print("✅ Парсер запущен и слушает каналы...")
    await client.run_until_disconnected()
