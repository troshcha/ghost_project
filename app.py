import os
import time
import json
import socket
import psutil
import datetime
import telebot
import threading
import re
import logging

from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

# ---------------------------------------------------------
# INIT
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")

STATE_FILE = "state.json"
UPLOADS_DIR = os.path.join("static", "uploads")

# Auto page-switch schedule (24h). Only affects pages 1 and 2.
NIGHT_HOUR = 23   # switch to page 2 at this hour
DAY_HOUR   = 7    # switch back to page 1 at this hour

DEFAULT_STATE = {
    "name": "GHOST-CORE",
    "page": "1",
    "mirror": False,
    "content_type": "image",
    "content_url": "",
    "cpu": 0.0,
    "ram": 0.0,
    "temp": 0.0,
    "disk": 0.0,
    "uptime": "0m",
    "ip": "—",
    "time": "00:00:00",
    "date": "—",
}

state_lock = threading.Lock()
state = {}

# ---------------------------------------------------------
# STATE HANDLING (THREAD-SAFE)
# ---------------------------------------------------------

def load_state():
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            base = DEFAULT_STATE.copy()
            base.update(data)
            return base
    except Exception:
        return DEFAULT_STATE.copy()


VOLATILE = {"cpu", "ram", "temp", "disk", "uptime", "ip", "time", "date"}

def save_state():
    try:
        with state_lock:
            persistent = {k: v for k, v in state.items()
                          if k not in VOLATILE}

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(persistent, f, ensure_ascii=False, indent=4)

    except Exception as e:
        log.error("State save error: %s", e)


# ---------------------------------------------------------
# BACKGROUND SYSTEM METRICS
# ---------------------------------------------------------

def auto_page_switch(hour):
    """Switch between page 1 (day) and page 2 (night) based on time.
    Pages 3 and 4 are never touched automatically."""
    with state_lock:
        current = state.get("page")

    if current not in ("1", "2"):
        return

    if NIGHT_HOUR > DAY_HOUR:
        # spans midnight e.g. 23→07
        is_night = (hour >= NIGHT_HOUR) or (hour < DAY_HOUR)
    else:
        # same-day range e.g. 16→17
        is_night = (hour >= NIGHT_HOUR) and (hour < DAY_HOUR)
    target = "2" if is_night else "1"

    if current != target:
        safe_set("page", target)
        log.info("[Auto] page %s → %s (hour=%d)", current, target, hour)


def get_temp():
    try:
        raw = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        return int(raw) // 1000
    except Exception:
        return 0.0

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "N/A"

def format_uptime(seconds):
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    if d > 0:
        return f"{d}d {h}h {m}m"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def stats_loop():
    psutil.cpu_percent(None)
    _ip = get_ip()
    _ip_refresh = 0

    while True:
        try:
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            temp = get_temp()
            now  = datetime.datetime.now()
            uptime = format_uptime(time.time() - psutil.boot_time())

            # refresh IP every 60s
            if time.time() - _ip_refresh > 60:
                _ip = get_ip()
                _ip_refresh = time.time()

            with state_lock:
                state["cpu"]    = cpu
                state["ram"]    = ram
                state["temp"]   = temp
                state["disk"]   = disk
                state["uptime"] = uptime
                state["ip"]     = _ip
                state["time"]   = now.strftime("%H:%M:%S")
                state["date"]   = now.strftime("%a %d %b %Y").upper()

            auto_page_switch(now.hour)
        except Exception as e:
            log.error("[Stats] error: %s", e)
            time.sleep(1)


# ---------------------------------------------------------
# FLASK ENDPOINTS
# ---------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    with state_lock:
        return jsonify(state.copy())


# ---------------------------------------------------------
# TELEGRAM HANDLERS
# ---------------------------------------------------------

def safe_set(key, value):
    with state_lock:
        state[key] = value
    save_state()

def safe_multi(**kwargs):
    with state_lock:
        for k, v in kwargs.items():
            state[k] = v
    save_state()


@bot.message_handler(commands=["help"])
def help_cmd(msg):
    bot.reply_to(msg, (
        "<b>Commands</b>\n\n"
        "<b>Display</b>\n"
        "/page — show page selector (1–4)\n"
        "/mirror — toggle horizontal mirror\n\n"
        "<b>Content (page 4)</b>\n"
        "/show &lt;URL&gt; — load image or video from URL\n"
        "/gif &lt;URL&gt; — load GIF from URL\n"
        "/yt &lt;URL&gt; — load YouTube video\n"
        "— or just send a GIF/video file directly\n\n"
        "<b>System</b>\n"
        "/load — CPU, RAM, temp, disk\n"
        "/rename &lt;NAME&gt; — set display name\n"
        "/off — shutdown the Pi"
    ))


