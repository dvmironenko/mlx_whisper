# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a high-performance web service for audio transcription and translation using Apple's optimized Whisper model (MLX-Whisper). The service provides both a web interface and REST API for converting speech to text with support for multiple languages and flexible processing parameters.

## Key Architecture Components

1. **FastAPI Application** (`src/main.py`):
   - Main application entry point built with FastAPI
   - Handles HTTP requests and responses for audio transcription
   - Implements REST API endpoints for transcription operations

2. **Web Interface**:
   - HTML template (`src/templates/index.html`) with embedded JavaScript
   - CSS styling (`src/static/style.css`)
   - Provides user-friendly web interface for audio file upload and processing

3. **Audio Processing Pipeline**:
   - Audio format conversion using FFmpeg to WAV (16kHz, mono)
   - MLX-Whisper model integration for transcription
   - Memory-efficient chunked file processing for large audio files

4. **Model Support**:
   - Multiple Whisper model sizes (tiny, base, small, medium, turbo, large)
   - Model files stored in `models/` directory with specific paths

5. **Task Management**:
   - Job status tracking using in-memory dictionary
   - Unique job IDs for each transcription task
   - Thread pool executor for concurrent processing

## Development Commands

### Setup and Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r src/requirements.txt
```

### Running the Application
```bash
# Run the server
python src/main.py

# Server will start on http://localhost:8801
```

### Testing
```bash
# Manual testing with curl
curl -X POST "http://localhost:8801/transcribe" \
  -F "file=@tests/test.wav" \
  -F "language=ru"

# Using the web interface
# Visit http://localhost:8801 in your browser

# Run unit tests
pytest tests/ -v
```

## Code Structure

- `src/main.py`: Main FastAPI application with transcription logic
- `src/templates/index.html`: Web interface template
- `src/static/style.css`: CSS styling for web interface
- `models/`: Directory containing MLX-Whisper model files (tiny, base, small, medium, turbo, large)
- `tests/`: Test audio files for manual testing
- `uploads/`: Temporary directory for uploaded audio files (created automatically)

## Key Features and Design Patterns

1. **Memory Optimization**:
   - Chunked file reading/writing for handling large audio files efficiently
   - Thread pool execution for CPU-intensive transcription tasks

2. **Error Handling**:
   - Comprehensive error handling with proper HTTP status codes
   - Memory-safe cleanup of temporary files
   - JSON serialization with NaN/Infinity handling

3. **Multi-Format Support**:
   - Supports various audio formats (WAV, MP3, M4A, FLAC, AAC, OGG, WMA, WEBM, MP4)
   - Automatic conversion to WAV format using FFmpeg

4. **Configuration Options**:
   - Language selection (auto-detection or specific)
   - Task types (transcribe/translate)
   - Model size selection
   - Word-level timestamps option
   - Context-aware processing option

## Development Workflow

### Common Development Tasks:
1. **Adding new models**: Create directories in `models/` and update `SUPPORTED_MODELS` in `src/main.py`
2. **Modifying web interface**: Edit `src/templates/index.html` and `src/static/style.css`
3. **Extending API**: Add new endpoints in `src/main.py`
4. **Improving error handling**: Enhance error responses and logging in `src/main.py`

### Code Quality Standards:
- Follow PEP 8 Python style guidelines
- Use type annotations for function parameters and return values
- Implement proper error handling with HTTP exceptions
- Use async/await for I/O operations to maintain performance

### Testing Approach:
- Manual testing with audio files in `tests/` directory
- API endpoint integration testing
- Memory usage optimization verification