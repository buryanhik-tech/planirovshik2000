#!/usr/bin/env bash
# Сервер + бот + туннель с автоматическим переподключением.
#
# Бесплатные туннели рвут соединение каждые несколько десятков минут и выдают
# новый адрес. Поэтому туннель здесь под присмотром: как только он падает,
# скрипт поднимает следующий и кладёт свежий адрес в .webapp_url — бот читает
# этот файл при каждой отрисовке кнопки, перезапускать его не нужно.
set -u
cd "$(dirname "$0")"

PORT_LOCAL=$(grep '^PORT=' .env | cut -d= -f2- | tr -d ' ')
PORT_LOCAL=${PORT_LOCAL:-8080}
URL_FILE=.webapp_url
PID_FILE=.start.pid
LOG=/tmp/todo-tunnel.log
SERVER_PID=""
TUNNEL_PID=""
URL=""

cleanup() {
  echo ""
  echo "⏹  Останавливаю…"
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  rm -f "$URL_FILE" "$PID_FILE"
  exit 0
}
trap cleanup INT TERM

# --- один экземпляр за раз --------------------------------------------------
# Два запущенных start.sh дерутся за порт и за файл адреса — мини-приложение
# после этого открывается белым экраном. Поэтому старый экземпляр снимаем.
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ℹ️  Уже запущен другой экземпляр (pid $OLD_PID) — останавливаю его."
    pkill -9 -P "$OLD_PID" 2>/dev/null      # сервер и туннель
    kill -9 "$OLD_PID" 2>/dev/null          # -9, чтобы его trap не стёр общие файлы
    sleep 2
  fi
fi
echo $$ > "$PID_FILE"

# --- окружение --------------------------------------------------------------
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt

TOKEN=$(grep '^BOT_TOKEN=' .env | cut -d= -f2-)
case "$TOKEN" in
  [0-9]*:*) ;;
  *) echo ""
     echo "⚠️  BOT_TOKEN в .env не заполнен — бот не запустится."
     echo "    Возьми токен у @BotFather (/newbot) и впиши:  open -e .env"
     echo "" ;;
esac

if lsof -ti:"$PORT_LOCAL" >/dev/null 2>&1; then
  echo "⚠️  Порт $PORT_LOCAL занят — освобождаю…"
  kill -9 $(lsof -ti:"$PORT_LOCAL") 2>/dev/null
  sleep 1
fi

# --- сервер и бот -----------------------------------------------------------
rm -f "$URL_FILE"
./.venv/bin/python main.py &
SERVER_PID=$!
sleep 3

# --- туннель ----------------------------------------------------------------
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o ConnectTimeout=10"

raise_tunnel() {   # $1 — имя, $2 — regexp адреса, $3… — команда
  local name="$1" pattern="$2"; shift 2
  : > "$LOG"
  "$@" > "$LOG" 2>&1 &
  TUNNEL_PID=$!
  local i
  for i in $(seq 1 25); do
    sleep 1
    URL=$(grep -oE "$pattern" "$LOG" 2>/dev/null | grep -v '^https://api\.' | head -1)
    [ -n "$URL" ] && return 0
    kill -0 "$TUNNEL_PID" 2>/dev/null || break
  done
  kill "$TUNNEL_PID" 2>/dev/null
  TUNNEL_PID=""
  URL=""
  return 1
}

attempt=0
while true; do
  # сервер мог упасть — тогда и мы выходим
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "❌ Сервер остановился. Смотри сообщения выше."
    exit 1
  fi

  attempt=$((attempt + 1))
  [ "$attempt" -eq 1 ] && echo "⏳ Поднимаю HTTPS-туннель…" || echo "🔄 Переподключаю туннель (попытка $attempt)…"

  raise_tunnel "localhost.run" 'https://[a-z0-9-]+\.lhr\.life' \
      ssh $SSH_OPTS -R 80:localhost:"$PORT_LOCAL" nokey@localhost.run \
    || raise_tunnel "serveo.net" 'https://[a-z0-9-]+\.serveo\.net' \
      ssh $SSH_OPTS -R 80:localhost:"$PORT_LOCAL" serveo.net \
    || raise_tunnel "cloudflared" 'https://[a-z0-9-]+\.trycloudflare\.com' \
      ./tools/cloudflared tunnel --url "http://localhost:$PORT_LOCAL"

  if [ -z "$URL" ]; then
    echo "   ✗ ни один туннель не поднялся, жду 15 секунд…"
    sleep 15
    continue
  fi

  printf '%s' "$URL" > "$URL_FILE"
  python3 - "$URL" <<'PY'
import pathlib, re, sys
p = pathlib.Path('.env')
p.write_text(re.sub(r'^WEBAPP_URL=.*$', 'WEBAPP_URL=' + sys.argv[1], p.read_text(), flags=re.M))
PY
  cat <<BANNER

────────────────────────────────────────────────────────────
  ✅ Мини-приложение доступно:  $URL

  В боте нажми /start — кнопка «🚀 Открыть To-Do» подхватит
  этот адрес сама. При обрыве туннеля адрес сменится, и
  кнопка снова обновится автоматически: жать /start заново.
────────────────────────────────────────────────────────────

BANNER

  wait "$TUNNEL_PID"          # ждём, пока туннель не оборвётся
  TUNNEL_PID=""
  # файл с адресом НЕ трогаем: localhost.run обычно возвращает тот же адрес,
  # и кнопка остаётся рабочей всё время переподключения
  echo ""
  echo "⚠️  Туннель оборвался (так бывает на бесплатных). Поднимаю заново…"
  sleep 2
done
