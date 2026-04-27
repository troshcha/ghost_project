import os
import time
import json
import psutil
import datetime
import telebot
from flask import Flask, render_template, jsonify
from threading import Thread
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))

DATA_FILE = "state.json"
DEFAULT_STATE = {
    "name": "GHOST-CORE",
    "page": "1",
    "mirror": False,
    "content_type": "image",
    "content_url": "",
    "cpu": "0%",
    "ram": "0%",
    "time": "00:00:00",
    "yt_id": "", 
    "sound_url": ""
}

# --- Save/Load State ---
def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                base = DEFAULT_STATE.copy()
                base.update(saved)
                return base
        except Exception as e:
            print(f"Помилка завантаження: {e}")
    return DEFAULT_STATE.copy()

def save_state():
    try:
        to_save = {k: v for k, v in state.items() if k not in ['cpu', 'ram', 'time']}
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Помилка збереження: {e}")

state = load_state()
state.update({"cpu": "0%", "ram": "0%", "time": "00:00:00"})

# --- States update loop ---
def update_stats_loop():
    psutil.cpu_percent(interval=None)
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        state['cpu'] = f"CPU: {cpu_usage}%"
        state['ram'] = f"RAM: {psutil.virtual_memory().percent}%"
        state['time'] = datetime.datetime.now().strftime("%H:%M:%S")

# --- ЛОГІКА FLASK ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify(state)

# --- ЛОГІКА TELEGRAM ---
# Команда для вибору сторінки
@bot.message_handler(commands=['page'])
def page_menu(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1", "2", "3", "4")
    bot.send_message(message.chat.id, "Оберіть сторінку:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["1", "2", "3", "4"])
def bot_page_buttons(message):
    state["page"] = message.text
    save_state()       
    bot.reply_to(message, f".mode-{get_word(message.text)}")

# Turn off the Raspberry Pi
@bot.message_handler(commands=['off'])
def shutdown_pi(message):
    bot.reply_to(message, "GHOST-CORE завершує роботу")
    os.system("sudo shutdown -h now")

# Mirror mode toggle
@bot.message_handler(commands=['mirror'])
def toggle_mirror(message):
    current_val = state.get("mirror", False)
    if isinstance(current_val, str):
        current_val = current_val.lower() == 'true'
    
    state["mirror"] = not current_val
    save_state()
    status = "ON" if state["mirror"] else "OFF"
    bot.reply_to(message, f"Mirror mode: {status}")

# GIF as file upload
@bot.message_handler(content_types=['animation', 'document', 'video'])
def handle_files(message):
    try:
        file_info = None
        if message.animation:
            file_info = bot.get_file(message.animation.file_id)
        elif message.video:
            file_info = bot.get_file(message.video.file_id)
        elif message.document and message.document.mime_type.startswith('image/gif'):
            file_info = bot.get_file(message.document.file_id)

        if file_info:
            # Отримуємо розширення файлу
            ext = file_info.file_path.split('.')[-1]
            filename = f"content.{ext}"
            filepath = os.path.join("static/uploads", filename)
            
            # Скачуємо файл на малинку
            downloaded_file = bot.download_file(file_info.file_path)
            with open(filepath, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            # Даємо фронтенду ЛОКАЛЬНЕ посилання
            # Додаємо таймстамп ?t=..., щоб браузер не брав стару гіфку з кешу
            state["content_type"] = "video" if ext in ['mp4', 'webm'] else "image"
            state["content_url"] = f"/static/uploads/{filename}?t={int(time.time())}"
            save_state()
            
            bot.reply_to(message, "🔥 Гіфку збережено локально! Перевіряй на 4 сторінці.")
        else:
            bot.reply_to(message, "❌ Не вдалося розпізнати файл.")
            
    except Exception as e:
        bot.reply_to(message, f"⚠️ Помилка: {e}")

# GIF by URL
@bot.message_handler(commands=['gif'])
def gif_link(message):
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        state["content_type"] = "image"
        state["content_url"] = url
        save_state()
        bot.reply_to(message, "🖼 Гіфку за посиланням додано!")
    except:
        bot.reply_to(message, "❌ Використання: /gif [посилання]")

# Load content from URL
@bot.message_handler(commands=['show'])
def show_content(message):
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        # Автоматичне визначення типу
        ext = url.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg', 'png', 'gif']:
            state["content_type"] = "image"
        else:
            state["content_type"] = "video"
            
        state["content_url"] = url
        save_state()
        bot.reply_to(message, "✅ Медіа в буфері.")
    except:
        bot.reply_to(message, "❌ Використання: /show [link]")

# Set custom name
@bot.message_handler(commands=['rename', 'setname'])
def rename_command(message):
    try:
        new_name = message.text.split(maxsplit=1)[1].strip().upper()
        state["name"] = new_name
        save_state() # ЗБЕРІГАЄМО
        bot.reply_to(message, f"Name saved: {new_name}")
    except IndexError:
        bot.reply_to(message, "Enter new name")

# Set YouTube video by URL
@bot.message_handler(commands=['yt'])
def set_youtube(message):
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        
        if video_id:
            state["content_type"] = "youtube"
            state["content_url"] = video_id.group(1)
            save_state()
            bot.reply_to(message, f"📺 YouTube завантажено. Перемкніть на сторінку 4.")
        else:
            bot.reply_to(message, "❌ Посилання не розпізнано.")
    except:
        bot.reply_to(message, "❌ Використання: /yt [link]")

def get_word(num):
    words = {"1": "one", "2": "two", "3": "three", "4": "four"}
    return words.get(num, "one")

# --- START ---
if __name__ == '__main__':
    Thread(target=update_stats_loop, daemon=True).start()
    Thread(target=lambda: bot.polling(none_stop=True), daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
