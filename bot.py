# bot.py
import os
import json
from telebot import TeleBot, types
from config import bot_token, owner_id, target_channel
from database import get_post, update_status, set_owner_message_ids, get_owner_message_ids

bot = TeleBot(bot_token, parse_mode='HTML')


def _make_controls(post_id: int):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{post_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{post_id}")
    )
    return markup


def _split_text(text, limit=4096):
    """Split by safe boundary (space) to avoid breaking tags in the middle if possible."""
    if len(text) <= limit:
        return [text]
    parts = []
    start = 0
    L = len(text)
    while start < L:
        end = start + limit
        if end >= L:
            parts.append(text[start:].strip())
            break
        # try to break at last space before end
        br = text.rfind(' ', start, end)
        if br <= start:
            br = end  # forced break
        parts.append(text[start:br].strip())
        start = br
    return parts


def _send_long_message(chat_id, text, reply_markup=None):
    parts = _split_text(text)
    ids = []
    for i, part in enumerate(parts):
        msg = bot.send_message(chat_id, part, reply_markup=reply_markup if i == 0 else None)
        ids.append(msg.message_id)
    return ids


def send_post_for_approval(post_id: int, text: str, media_paths=None):
    """Send post to owner for moderation and save message ids."""
    try:
        media_paths = [p for p in (media_paths or []) if p and os.path.exists(p)]
        sent_ids = []

        if media_paths:
            media_group = []
            files = []
            try:
                for i, path in enumerate(media_paths):
                    ext = os.path.splitext(path)[1].lower()
                    f = open(path, 'rb')
                    files.append(f)
                    if ext in ('.mp4', '.mov', '.mkv', '.webm'):
                        media = types.InputMediaVideo(f)
                    else:
                        media = types.InputMediaPhoto(f)
                    if i == 0:
                        caption = text[:1024] + ("…" if len(text) > 1024 else "")
                        media.caption = caption
                    media_group.append(media)

                sent = bot.send_media_group(owner_id, media_group)
                sent_ids.extend([m.message_id for m in sent])
            finally:
                for f in files:
                    try:
                        f.close()
                    except:
                        pass

            if len(text) > 1024:
                extra = text[1024:]
                sent_ids.extend(_send_long_message(owner_id, extra))

            info = bot.send_message(
                owner_id,
                f"🆔 <b>Post ID:</b> {post_id}\nИсточник: {get_post(post_id)['channel']}",
                reply_markup=_make_controls(post_id)
            )
            sent_ids.append(info.message_id)
        else:
            msg_ids = _send_long_message(owner_id, f"<b>Post ID:</b> {post_id}\n\n{text}", reply_markup=_make_controls(post_id))
            sent_ids.extend(msg_ids)

        set_owner_message_ids(post_id, sent_ids)
        return sent_ids

    except Exception as e:
        bot.send_message(owner_id, f"❌ Ошибка при отправке поста: {e}")


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if ":" not in call.data:
            return bot.answer_callback_query(call.id, "Неверная команда")
        cmd, sid = call.data.split(":", 1)
        post_id = int(sid)
        if call.from_user.id != owner_id:
            return bot.answer_callback_query(call.id, "⛔ Нет доступа")

        # удаляем сообщения владельца (модерация)
        owner_ids = get_owner_message_ids(post_id) or []
        for mid in owner_ids:
            try:
                bot.delete_message(owner_id, mid)
            except:
                pass

        if cmd == "approve":
            bot.answer_callback_query(call.id, "Публикую…")
            publish_post(post_id)
        elif cmd == "reject":
            update_status(post_id, 'rejected')
            bot.answer_callback_query(call.id, "Отклонено")
            bot.send_message(owner_id, f"🚫 Post {post_id} отклонён.")
        else:
            bot.answer_callback_query(call.id, "Неизвестная команда")
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {e}")
        except:
            pass


def _send_media_paths_direct(chat_id, text, media_paths):
    """Fallback: send media files directly to channel when copy_message fails."""
    media_paths = [p for p in (media_paths or []) if p and os.path.exists(p)]
    if media_paths:
        media_group = []
        files = []
        try:
            for i, path in enumerate(media_paths):
                ext = os.path.splitext(path)[1].lower()
                f = open(path, 'rb')
                files.append(f)
                if ext in ('.mp4', '.mov', '.mkv', '.webm'):
                    media = types.InputMediaVideo(f)
                else:
                    media = types.InputMediaPhoto(f)
                if i == 0:
                    caption = text[:1024] + ("…" if len(text) > 1024 else "")
                    media.caption = caption
                media_group.append(media)
            bot.send_media_group(chat_id, media_group)
        finally:
            for f in files:
                try:
                    f.close()
                except:
                    pass
    else:
        _send_long_message(chat_id, text)


def publish_post(post_id: int) -> bool:
    """Try copy_message; if fails — fallback to direct sending using stored text/media."""
    post = get_post(post_id)
    if not post:
        bot.send_message(owner_id, f"❌ Post {post_id} не найден в базе.")
        return False

    owner_msg_ids = get_owner_message_ids(post_id) or []
    text = post.get("text") or ""
    try:
        media_paths = json.loads(post.get("media_paths") or "[]")
    except Exception:
        media_paths = []

    success = False
    # First try to copy messages that were sent to owner (this preserves original sender formatting best)
    if owner_msg_ids:
        for mid in owner_msg_ids:
            try:
                bot.copy_message(target_channel, owner_id, mid)
                success = True
            except Exception as e:
                success = False
    # If nothing was copied successfully, use fallback
    if not success:
        try:
            _send_media_paths_direct(target_channel, text, media_paths)
            success = True
        except Exception as e:
            update_status(post_id, 'error')
            bot.send_message(owner_id, f"❌ Ошибка при публикации post {post_id}: {e}")
            return False

    update_status(post_id, 'published')
    bot.send_message(owner_id, f"✅ Post {post_id} опубликован.")
    return True


def run_bot():
    print("🤖 Bot thread started")
    bot.infinity_polling(skip_pending=True)
