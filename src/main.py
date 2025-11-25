from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import tempfile
from typing import Optional, Any, Dict, List
import mlx_whisper
import numpy as np
from fastapi.templating import Jinja2Templates
import time
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import math
import uuid  # Added for job ID generation

# Add logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported audio extensions - Added WEBM and MP4 formats
AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".webm", ".mp4"
}

# Supported models with their Hugging Face paths
SUPPORTED_MODELS = {
    "tiny": "models/whisper-tiny",
    "base": "models/whisper-base", 
    "small": "models/whisper-small",
    "medium": "models/whisper-medium",
    "turbo": "models/whisper-turbo",
    "large": "models/whisper-large",
}

UPLOADS_DIR = "uploads"
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

# Initialize ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=4)  # Ограничиваем до 4 потоков

# Initialize FastAPI app
app = FastAPI(
    title="MLX-Whisper REST API",
    description="REST API for audio transcription using Apple's optimized Whisper model",
    version="1.0.0"
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="src/templates")

# Job status tracking dictionary
job_status: Dict[str, Dict] = {}

def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types, handling NaN values
    """
    if isinstance(obj, np.ndarray):
        # Handle array elements recursively
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        # Handle NaN and infinity values
        if np.isnan(obj) or np.isinf(obj):
            return None  # Replace invalid floats with null
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        # Recursively process dictionary values
        result = {}
        for key, value in obj.items():
            # Convert keys to strings if they aren't already
            str_key = str(key) if not isinstance(key, str) else key
            result[str_key] = convert_numpy_types(value)
        return result
    elif isinstance(obj, list):
        # Recursively process list elements
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, float):
        # Protect against NaN / Inf in native Python float
        if math.isnan(obj) or math.isinf(obj):
            return None 
        return obj
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    else:
        # For any other types that might be problematic, convert to string
        return str(obj)

def safe_json_serialize(data: Any) -> str:
    """
    Safely serialize data to JSON, handling all edge cases including NaN values
    """
    try:
        # First convert any numpy types
        converted_data = convert_numpy_types(data)
        
        # Use json.dumps with custom handling for NaN/Infinity
        return json.dumps(converted_data, allow_nan=False)
    except Exception as e:
        logger.error(f"Failed to serialize data to JSON: {str(e)}")
        # Fallback: create a minimal safe response
        return json.dumps({"error": "Serialization failed", "details": str(e)})


def transcribe_audio_sync(
    file_path: str,
    language: Optional[str],
    task: str,
    model: str,
    word_timestamps: bool,
    condition_on_previous_text: bool,
    no_speech_threshold: float,
    hallucination_silence_threshold: float,
    job_id: str
) -> Dict:
    """
    Synchronous transcription function to run in thread pool
    """
    try:
        # Update job status to processing
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["start_time"] = time.time()
        
        # Transcribe the audio file using MLX-Whisper directly
        result = mlx_whisper.transcribe(
            file_path,
            language=language or "ru",
            task=task,
            path_or_hf_repo=SUPPORTED_MODELS[model],
            word_timestamps=word_timestamps,
            condition_on_previous_text=condition_on_previous_text,
            no_speech_threshold=no_speech_threshold,
            hallucination_silence_threshold=hallucination_silence_threshold
        )
        
        # Process result to ensure it's JSON serializable by converting all numpy types
        if isinstance(result, dict):
            # Convert the entire result dictionary to native Python types
            converted_result = convert_numpy_types(result)
            
            # Now safely extract text and segments from the dict
            text = str(converted_result.get("text", "")) if "text" in converted_result and converted_result["text"] is not None else ""
            segments = converted_result.get("segments", [])
        elif isinstance(result, str):
            # Handle case where result is a string
            text = result
            segments = []
        else:
            # Handle other cases (shouldn't happen with MLX-Whisper)
            text = str(result) if result is not None else ""
            segments = []
            
        # Update job status to completed
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["end_time"] = time.time()
        job_status[job_id]["duration"] = job_status[job_id]["end_time"] - job_status[job_id]["start_time"]
        job_status[job_id]["result"] = {
            "text": text,
            "language": language or "ru",
            "model": model,
            "task": task,
            "word_timestamps": word_timestamps,
            "condition_on_previous_text": condition_on_previous_text,
            "no_speech_threshold": no_speech_threshold,
            "hallucination_silence_threshold": hallucination_silence_threshold,
            "segments": segments
        }
        
        # --- NEW: Print job_status to console after successful completion ---
        print(f"=== JOB COMPLETED ===")
        print(f"Job ID: {job_id}")
        print(f"Status: {job_status[job_id]['status']}")
        print(f"File: {job_status[job_id].get('filename', 'N/A')}")
        print(f"Model: {job_status[job_id]['model']}")
        print(f"Language: {job_status[job_id]['language']}")
        print(f"Task: {job_status[job_id]['task']}")
        print(f"Duration: {job_status[job_id]['duration']:.2f} seconds")
        print(f"======================")
        
        return job_status[job_id]["result"]
    except Exception as e:
        logger.error(f"Transcription failed for job {job_id}: {str(e)}")
        # Update job status to failed
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Root endpoint with web interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/models")
async def get_models():
    """Get list of supported models"""
    return {
        "supported_models": list(SUPPORTED_MODELS.keys())
    }

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a specific job
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

# Helper function to handle common transcription logic
async def process_transcription(
    file: UploadFile,
    language: Optional[str],
    task: str,
    model: str,
    word_timestamps: bool,
    condition_on_previous_text: bool,
    no_speech_threshold: float,
    hallucination_silence_threshold: float
) -> Dict:
    """
    Common function to handle transcription processing
    """
    # Validate file extension
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Supported formats: {', '.join(AUDIO_EXTENSIONS)}"
        )
    
    # Validate model size
    if model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model size. Supported models: {', '.join(SUPPORTED_MODELS.keys())}"
        )
    
    # Validate task
    if task not in ["transcribe", "translate"]:
        raise HTTPException(
            status_code=400,
            detail="Task must be either 'transcribe' or 'translate'"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    job_status[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "filename": file.filename,
        "model": model,
        "language": language,
        "task": task,
        "word_timestamps": word_timestamps,
        "condition_on_previous_text": condition_on_previous_text,
        "no_speech_threshold": no_speech_threshold,
        "hallucination_silence_threshold": hallucination_silence_threshold
    }
    
    # Save uploaded file to uploads directory with unique filename using job_id
    tmp_file_path = None
    result_text_path = None
    try:
        # Create a unique filename to avoid conflicts using job_id
        unique_filename = f"{job_id}_{file.filename}"
        tmp_file_path = os.path.join(UPLOADS_DIR, unique_filename)
        
        # Save the uploaded audio file to uploads directory
        with open(tmp_file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Log the transcription request
        logger.info(f"Transcribing {unique_filename} with model {model}, language {language}")
        
        # Execute transcription in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            transcribe_audio_sync,
            tmp_file_path,
            language,
            task,
            model,
            word_timestamps,
            condition_on_previous_text,
            no_speech_threshold,
            hallucination_silence_threshold,
            job_id
        )
        
        # Also save the transcription result as a text file in uploads directory using job_id
        result_filename = f"{job_id}_{os.path.splitext(file.filename)[0]}.txt"
        result_text_path = os.path.join(UPLOADS_DIR, result_filename)
        
        with open(result_text_path, 'w', encoding='utf-8') as f:
            f.write(result["text"])
        
        # Delete the uploaded audio file after successful transcription
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

        # Add file references to result
        result["uploaded_file"] = unique_filename
        result["result_file"] = result_filename
        result["job_id"] = job_id
        
        return result
        
    except Exception as e:
        logger.error(f"Transcription failed for {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )
    finally:
        # Clean up temporary file if it exists (regardless of success/failure)
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception as e:
                logger.error(f"Failed to clean up temporary file: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    task: str = Form("transcribe"),
    model: str = Form("large"),
    word_timestamps: str = Form("false"),
    condition_on_previous_text: str = Form("true"),
    no_speech_threshold: Optional[str] = Form("0.4"),
    hallucination_silence_threshold: Optional[str] = Form("0.8")
):
    """
    Transcribe audio file to text
    
    Parameters:
    - file: Audio file to transcribe
    - language: Language code (ISO-639) - defaults to 'ru'
    - task: Task type ('transcribe' or 'translate') - defaults to 'transcribe'
    - model: Whisper model size - defaults to 'large'
    - word_timestamps: Enable word-level timestamps - defaults to True
    - condition_on_previous_text: Use previous text for context - defaults to True
    - no_speech_threshold: Threshold for detecting no speech (default: 0.4)
    - hallucination_silence_threshold: Threshold for detecting hallucinations/silence (default: 0.8)
    """
    
    # Convert string parameters to appropriate types
    try:
        word_timestamps_bool = word_timestamps.lower() == "true"
        condition_on_previous_text_bool = condition_on_previous_text.lower() == "true"
        no_speech_threshold_float = float(no_speech_threshold) if no_speech_threshold is not None else 0.4
        hallucination_silence_threshold_float = float(hallucination_silence_threshold) if hallucination_silence_threshold is not None else 0.8
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameter values: {str(e)}"
        )
    
    return await process_transcription(
        file,
        language,
        task,
        model,
        word_timestamps_bool,
        condition_on_previous_text_bool,
        no_speech_threshold_float,
        hallucination_silence_threshold_float
    )

# Запуск сервера при прямом вызове файла
if __name__ == "__main__":
    import uvicorn
    print("Запуск MLX-Whisper REST API на http://localhost:8801")
    uvicorn.run("main:app", host="0.0.0.0", port=8801, reload=True)
