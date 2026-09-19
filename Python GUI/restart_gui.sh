#!/bin/bash
PI_DIR="/home/tim/ground-station-gui"
VENV_PY="$PI_DIR/venv/bin/python3"
ENTRY="gui2.py"

pkill -f "$ENTRY" 2>/dev/null
sleep 1

cd "$PI_DIR" || exit 1
export DISPLAY=:0

nohup "$VENV_PY" "$ENTRY" > gui.log 2>&1 &
disown

echo "GUI launched."
