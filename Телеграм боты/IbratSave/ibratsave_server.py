import os
import shutil
import asyncio
import logging
import uuid
import threading
import time
from urllib.parse import urlparse

import telebot
from telebot import types
import yt_dlp

# Папка для бота
BASE_DIR = "/root/ibratsave"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
VIDEO_DIR = DOWNLOAD_DIR

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

ADMIN_IDS = {772482922}

DOWNLOAD_REQUESTS = {}
ADMIN_DELETE_REQUESTS = {}
PROGRESS = {}

BOT_TOKEN = ""

DOWNLOAD_FINISHED = False

bot = telebot.TeleBot(BOT_TOKEN)


def safe_edit_message_text(text, chat_id, message_id, reply_markup=None):
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup)
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            logging.error(f"Ошибка редактирования сообщения: {e}")


def progress_hook(d):
    """
    Хук, вызываемый при скачивании (обновляет глобальный PROGRESS).
    """
    global PROGRESS
    if d.get('status') == 'downloading':
        PROGRESS = d


def download_video(url: str, format_id: str, do_postprocess: bool):
    """
    Скачиваем видео:
    - Если do_postprocess=True, включаем постпроцесс (FFmpeg: H.264 + AAC).
    - Если False, скачиваем «как есть».
    """
    global DOWNLOAD_FINISHED
    DOWNLOAD_FINISHED = False

    ydl_opts = {
        'format': format_id,
        'outtmpl': os.path.join(VIDEO_DIR, '%(title)s-%(id)s.%(ext)s'),
        'progress_hooks': [progress_hook],
    }

    if do_postprocess:
        ydl_opts['postprocessors'] = [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            },
            {
                'key': 'FFmpegMetadata'
            }
        ]
        ydl_opts['postprocessor_args'] = [
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23'
        ]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    safe_edit_message_text("Качаем: ██████████ 100.0%\nЗагрузка завершена!", 0, 0)
    DOWNLOAD_FINISHED = True
    print("Видео скачано" + (", с перекодированием!" if do_postprocess else ", без перекодирования!"))


