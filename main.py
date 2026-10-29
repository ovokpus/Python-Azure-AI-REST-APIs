"""Process entry point for ``uvicorn main:app`` and Gunicorn.

The FastAPI instance lives in :mod:`app.main`. This module exists so the
Azure App Service startup command keeps working:

``gunicorn -w 2 -k uvicorn.workers.UvicornWorker main:app``
"""

from app.main import app

__all__ = ["app"]
