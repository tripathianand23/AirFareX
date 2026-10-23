
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from backend import app

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

if not STATIC_DIR.exists():
    raise RuntimeError(
        f"Static directory not found: {STATIC_DIR}"
    )

app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="frontend",
)
