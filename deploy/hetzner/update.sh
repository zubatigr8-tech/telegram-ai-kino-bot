#!/usr/bin/env bash
# Ikkala botning kodini GitHub'dan yangilab, qayta ishga tushiradi. Ishlatish: bash update.sh
set -euo pipefail
BASE=/opt/bots

for name in kinobot videobot; do
  app="$BASE/$name/app"
  [[ -d "$app/.git" ]] || continue
  echo "==> $name yangilanmoqda..."
  branch=$(runuser -u bots -- git -C "$app" rev-parse --abbrev-ref HEAD)
  runuser -u bots -- git -C "$app" fetch --quiet origin "$branch"
  runuser -u bots -- git -C "$app" reset --quiet --hard "origin/$branch"
  runuser -u bots -- "$app/.venv/bin/pip" install --quiet -r "$app/requirements.txt"
  systemctl restart "$name"
done
sleep 5
for name in kinobot videobot; do
  [[ -d "$BASE/$name/app/.git" ]] || continue
  if systemctl is-active --quiet "$name"; then
    echo "✅ $name ishlayapti"
  else
    echo "❌ $name ishlamayapti — sababini ko'rish: journalctl -u $name -n 50"
  fi
done
