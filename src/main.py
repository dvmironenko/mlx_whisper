"""Main FastAPI application."""
import os
import sys

# Configure paths before any other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add parent directory for src imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env file is loaded by src/config.py before any other imports

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from src.config import HOST, PORT, DEBUG, DEFAULT_MODEL, logger
from src.api import router
from src.models.model_cache import ModelCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Предзагрузка моделей при запуске сервера."""
    try:
        cache = ModelCache.get_instance()
        models_dir = os.getenv("MODELS_DIR", "models")
        model_mapping = {
            "tiny": os.path.join(models_dir, "whisper-tiny"),
            "base": os.path.join(models_dir, "whisper-base"),
            "small": os.path.join(models_dir, "whisper-small"),
            "medium": os.path.join(models_dir, "whisper-medium"),
            "turbo": os.path.join(models_dir, "whisper-turbo"),
            "large": os.path.join(models_dir, "whisper-large"),
        }
        model_path = model_mapping.get(DEFAULT_MODEL, os.path.join(models_dir, "whisper-large"))

        if not os.path.exists(model_path):
            model_path = f"mlx-community/whisper-{DEFAULT_MODEL}"

        logger.info(f"Preloading model '{DEFAULT_MODEL}' from {model_path}")
        cache.load_model(DEFAULT_MODEL, model_path)
        logger.info(f"Model '{DEFAULT_MODEL}' preloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to preload model: {e}")

    yield


# Initialize FastAPI app
app = FastAPI(
    title="MLX-Whisper REST API",
    description="REST API for audio transcription using Apple's optimized Whisper model",
    version="1.0.0",
    lifespan=lifespan,
)

# Templates (must be defined before use)
templates = Jinja2Templates(directory="src/templates")

# Mount static files (must be after routes)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Include API router
app.include_router(router)


@app.get("/", include_in_schema=False)
async def read_root(request: Request):
    """Jobs list endpoint."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/uploads", include_in_schema=False)
async def uploads_page(request: Request):
    """Upload endpoint with upload interface."""
    return templates.TemplateResponse("uploads.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting MLX-Whisper REST API on http://{HOST}:{PORT}")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
    )
