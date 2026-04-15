"""Top-level package for mlx_whisper.

This module exposes a safe `app` reference and `__version__` metadata.
Importing `src` will attempt to import `src.main` to retrieve the FastAPI
`app` instance, but failures are handled gracefully so importing the package
does not crash the application in environments where `src.main` cannot be
initialized.
"""

from importlib import import_module

__all__ = ["app", "__version__"]

try:
	_main = import_module("src.main")
	app = getattr(_main, "app", None)
	__version__ = getattr(app, "version", "0.1.1")
except Exception:
	app = None
	__version__ = "0.1.1"
