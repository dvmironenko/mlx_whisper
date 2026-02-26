# Dev Commands

## Setup and Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r src/requirements.txt
```

## Running the Application

**Важно:** Приложение всегда должно запускаться в виртуальном окружении `venv`:

```bash
source .venv/bin/activate
python src/main.py
```

Сервер запускается на `http://localhost:8801`.

## Testing
```bash
# Manual testing with curl
curl -X POST "http://localhost:8801/transcribe" \
  -F "file=@tests/test.wav" \
  -F "language=ru"

# Using the web interface
Visit http://localhost:8801 in your browser

# Run unit tests
pytest tests/ -v
```
