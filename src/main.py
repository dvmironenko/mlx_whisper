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
import uuid
import subprocess
import shutil

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

# Maximum file size - 5GB
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB in bytes

# Memory optimization settings
MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer size for reading chunks
CHUNK_SIZE = 8192  # 8KB chunks for processing

UPLOADS_DIR = "uploads"
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

# Initialize ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=2)  # Reduced to 2 workers for better resource management

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
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        # Handle NaN and infinity values properly
        if np.isnan(obj) or np.isinf(obj):
            return None  # Replace invalid floats with null
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            str_key = str(key) if not isinstance(key, str) else key
            result[str_key] = convert_numpy_types(value)
        return result
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, np.void):
        return str(obj)
    elif isinstance(obj, np.str_):
        return str(obj)
    elif isinstance(obj, np.bytes_):
        return obj.decode('utf-8', errors='ignore')
    else:
        # For any other types that might be problematic, convert to string
        return str(obj)

def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize data for JSON serialization by replacing invalid values
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            result[key] = sanitize_for_json(value)
        return result
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        # Check for NaN and infinity values
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, np.floating):
        # Handle numpy floating point values
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    else:
        return obj

def safe_json_serialize(data: Any) -> str:
    """
    Safely serialize data to JSON, handling all edge cases including NaN values
    """
    try:
        # First convert any numpy types
        converted_data = convert_numpy_types(data)
        
        # Sanitize for JSON compatibility
        sanitized_data = sanitize_for_json(converted_data)
        
        # Use json.dumps with custom handling for NaN/Infinity
        return json.dumps(sanitized_data, allow_nan=False, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to serialize data to JSON: {str(e)}")
        # Fallback: create a minimal safe response
        return json.dumps({"error": "Serialization failed", "details": str(e)})

def convert_to_wav(input_file_path: str, output_file_path: str) -> bool:
    """
    Convert audio file to WAV format using ffmpeg with specific parameters
    Parameters: -acodec pcm_s16le -ar 16000 -ac 1
    """
    try:
        # Run ffmpeg command to convert to WAV with specific parameters
        cmd = [
            "ffmpeg",
            "-i", input_file_path,
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_file_path
        ]
        
        # Run the command and capture output
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True
        )
        
        # Check if conversion was successful
        if result.returncode == 0 and os.path.exists(output_file_path):
            logger.info(f"Successfully converted {input_file_path} to {output_file_path}")
            return True
        else:
            logger.error(f"FFmpeg conversion failed for {input_file_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error converting {input_file_path}: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please install ffmpeg to enable audio conversion.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error converting {input_file_path}: {str(e)}")
        return False

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
            
            # Sanitize for JSON compatibility
            sanitized_result = sanitize_for_json(converted_result)
            
            # Now safely extract text and segments from the dict
            text = str(sanitized_result.get("text", "")) if "text" in sanitized_result and sanitized_result["text"] is not None else ""
            segments = sanitized_result.get("segments", [])
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
        
        # Print job_status to console after successful completion
        logger.info(f"=== JOB COMPLETED ===")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Status: {job_status[job_id]['status']}")
        logger.info(f"File: {job_status[job_id].get('filename', 'N/A')}")
        logger.info(f"Model: {job_status[job_id]['model']}")
        logger.info(f"Language: {job_status[job_id]['language']}")
        logger.info(f"Task: {job_status[job_id]['task']}")
        logger.info(f"Duration: {job_status[job_id]['duration']:.2f} seconds")
        logger.info(f"======================")
        
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

# Helper function to handle common transcription logic with memory optimization
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
    Common function to handle transcription processing with memory optimization
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
    
    # Validate file size (max 5GB)
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum file size is 5GB"
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
    converted_file_path = None
    result_text_path = None
    try:
        # Create a unique filename to avoid conflicts using job_id
        unique_filename = f"{job_id}_{file.filename}"
        tmp_file_path = os.path.join(UPLOADS_DIR, unique_filename)
        
        # Save the uploaded audio file with chunked writing to optimize memory usage
        with open(tmp_file_path, 'wb') as f:
            # Read file in chunks to avoid memory issues with large files
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
        
        # Convert file to WAV format using ffmpeg with specific parameters
        converted_filename = f"{job_id}_{os.path.splitext(file.filename)[0]}.wav"
        converted_file_path = os.path.join(UPLOADS_DIR, converted_filename)
        
        logger.info(f"Converting {unique_filename} to WAV format...")
        if not convert_to_wav(tmp_file_path, converted_file_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to convert audio file to WAV format"
            )
        
        # Log the transcription request
        logger.info(f"Transcribing {converted_filename} with model {model}, language {language}")
        
        # Execute transcription in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            transcribe_audio_sync,
            converted_file_path,
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
        
        # Write result in chunks to optimize memory usage
        with open(result_text_path, 'w', encoding='utf-8') as f:
            # Write in chunks to handle large text outputs efficiently
            text_content = str(result["text"])
            for i in range(0, len(text_content), CHUNK_SIZE):
                f.write(text_content[i:i + CHUNK_SIZE])
        
        # Delete the uploaded audio file after successful transcription
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            
        # Delete the converted WAV file after successful transcription
        if converted_file_path and os.path.exists(converted_file_path):
            os.remove(converted_file_path)

        # Add file references to result
        result["uploaded_file"] = unique_filename
        result["result_file"] = result_filename
        result["job_id"] = job_id
        
        # Add duration to the result for frontend display
        if job_id in job_status and "duration" in job_status[job_id]:
            result["duration"] = job_status[job_id]["duration"]
        else:
            result["duration"] = None
        
        return result
        
    except Exception as e:
        logger.error(f"Transcription failed for {file.filename}: {str(e)}")
        # Clean up temporary files in case of error
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up temporary file: {str(cleanup_error)}")
        if converted_file_path and os.path.exists(converted_file_path):
            try:
                os.remove(converted_file_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up converted file: {str(cleanup_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

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
    uvicorn.run("src.main:app", host="0.0.0.0", port=8801, reload=True)
