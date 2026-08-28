#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
python3 -m http.server 8088 &
sleep 1
open "http://localhost:8088"
