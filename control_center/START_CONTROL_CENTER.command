#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/robot_control_center.py" &
sleep 1
open "http://127.0.0.1:8767"
