"""
Speech-to-Text Wrapper using faster-whisper
Streaming ASR for real-time transcription
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None
    logging.warning("faster-whisper not installed. STT will not work.")

from config import (
    STT_MODEL,
    STT_DEVICE,
    STT_COMPUTE_TYPE,
    STT_LANGUAGE,
    STT_BEAM_SIZE,
    MODELS_DIR,
)

logger = logging.getLogger(__name__)


class STTEngine:
    """
    Speech-to-Text engine using faster-whisper.
    Supports streaming transcription with confidence scores.
    """

    def __init__(
        self,
        model_size: str = STT_MODEL,
        device: str = STT_DEVICE,
        compute_type: str = STT_COMPUTE_TYPE,
        language: Optional[str] = STT_LANGUAGE,
    ):
        """
        Initialize STT engine.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on (cpu or cuda)
            compute_type: Compute type (int8, float16, float32)
            language: Language code (hi, en, or None for auto-detect)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.model = None

        logger.info(f"Initializing STT engine: {model_size} on {device} ({compute_type})")

    def load_model(self):
        """Load the Whisper model."""
        if not WhisperModel:
            raise RuntimeError("faster-whisper not installed")

        try:
            logger.info(f"Loading Whisper model '{self.model_size}'...")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(MODELS_DIR),
            )
            logger.info("✓ STT model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            raise

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        beam_size: int = STT_BEAM_SIZE,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            language: Language code override
            beam_size: Beam size for decoding

        Returns:
            Dictionary with:
                - text: Transcribed text
                - confidence: Average confidence score
                - language: Detected language
                - segments: List of segments with timestamps
        """
        if not self.model:
            self.load_model()

        lang = language or self.language

        try:
            segments, info = self.model.transcribe(
                audio_path,
                language=lang,
                beam_size=beam_size,
                vad_filter=True,  # Voice activity detection
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=500,
                ),
            )

            # Collect segments
            segments_list = []
            full_text = []
            confidences = []

            for segment in segments:
                segments_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "confidence": segment.avg_logprob,  # Log probability as confidence proxy
                })
                full_text.append(segment.text.strip())
                confidences.append(segment.avg_logprob)

            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            result = {
                "text": " ".join(full_text),
                "confidence": avg_confidence,
                "language": info.language if hasattr(info, 'language') else lang,
                "segments": segments_list,
            }

            logger.debug(f"Transcribed: '{result['text']}' (confidence: {avg_confidence:.3f})")
            return result

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "language": lang or "unknown",
                "segments": [],
                "error": str(e),
            }

    def transcribe_stream(self, audio_chunks):
        """
        Transcribe streaming audio chunks.

        Note: faster-whisper doesn't support true streaming yet.
        This method is a placeholder for future implementation.
        Current approach: accumulate chunks and transcribe when complete.
        """
        raise NotImplementedError("Streaming not yet implemented. Use batch transcription.")

    def is_low_confidence(self, confidence: float, threshold: float = 0.5) -> bool:
        """
        Check if transcription confidence is below threshold.

        Args:
            confidence: Confidence score
            threshold: Minimum acceptable confidence

        Returns:
            True if confidence is too low
        """
        return confidence < threshold


# Global STT instance (lazy loaded)
_stt_engine = None


def get_stt_engine() -> STTEngine:
    """Get global STT engine instance."""
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = STTEngine()
    return _stt_engine


def transcribe_audio(audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to transcribe audio.

    Args:
        audio_path: Path to audio file
        language: Language code

    Returns:
        Transcription result dictionary
    """
    engine = get_stt_engine()
    return engine.transcribe(audio_path, language=language)
