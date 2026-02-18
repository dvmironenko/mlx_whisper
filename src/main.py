"""Main FastAPI application."""
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import after setting path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add parent directory for src imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import HOST, PORT, DEBUG, logger
from api import router

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
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting MLX-Whisper REST API on http://{HOST}:{PORT}")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
    )
