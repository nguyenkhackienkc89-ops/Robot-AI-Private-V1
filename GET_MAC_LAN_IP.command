#!/bin/bash
for IFACE in en0 en1 en2; do
  IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
  if [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "$IP"
    exit 0
  fi
done
exit 1
