import sys
from pathlib import Path

pytest_plugins = ["pytest_homeassistant_custom_component"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))