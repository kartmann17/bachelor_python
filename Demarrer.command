#!/bin/zsh
set -e
cd -- "${0:A:h}"
export CINEMA_DEBUG=1

if [[ ! -x .venv/bin/python ]]; then
  cinema_python=${PYTHON:-$(command -v python3.12 || command -v python3 || true)}
  if [[ -z "$cinema_python" ]] || ! "$cinema_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
    echo "Installe Python 3.12 ou une version plus récente, puis relance ce fichier."
    exit 1
  fi
  "$cinema_python" -m venv .venv
fi
if ! .venv/bin/python -c 'import django, ninja, qrcode, reportlab, whitenoise' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_demo
echo "Ouvre http://127.0.0.1:8000 dans ton navigateur."
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
