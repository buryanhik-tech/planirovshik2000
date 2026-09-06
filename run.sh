#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
# без туннеля публичного адреса нет — убираем остаток от start.sh
rm -f .webapp_url
pip install -q --upgrade pip
pip install -q -r requirements.txt
python main.py
