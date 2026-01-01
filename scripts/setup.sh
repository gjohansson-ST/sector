#!/bin/sh

set -e

cd "$(dirname "$0")/.."
python3 -m pip install \
      homeassistant \
      debugpy \
      pytest \
      pytest-asyncio \
      pytest-homeassistant-custom-component