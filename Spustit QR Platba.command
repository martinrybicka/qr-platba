#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

export HOST=127.0.0.1 PORT=8080
.venv/bin/python app.py &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM

for attempt in {1..30}; do
  if curl -fsS http://127.0.0.1:8080/ >/dev/null 2>&1; then
    open http://127.0.0.1:8080/
    echo "QR Platba běží na http://127.0.0.1:8080/"
    echo "Pro ukončení zavřete toto okno nebo stiskněte Ctrl+C."
    wait "$server_pid"
    exit $?
  fi
  sleep 1
done

echo "Server se nepodařilo spustit. Zkontrolujte, zda port 8080 není obsazený."
exit 1
