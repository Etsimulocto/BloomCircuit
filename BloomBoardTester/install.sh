#!/usr/bin/env bash
set -e
sudo apt update
sudo apt install -y python3-tk python3-serial
if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli is required but was not found. Install it first, then rerun this script."
  exit 1
fi
arduino-cli core update-index
arduino-cli core install esp32:esp32 || true
chmod +x "$(dirname "$0")/board_tester.py" "$(dirname "$0")/run.sh"
echo "Installed. Run: ./run.sh"
