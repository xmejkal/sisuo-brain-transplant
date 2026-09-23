#!/bin/sh
# Deploy the firmware to a XIAO ESP32-C6 running MicroPython.
#
#   ./deploy.sh          copy the source as .py (edit on device, slower import)
#   ./deploy.sh --mpy    cross-compile first (smaller, much less heap at import)
#
# /config.json is never touched, so this bin's calibration survives a deploy.
set -e
cd "$(dirname "$0")"

# CPython's cache would otherwise be copied to the device — it is bigger than the source.
rm -rf smartbin/__pycache__ tests/__pycache__

echo "Removing the previous package (cp never deletes, so stale modules would linger)"
mpremote rm -r :smartbin || true
mpremote mkdir :smartbin || true

if [ "$1" = "--mpy" ]; then
    command -v mpy-cross >/dev/null || { echo "pip install mpy-cross"; exit 1; }
    for source in smartbin/*.py; do mpy-cross -march=rv32imc "$source"; done
    mpremote cp smartbin/*.mpy :smartbin/
    rm -f smartbin/*.mpy
else
    mpremote cp smartbin/*.py :smartbin/
fi

mpremote cp config.py main.py boot.py :
mpremote soft-reset
echo "Deployed. 'mpremote repl' to attach; Ctrl-C stops main.py."
