"""
AI Voice Bot Configuration
Free, local, honest collections bot
"""

import os
from pathlib import Path

# Base paths
BOT_DIR = Path(__file__).parent
PROMPTS_DIR = BOT_DIR / "prompts"
FLOWS_DIR = BOT_DIR / "flows"
MODELS_DIR = BOT_DIR / "models"
AUDIO_CACHE_DIR = BOT_DIR / "audio_cache"

# Ensure directories exist
AUDIO_CACHE_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# STT Configuration (faster-whisper)
STT_MODEL = "small"  # small, medium, large
STT_DEVICE = "cpu"  # cpu or cuda
STT_COMPUTE_TYPE = "int8"  # int8, float16, float32
STT_LANGUAGE = "hi"  # hi (Hindi), en (English), or None for auto-detect
STT_BEAM_SIZE = 5

# TTS Configuration (Piper)
# TTS uses prompt bank - pre-rendered audio for fixed scripts
# Only dynamic slots (names, amounts, dates) are synthesized live
TTS_VOICE = "en_US-amy-medium"  # Default English voice
TTS_VOICE_HI = "hi_IN-kavya-medium"  # Hindi voice (if available)
TTS_SAMPLE_RATE = 22050

# NLU Configuration (Ollama Qwen)
NLU_MODEL = "qwen2.5:7b-instruct-q4_K_M"
NLU_ENDPOINT = "http://localhost:11434"
NLU_TEMPERATURE = 0.1  # Low for consistency
NLU_MAX_TOKENS = 200

# Conversation Configuration
MAX_TURNS = 20  # Maximum conversation turns
INTENT_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence for NLU
LOW_ASR_THRESHOLD = 0.5  # Below this, escalate to human
MAX_LOW_ASR_RETRIES = 2  # After this many low ASR, escalate

# Compliance Guardrails
RECORDING_DISCLOSURE_REQUIRED = True
MAX_COLLECTION_ASKS = 2  # Maximum times bot can ask for payment
MAX_PTP_WINDOW_DAYS = 7  # Maximum PTP date in future
ALLOWED_CONTACT_HOURS = (8, 19)  # 08:00 to 19:00 only
PROHIBITED_PHRASES = [
    "legal action",
    "police",
    "jail",
    "court",
    "arrest",
    "seize",
    "confiscate",
]

# Session Configuration
SESSION_TIMEOUT_SECONDS = 300  # 5 minutes
SILENCE_TIMEOUT_SECONDS = 10  # Hang up after 10s silence

# Database connection (for disposition logging)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://collectos_user:collectos_dev_password_change_in_production@localhost:5432/collectos"
)

# Disposition codes
DISPOSITIONS = {
    "CONNECT_RPC": "Connected with Right Party Contact",
    "CONNECT_WPC": "Connected with Wrong Party Contact",
    "PTP": "Promise to Pay captured",
    "PAID_CLAIM": "Customer claims already paid",
    "DISPUTE": "Customer disputes amount/loan",
    "HARDSHIP": "Customer claims financial hardship",
    "CALLBACK_REQUEST": "Customer requests callback",
    "ESCALATE_HUMAN": "Escalated to human agent",
    "NO_ANSWER": "No answer",
    "BUSY": "Line busy",
    "NOT_REACHABLE": "Number not reachable",
    "SILENCE": "Call answered but silence",
    "TECHNICAL_ERROR": "Technical error",
}

# Languages
LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish (Hindi-English mix)"
}

# Flow types
FLOW_TYPES = [
    "pre_due_reminder",
    "post_bounce_ptp",
    "ptp_reminder",
    "visit_confirm",
]
