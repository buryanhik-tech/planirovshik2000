#!/usr/bin/env bash
# Скачивает cloudflared в tools/ — запасной туннель для start.sh.
# Нужен только если localhost.run и serveo.net недоступны.
set -e
cd "$(dirname "$0")"
mkdir -p tools && cd tools

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  FILE=cloudflared-darwin-arm64.tgz ;;
  Darwin-x86_64) FILE=cloudflared-darwin-amd64.tgz ;;
  Linux-x86_64)  FILE=cloudflared-linux-amd64 ;;
  Linux-aarch64) FILE=cloudflared-linux-arm64 ;;
  *) echo "❌ Неизвестная платформа: $(uname -s)-$(uname -m)"; exit 1 ;;
esac

echo "⏳ Скачиваю $FILE…"
curl -fsSL -o "$FILE" "https://github.com/cloudflare/cloudflared/releases/latest/download/$FILE"
case "$FILE" in
  *.tgz) tar -xzf "$FILE" && rm "$FILE" ;;
  *)     mv "$FILE" cloudflared ;;
esac
chmod +x cloudflared
./cloudflared --version
echo "✅ Готово: tools/cloudflared"
