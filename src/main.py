"""Main FastAPI application."""
import os
import sys

# Configure paths before any other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add parent directory for src imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file before any other imports. If `python-dotenv` is not
# available in the environment, fall back to a no-op loader and log a
# warning so the module can still be imported for tests or other tooling.
try:
    from dotenv import load_dotenv
except Exception:
    import logging

    logging.getLogger(__name__).warning("python-dotenv not installed; skipping .env load")

    # Define a permissive fallback that accepts any arguments.  The
    # ``*_, **__`` signature ensures compatibility with the real
    # ``load_dotenv`` regardless of its exact parameters.
    def load_dotenv(*_, **__) -> bool:  # type: ignore
        return False

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import HOST, PORT, DEBUG, logger
from src.api import router

# Initialize FastAPI app
app = FastAPI(
    title="MLX-Whisper REST API",
    description="REST API for audio transcription using Apple's optimized Whisper model",
    version="1.0.0",
)

# Templates (must be defined before use)
templates = Jinja2Templates(directory="src/templates")

# Mount static files (must be after routes)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Include API router
app.include_router(router)


@app.get("/", include_in_schema=False)
async def read_root(request: Request):
    """Root endpoint with web interface."""
    return templates.TemplateResponse("new_index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting MLX-Whisper REST API on http://{HOST}:{PORT}")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
    )