def progress_updater(chat_id, message_id):
    """
    Каждые 3 секунды пытается обновить сообщение о прогрессе.
    """
    last_text = ""
    while not DOWNLOAD_FINISHED:
        time.sleep(3)
        try:
            if PROGRESS and PROGRESS.get('status') == 'downloading':
                downloaded = PROGRESS.get('downloaded_bytes', 0)
                total = PROGRESS.get('total_bytes') or PROGRESS.get('total_bytes_estimate', 0)
                percent = (downloaded / total * 100) if total else 0
                speed = PROGRESS.get('speed', 0)
                eta = PROGRESS.get('eta', 0)
                blocks = int(percent // 10)
                progress_bar = '█' * blocks + '▒' * (10 - blocks)
                text = (
                    f"Качаем: {progress_bar} {percent:.1f}%\n"
                    f"Загружено: {downloaded}/{total} байт\n"
                    f"Скорость: {speed:.2f} B/s, ETA: {eta} сек"
                )
                if text != last_text:
                    safe_edit_message_text(text, chat_id, message_id)
                    last_text = text
        except Exception as e:
            logging.error(f"Ошибка обновления прогресса: {e}")


def get_video_formats(url: str):
    """
    Возвращает список форматов, чтобы подобрать 360/480/720/1080p (mp4).
    """
    ydl_opts = {'listformats': True, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('formats', [])


def select_format_by_resolution(formats, target_res):
    """
    Находим mp4-формат, у которого высота ближе всего к target_res (±50).
    """
    candidates = []
    for fmt in formats:
        if fmt.get('ext') != 'mp4':
            continue
        height = fmt.get('height') or 0
        diff = abs(height - target_res)
        if diff <= 50:
            candidates.append((fmt, diff))
    if not candidates:
        return None
    best_fmt = min(candidates, key=lambda x: x[1])[0]
    return best_fmt


def download_instagram_post(url: str):
    """
    Скачивание Instagram-постов (не трогаем).
    """
    global DOWNLOAD_FINISHED
    DOWNLOAD_FINISHED = False
    ydl_opts = {
        'outtmpl': os.path.join(VIDEO_DIR, '%(title)s-%(id)s-%(playlist_index)s.%(ext)s'),
        'progress_hooks': [progress_hook]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info and info['entries']:
            for entry in info['entries']:
                if entry:
                    ydl.download([entry['webpage_url']])
        else:
            ydl.download([url])
    DOWNLOAD_FINISHED = True
    return info


def download_instagram(message, url):
    """
    Отдельная функция для Instagram — возвращаем шуточные тексты.
    """
    status_msg = bot.send_message(message.chat.id, "Стартуем! Начинаю качать этот сумасшедший пост... 🤡🚀")
    progress_thread = threading.Thread(target=progress_updater, args=(message.chat.id, status_msg.message_id), daemon=True)
    progress_thread.start()

    try:
        info = download_instagram_post(url)
        title = info.get('title', '')
        media_files = [
            os.path.join(VIDEO_DIR, f)
            for f in os.listdir(VIDEO_DIR)
            if f.lower().endswith(('.mp4', '.mov', '.jpg', '.jpeg', '.png'))
        ]
        if not media_files:
            time.sleep(3)
            bot.edit_message_text("Ой-ой! Пост скачан, но файлы затерялись... 🤷‍♂️🙈", message.chat.id, status_msg.message_id)
            return

        bot.edit_message_text("Бах! Пост готов, закидываю файлы к тебе! 🎉🤡", message.chat.id, status_msg.message_id)

        for file in media_files:
            file_size = os.path.getsize(file)
            if file_size >= MAX_FILE_SIZE:
                if message.chat.id not in ADMIN_IDS:
                    time.sleep(3)
                    bot.send_message(
                        message.chat.id,
                        "Ого, этот пост настолько гигантский, что не могу его прям закинуть! 😱📏"
                    )
                    if os.path.isdir(file):
                        shutil.rmtree(file, ignore_errors=True)
                    else:
                        os.remove(file)
                else:
                    admin_key = str(uuid.uuid4())[:8]
                    ADMIN_DELETE_REQUESTS[admin_key] = file
                    admin_markup = types.InlineKeyboardMarkup()
                    admin_markup.add(
                        types.InlineKeyboardButton(
                            text="Я скачал контент",
                            callback_data=f"delete|{admin_key}"
                        )
                    )
                    bot.send_message(
                        message.chat.id,
                        f"Контент заскочил на сервер: {file}\nСкачай и жми кнопку, как настоящий клоун! 🤡👉",
                        reply_markup=admin_markup
                    )
            else:
                if file.lower().endswith(('.mp4', '.mov')):
                    with open(file, 'rb') as video:
                        bot.send_video(message.chat.id, video, caption=title)
                else:
                    with open(file, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo, caption=title)

        time.sleep(10)
        admin_files = set(ADMIN_DELETE_REQUESTS.values())
        for f in os.listdir(VIDEO_DIR):
            file_path = os.path.join(VIDEO_DIR, f)
            if file_path in admin_files:
                continue
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path, ignore_errors=True)
                else:
                    os.remove(file_path)
            except Exception as del_e:
                logging.error(f"Ошибка при удалении файла {file_path}: {del_e}")

    except Exception as e:
        bot.edit_message_text(f"Ой-ой, произошла ошибка при качании поста! 😵‍💫 {e}", message.chat.id, status_msg.message_id)


@bot.message_handler(commands=["start"])
def start_handler(message: types.Message):
    welcome_text = (
        "Йо, привет! 🤡🎉\n\n"
        "Я — Ibratsave, твой безбашенный клоун-бот для скачивания постов с видосами и фотками! 🤪📸🎥\n"
        "Скинь мне ссылку на пост (VK, Instagram, YouTube – всё, что душе угодно 😜) и смотри, как я превращаю контент в магию! 🚀💥\n\nСохраните видео на устройство, чтобы восстановить его первичный облик!\n\n"
        "Если файл больше 50 MB, обычным юзерам он не доступен! 🗑️🤡 Но админам можно. 🔑"
    )
    bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(func=lambda message: 'http' in message.text)
def link_handler(message: types.Message):
    url = message.text.strip()

    # Проверяем Instagram
    if "instagram.com" in url:
        download_instagram(message, url)
        return

    # Иначе пробуем YouTube / другое
    status_msg = bot.send_message(message.chat.id, "Стартуем! Начинаю проверять форматы... 🎬🔥")
    try:
        all_formats = get_video_formats(url)
        if not all_formats:
            bot.edit_message_text(
                "Упс... Не удалось найти форматы для этого видео. 😕",
                message.chat.id,
                status_msg.message_id
            )
            return

        target_resolutions = [360, 480, 720, 1080, 640, 848, 1280, 1920]
        markup = types.InlineKeyboardMarkup()
        any_found = False

        for res in target_resolutions:
            fmt = select_format_by_resolution(all_formats, res)
            if fmt:
                fid = fmt.get('format_id')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                height = fmt.get('height') or 0
                width = fmt.get('width') or 0
                size_mb = f"{filesize/(1024*1024):.1f} MB" if filesize else "N/A"

                key = str(uuid.uuid4())[:8]
                DOWNLOAD_REQUESTS[key] = (fid, url, filesize)

                btn_text = f"{res}p (ID {fid}) | {width}x{height} | {size_mb}"
                markup.add(
                    types.InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"download|{key}"
                    )
                )
                any_found = True

        if not any_found:
            bot.edit_message_text(
                "Не нашлось подходящих mp4-форматов на 360/480/720/1080p. 😵‍💫",
                message.chat.id,
                status_msg.message_id
            )
            return

        bot.edit_message_text(
            "Выбери формат для скачивания видоса:",
            message.chat.id,
            status_msg.message_id,
            reply_markup=markup
        )

    except Exception as e:
        bot.edit_message_text(
            f"Упс, ошибка при получении форматов! 😵 {e}",
            message.chat.id,
            status_msg.message_id
        )


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("download|"))
def process_download_callback(call: types.CallbackQuery):
    data = call.data.split("|")
    if len(data) < 2:
        return

    key = data[1]
    if key not in DOWNLOAD_REQUESTS:
        bot.send_message(call.message.chat.id, "Запрос просрочен или недействителен! ⏰🤡")
        return

    format_id, url, filesize = DOWNLOAD_REQUESTS.pop(key)
    msg = call.message

    # Если не админ и размер > 50MB
    if filesize and filesize > MAX_FILE_SIZE and (msg.chat.id not in ADMIN_IDS):
        bot.edit_message_text(
            "Ого, этот пост настолько гигантский, что не могу его прям закинуть! 😱📏",
            msg.chat.id,
            msg.message_id
        )
        return

    # Для админов > 50MB (или юзеров < 50MB) решаем — перекодировать или нет
    do_postprocess = False
    if filesize and filesize <= MAX_FILE_SIZE:
        do_postprocess = True  # Для маленьких файлов включим перекодирование

    bot.edit_message_text("Стартуем качать видос! 🎬🔥", msg.chat.id, msg.message_id)

    progress_thread = threading.Thread(
        target=progress_updater,
        args=(msg.chat.id, msg.message_id),
        daemon=True
    )
    progress_thread.start()

    try:
        download_video(url, format_id, do_postprocess)

        info = yt_dlp.YoutubeDL({'quiet': True}).extract_info(url, download=False)
        video_title = info.get('title', '')

        media_files = [
            os.path.join(VIDEO_DIR, f)
            for f in os.listdir(VIDEO_DIR)
            if f.lower().endswith(('.mp4', '.mov', '.jpg', '.jpeg', '.png'))
        ]
        if not media_files:
            time.sleep(3)
            bot.edit_message_text("Ой! Видос скачан, но файлы где-то исчезли... 🤔", msg.chat.id, msg.message_id)
            return

        bot.edit_message_text("Видос готов! Закидываю файлы к тебе! 🚀🎉", msg.chat.id, msg.message_id)

        for file in media_files:
            file_size = os.path.getsize(file)
            if file_size >= MAX_FILE_SIZE:
                if msg.chat.id not in ADMIN_IDS:
                    time.sleep(3)
                    bot.send_message(msg.chat.id, "Контент слишком огромный для прямой отправки! 🎪😲")
                    if os.path.isdir(file):
                        shutil.rmtree(file, ignore_errors=True)
                    else:
                        os.remove(file)
                else:
                    admin_key = str(uuid.uuid4())[:8]
                    ADMIN_DELETE_REQUESTS[admin_key] = file
                    admin_markup = types.InlineKeyboardMarkup()
                    admin_markup.add(
                        types.InlineKeyboardButton(
                            text="Я скачал контент",
                            callback_data=f"delete|{admin_key}"
                        )
                    )
                    bot.send_message(
                        msg.chat.id,
                        f"Контент заскочил на сервер: {file}\nСкачай и жми кнопку, как настоящий клоун! 🤡👉",
                        reply_markup=admin_markup
                    )
            else:
                if file.lower().endswith(('.mp4', '.mov')):
                    with open(file, 'rb') as video:
                        bot.send_video(msg.chat.id, video, caption=video_title)
                else:
                    with open(file, 'rb') as photo:
                        bot.send_photo(msg.chat.id, photo, caption=video_title)

        time.sleep(10)
        admin_files = set(ADMIN_DELETE_REQUESTS.values())
        for f in os.listdir(VIDEO_DIR):
            file_path = os.path.join(VIDEO_DIR, f)
            if file_path in admin_files:
                continue
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path, ignore_errors=True)
                else:
                    os.remove(file_path)
            except Exception as del_e:
                logging.error(f"Ошибка при удалении файла {file_path}: {del_e}")

    except Exception as e:
        bot.edit_message_text(f"Ой-ой, произошла ошибка при качании видоса! 😵‍💫 {e}", msg.chat.id, msg.message_id)


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("delete|"))
def delete_video_callback(call: types.CallbackQuery):
    data = call.data.split("|")
    if len(data) < 2:
        return

    key = data[1]
    if key not in ADMIN_DELETE_REQUESTS:
        bot.send_message(call.message.chat.id, "Запрос просрочен или недействителен! ⏰🤡")
        return

    file_path = ADMIN_DELETE_REQUESTS.pop(key)
    if os.path.exists(file_path):
        if os.path.isdir(file_path):
            shutil.rmtree(file_path, ignore_errors=True)
        else:
            os.remove(file_path)
        bot.edit_message_text("Контент стер с сервера! 🗑️💥", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("Контент уже пропал, как иллюзия! 🕳️😜", call.message.chat.id, call.message.message_id)


if __name__ == "__main__":
    DOWNLOAD_REQUESTS = {}
    ADMIN_DELETE_REQUESTS = {}
    print("Бот запущен!")
    bot.polling(none_stop=True)
