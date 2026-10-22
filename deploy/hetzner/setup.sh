#!/usr/bin/env bash
# Hetzner (yoki istalgan Ubuntu 24.04 VPS) ga ikkala botni o'rnatadi:
#   kinobot  — kino bot          (GitHub: main)
#   videobot — Video Downloader  (GitHub: claude/amazing-archimedes-bh1qbb)
#
# Ishlatish (serverda, root sifatida):
#   curl -fsSL https://raw.githubusercontent.com/zubatigr8-tech/telegram-ai-kino-bot/claude/amazing-archimedes-bh1qbb/deploy/hetzner/setup.sh -o setup.sh
#   bash setup.sh             — ikkala bot
#   bash setup.sh videobot    — faqat Video Downloader (kino bot bazasi hali ko'chirilmagan bo'lsa)
#
# Skriptni qayta ishga tushirish xavfsiz: mavjud .env va ma'lumotlar bazasi o'zgartirilmaydi,
# faqat kod va kutubxonalar yangilanadi.
set -euo pipefail

REPO_URL="https://github.com/zubatigr8-tech/telegram-ai-kino-bot.git"
BASE=/opt/bots
APP_USER=bots
CREDENTIALS=/root/bot-parollar.txt

# nom | GitHub branch | admin panel porti
BOTS=(
  "kinobot|main|8000"
  "videobot|claude/amazing-archimedes-bh1qbb|8001"
)

# Argument berilsa — faqat o'sha bot(lar) o'rnatiladi
if [[ $# -gt 0 ]]; then
  selected=()
  for entry in "${BOTS[@]}"; do
    for want in "$@"; do
      [[ "${entry%%|*}" == "$want" ]] && selected+=("$entry")
    done
  done
  if [[ ${#selected[@]} -eq 0 ]]; then
    echo "❌ Noma'lum bot: $* (mavjudlari: kinobot, videobot)"
    exit 1
  fi
  BOTS=("${selected[@]}")
fi

if [[ $EUID -ne 0 ]]; then
  echo "❌ Skriptni root sifatida ishga tushiring: sudo bash setup.sh"
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" ]]; then
  echo "⚠️  Bu skript Ubuntu 24.04 uchun yozilgan (sizda: ${PRETTY_NAME:-?}). Davom etilmoqda..."
fi

ask() {
  local prompt=$1 answer=""
  while [[ -z "$answer" ]]; do
    read -rp "$prompt" answer </dev/tty
    answer=$(echo "$answer" | tr -d '[:space:]')
  done
  echo "$answer"
}

as_app() { runuser -u "$APP_USER" -- "$@"; }

echo "==> 1/4 Tizim paketlari o'rnatilmoqda (python, git, ffmpeg)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-dev build-essential git ffmpeg sqlite3 ufw openssl

# Kichik serverda video ishlashda xotira yetmay qolmasligi uchun 2 GB swap
if ! swapon --show | grep -q .; then
  echo "==> Swap (2 GB) yaratilmoqda..."
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

id "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$BASE"
chown "$APP_USER:$APP_USER" "$BASE"
touch "$CREDENTIALS"
chmod 600 "$CREDENTIALS"

ADMIN_IDS=""

install_bot() {
  local name=$1 branch=$2 port=$3
  local root="$BASE/$name" app="$BASE/$name/app" data="$BASE/$name/data"

  echo
  echo "==> 2/4 [$name] kod yuklanmoqda (branch: $branch)..."
  mkdir -p "$root" "$data"
  chown "$APP_USER:$APP_USER" "$root" "$data"
  if [[ -d "$app/.git" ]]; then
    as_app git -C "$app" fetch --quiet origin "$branch"
    as_app git -C "$app" reset --quiet --hard "origin/$branch"
  else
    as_app git clone --quiet --branch "$branch" --single-branch "$REPO_URL" "$app"
  fi

  echo "==> 3/4 [$name] kutubxonalar o'rnatilmoqda (bir necha daqiqa)..."
  [[ -d "$app/.venv" ]] || as_app python3 -m venv "$app/.venv"
  as_app "$app/.venv/bin/pip" install --quiet --upgrade pip
  as_app "$app/.venv/bin/pip" install --quiet -r "$app/requirements.txt"

  if [[ ! -f "$app/.env" ]]; then
    echo
    echo "🔑 [$name] sozlamalari"
    local token password secret
    token=$(ask "   $name tokeni (@BotFather → /mybots → bot → API Token): ")
    if [[ -z "$ADMIN_IDS" ]]; then
      ADMIN_IDS=$(ask "   Admin Telegram ID (bir nechta bo'lsa vergul bilan): ")
    fi
    password=$(openssl rand -hex 8)
    secret=$(openssl rand -hex 32)
    cat > "$app/.env" <<ENV
BOT_TOKEN=$token
ADMIN_IDS=$ADMIN_IDS

DATABASE_URL=sqlite+aiosqlite:///$data/bot_database.db
BACKUP_DIR=$data/backups

ADMIN_PANEL_SECRET_KEY=$secret
ADMIN_PANEL_USERNAME=admin
ADMIN_PANEL_PASSWORD=$password
ADMIN_PANEL_HOST=0.0.0.0
ADMIN_PANEL_PORT=$port
PORT=$port

# Faqat Video Downloader ishlatadi (kino bot e'tiborsiz qoldiradi)
DOWNLOAD_DIR=$data/downloads
COOKIES_DIR=$data/cookies
MAX_CONCURRENT_DOWNLOADS=3
MAX_UPLOAD_MB=50
MAX_VIDEO_DURATION=1200
AUTO_APPROVE_JOIN_REQUESTS=true
ENV
    chown "$APP_USER:$APP_USER" "$app/.env"
    chmod 600 "$app/.env"
    {
      echo "[$name] admin panel: http://SERVER_IP:$port  login: admin  parol: $password"
    } >> "$CREDENTIALS"
  fi

  cat > "/etc/systemd/system/$name.service" <<UNIT
[Unit]
Description=Telegram bot: $name
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$app
Environment=PYTHONUNBUFFERED=1
Environment=PATH=$app/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$app/.venv/bin/python run_all.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

  ufw allow "$port/tcp" >/dev/null
}

for entry in "${BOTS[@]}"; do
  IFS='|' read -r name branch port <<<"$entry"
  install_bot "$name" "$branch" "$port"
done

ufw allow OpenSSH >/dev/null
ufw --force enable >/dev/null

echo
echo "==> 4/4 Botlar ishga tushirilmoqda..."
systemctl daemon-reload
for entry in "${BOTS[@]}"; do
  IFS='|' read -r name _ _ <<<"$entry"
  systemctl enable --quiet "$name"
  systemctl restart "$name"
done
sleep 8

echo
echo "================ NATIJA ================"
for entry in "${BOTS[@]}"; do
  IFS='|' read -r name _ _ <<<"$entry"
  if systemctl is-active --quiet "$name"; then
    echo "✅ $name ishlayapti"
  else
    echo "❌ $name ishlamayapti — sababini ko'rish: journalctl -u $name -n 50"
  fi
done
echo
echo "Admin panel parollari: cat $CREDENTIALS"
echo "Loglarni ko'rish:      journalctl -u videobot -f   (chiqish: Ctrl+C)"
echo "Kodni yangilash:       bash $BASE/videobot/app/deploy/hetzner/update.sh"
echo "========================================"
