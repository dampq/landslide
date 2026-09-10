"""Load optional local configuration without changing the parent project."""
import os
from pathlib import Path


def load_env():
    path = Path(__file__).with_name('.env')
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
