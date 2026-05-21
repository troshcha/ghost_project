#!/bin/bash

### --- STOP CHROMIUM COMPLETELY ---
echo "[KIOSK] Killing old chromium..."
sudo pkill -9 -f chromium 2>/dev/null

### --- CLEAN BAD CHROMIUM PROFILES ---
echo "[KIOSK] Cleaning chromium cache..."
rm -rf ~/.config/chromium
rm -rf ~/.cache/chromium
rm -rf ~/.pki

mkdir -p ~/.config/chromium/Default

### --- DISABLE TRANSLATE POPUP ---
cat > ~/.config/chromium/Default/Preferences << 'EOF'
{
  "translate": { "enabled": false },
  "translate_site_blacklist": [],
  "browser": { "check_default_browser": false }
}
EOF

### --- WAIT FOR FLASK ---
echo "[KIOSK] Waiting for Flask..."
until curl -sf http://localhost:5000 > /dev/null; do
    sleep 1
done
echo "[KIOSK] Flask is up."

### --- START KIOSK MODE ---
echo "[KIOSK] Launching Chromium..."

DISPLAY=:0 chromium \
    --app=http://localhost:5000 \
    --start-fullscreen \
    --disable-gpu \
    --disable-software-rasterizer \
    --noerrdialogs \
    --password-store=basic \
    --no-default-browser-check \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-features=UseOzonePlatform,TranslateUI \
    --kiosk &