@bot.message_handler(commands=["load"])
def system_load(msg):
    try:
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        freq = psutil.cpu_freq()
        temp = get_temp()

        freq_str  = f"{freq.current:.0f} MHz" if freq else "N/A"
        ram_used  = ram.used  // (1024 ** 2)
        ram_total = ram.total // (1024 ** 2)
        disk_free = disk.free // (1024 ** 3)
        temp_str  = f"{temp}°C" if temp else "N/A"

        bot.reply_to(msg, (
            f"<b>System Load</b>\n"
            f"CPU:  {cpu}%\n"
            f"RAM:  {ram.percent}% ({ram_used} / {ram_total} MB)\n"
            f"Temp: {temp_str}\n"
            f"Freq: {freq_str}\n"
            f"Disk: {disk.percent}% ({disk_free} GB free)"
        ))
    except Exception as e:
        bot.reply_to(msg, f"Error: {e}")


@bot.message_handler(commands=["page"])
def choose_page(msg):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1", "2", "3", "4")
    bot.send_message(msg.chat.id, "Select page:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text in ["1", "2", "3", "4"])
def set_page(msg):
    page = msg.text
    safe_set("page", page)
    bot.reply_to(msg, f".mode-{page}")


@bot.message_handler(commands=["mirror"])
def toggle_mirror(msg):
    with state_lock:
        current = state.get("mirror", False)
        new_val = not bool(current)

    safe_set("mirror", new_val)
    bot.reply_to(msg, f"Mirror: {'ON' if new_val else 'OFF'}")


@bot.message_handler(commands=["off"])
def shutdown(msg):
    bot.reply_to(msg, "Shutting down...")
    os.system("sudo shutdown -h now")


@bot.message_handler(commands=["rename", "setname"])
def rename(msg):
    try:
        new = msg.text.split(maxsplit=1)[1].strip().upper()
        safe_set("name", new)
        bot.reply_to(msg, f"Name set: {new}")
    except Exception:
        bot.reply_to(msg, "Usage: /rename NAME")


# ----------------------- MEDIA HANDLERS -----------------------

@bot.message_handler(commands=["gif"])
def gif_url(msg):
    try:
        url = msg.text.split(maxsplit=1)[1].strip()
        safe_multi(content_type="image", content_url=url)
        bot.reply_to(msg, "GIF added.")
    except Exception:
        bot.reply_to(msg, "Usage: /gif URL")


@bot.message_handler(commands=["show"])
def show_from_url(msg):
    try:
        url = msg.text.split(maxsplit=1)[1].strip()
        ext = url.lower().split(".")[-1]

        safe_multi(
            content_type="image" if ext in ("jpg", "jpeg", "png", "gif") else "video",
            content_url=url
        )
        bot.reply_to(msg, "Content loaded.")
    except Exception:
        bot.reply_to(msg, "Usage: /show URL")


@bot.message_handler(commands=["yt"])
def youtube(msg):
    try:
        url = msg.text.split(maxsplit=1)[1].strip()
        match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)

        if not match:
            bot.reply_to(msg, "Bad link.")
            return

        video_id = match.group(1)
        safe_multi(content_type="youtube", content_url=video_id)
        bot.reply_to(msg, "YouTube loaded. Switch to page 4.")
    except Exception:
        bot.reply_to(msg, "Usage: /yt URL")


@bot.message_handler(content_types=["animation", "document", "video"])
def upload_media(msg):
    try:
        file_info = (
            bot.get_file(msg.animation.file_id) if msg.animation else
            bot.get_file(msg.video.file_id) if msg.video else
            bot.get_file(msg.document.file_id) if msg.document and msg.document.mime_type == "image/gif"
            else None
        )

        if not file_info:
            bot.reply_to(msg, "Can't read the file.")
            return

        ext = file_info.file_path.split(".")[-1]
        fname = f"content.{ext}"
        path = os.path.join(UPLOADS_DIR, fname)

        data = bot.download_file(file_info.file_path)
        with open(path, "wb") as f:
            f.write(data)

        safe_multi(
            content_type="video" if ext in ("mp4", "webm") else "image",
            content_url=f"/static/uploads/{fname}?t={int(time.time())}"
        )

        bot.reply_to(msg, "Media saved locally.")
    except Exception as e:
        bot.reply_to(msg, f"Error: {e}")


# ---------------------------------------------------------
# BOT THREAD — auto-restarts on any crash
# ---------------------------------------------------------

def run_bot():
    backoff = 5
    while True:
        try:
            log.info("[Bot] Starting polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            log.error("[Bot] Polling crashed: %s. Restarting in %ds...", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        else:
            # infinity_polling exited cleanly — restart immediately
            backoff = 5
            log.warning("[Bot] Polling stopped unexpectedly, restarting...")


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    state.update(load_state())

    threading.Thread(target=stats_loop, daemon=True, name="stats").start()
    threading.Thread(target=run_bot, daemon=True, name="telegram-bot").start()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
