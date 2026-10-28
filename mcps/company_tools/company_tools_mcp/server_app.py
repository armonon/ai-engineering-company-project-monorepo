"""Uvicorn entrypoint. Configuration is read only when the server starts."""

from .config import Settings
from .server import create_server

app = create_server(Settings.from_env()).app
