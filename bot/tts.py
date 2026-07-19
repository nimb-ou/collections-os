"""
Text-to-Speech Wrapper with Prompt Bank
Hybrid approach: pre-rendered fixed scripts + live synthesis for dynamic slots
"""

import logging
import hashlib
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

from config import (
    TTS_VOICE,
    TTS_VOICE_HI,
    TTS_SAMPLE_RATE,
    PROMPTS_DIR,
    AUDIO_CACHE_DIR,
)

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Text-to-Speech engine using Piper with prompt bank caching.

    Strategy:
    1. Fixed script lines are pre-rendered once and cached
    2. Dynamic slots (names, amounts, dates) are synthesized on-demand
    3. Audio segments are stitched with ffmpeg for final output
    """

    def __init__(
        self,
        voice_en: str = TTS_VOICE,
        voice_hi: str = TTS_VOICE_HI,
        sample_rate: int = TTS_SAMPLE_RATE,
    ):
        """
        Initialize TTS engine.

        Args:
            voice_en: English voice name
            voice_hi: Hindi voice name
            sample_rate: Audio sample rate
        """
        self.voice_en = voice_en
        self.voice_hi = voice_hi
        self.sample_rate = sample_rate
        self.prompt_bank = {}  # Cache of pre-rendered prompts

        logger.info(f"Initializing TTS engine (voices: {voice_en}, {voice_hi})")

    def _get_cache_key(self, text: str, language: str = "en") -> str:
        """
        Generate cache key for text.

        Args:
            text: Text to hash
            language: Language code

        Returns:
            MD5 hash as cache key
        """
        key_str = f"{language}:{text}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_audio_path(self, cache_key: str) -> Path:
        """Get path to cached audio file."""
        return AUDIO_CACHE_DIR / f"{cache_key}.wav"

    def synthesize(
        self,
        text: str,
        language: str = "en",
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            language: Language code (en or hi)
            use_cache: Use cached audio if available

        Returns:
            Path to generated audio file, or None on error
        """
        # Check cache
        cache_key = self._get_cache_key(text, language)
        audio_path = self._get_cached_audio_path(cache_key)

        if use_cache and audio_path.exists():
            logger.debug(f"Using cached audio for: '{text[:30]}...'")
            return str(audio_path)

        # Select voice
        voice = self.voice_hi if language == "hi" else self.voice_en

        try:
            # Note: This is a placeholder for actual Piper TTS synthesis
            # In production, you would call: piper --model <voice> --output_file <path>
            # For now, we'll create a simple implementation

            logger.info(f"Synthesizing ({language}): '{text[:50]}...'")

            # Placeholder: In production, use actual Piper command
            # For development, we'll just create an empty file
            # Real command would be:
            # subprocess.run([
            #     "piper",
            #     "--model", voice,
            #     "--output_file", str(audio_path),
            # ], input=text.encode(), check=True)

            # For now, create placeholder
            audio_path.touch()
            logger.debug(f"✓ Synthesized to: {audio_path}")

            return str(audio_path)

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    def stitch_audio_segments(
        self,
        audio_paths: List[str],
        output_path: str,
    ) -> bool:
        """
        Stitch multiple audio segments into one file using ffmpeg.

        Args:
            audio_paths: List of paths to audio files
            output_path: Output file path

        Returns:
            True if successful
        """
        try:
            # Create concat file for ffmpeg
            concat_file = Path(output_path).parent / "concat.txt"
            with open(concat_file, "w") as f:
                for path in audio_paths:
                    f.write(f"file '{path}'\n")

            # Run ffmpeg concat
            subprocess.run(
                [
                    "ffmpeg",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    "-y",  # Overwrite
                    output_path,
                ],
                check=True,
                capture_output=True,
            )

            concat_file.unlink()  # Clean up
            logger.debug(f"✓ Stitched {len(audio_paths)} segments to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Audio stitching failed: {e}")
            return False

    def render_prompt_template(
        self,
        template: str,
        slots: Dict[str, str],
        language: str = "en",
    ) -> Optional[str]:
        """
        Render a prompt template with dynamic slots.

        Strategy:
        1. Split template into fixed parts and slots
        2. Synthesize fixed parts (cached)
        3. Synthesize slot values (fresh)
        4. Stitch all segments together

        Args:
            template: Template string with {slot} placeholders
            slots: Dictionary of slot values
            language: Language code

        Returns:
            Path to final stitched audio, or None on error
        """
        # Parse template into segments
        segments = []
        current_pos = 0

        import re
        for match in re.finditer(r'\{(\w+)\}', template):
            # Add fixed text before slot
            if match.start() > current_pos:
                fixed_text = template[current_pos:match.start()]
                if fixed_text.strip():
                    segments.append(("fixed", fixed_text))

            # Add slot
            slot_name = match.group(1)
            if slot_name in slots:
                segments.append(("slot", slots[slot_name]))
            else:
                logger.warning(f"Missing slot value for: {slot_name}")
                segments.append(("slot", slot_name))  # Fallback

            current_pos = match.end()

        # Add remaining fixed text
        if current_pos < len(template):
            fixed_text = template[current_pos:]
            if fixed_text.strip():
                segments.append(("fixed", fixed_text))

        # Synthesize all segments
        audio_paths = []
        for seg_type, text in segments:
            use_cache = (seg_type == "fixed")  # Cache fixed parts
            audio_path = self.synthesize(text, language=language, use_cache=use_cache)
            if audio_path:
                audio_paths.append(audio_path)

        if not audio_paths:
            return None

        # Stitch segments
        output_path = str(AUDIO_CACHE_DIR / f"rendered_{hashlib.md5(template.encode()).hexdigest()}.wav")
        if self.stitch_audio_segments(audio_paths, output_path):
            return output_path

        return None


class PromptBank:
    """
    Manages pre-rendered prompt audio files.
    """

    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        """
        Initialize prompt bank.

        Args:
            prompts_dir: Directory containing prompt definitions
        """
        self.prompts_dir = prompts_dir
        self.prompts = {}
        self.tts_engine = TTSEngine()

    def load_prompts(self, language: str = "en"):
        """
        Load prompt definitions from JSON files.

        Args:
            language: Language code
        """
        prompt_file = self.prompts_dir / f"prompts_{language}.json"

        if not prompt_file.exists():
            logger.warning(f"Prompt file not found: {prompt_file}")
            return

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                self.prompts = json.load(f)

            logger.info(f"✓ Loaded {len(self.prompts)} prompts for language '{language}'")

        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")

    def get_prompt(self, prompt_id: str) -> Optional[str]:
        """
        Get prompt text by ID.

        Args:
            prompt_id: Prompt identifier

        Returns:
            Prompt text, or None if not found
        """
        return self.prompts.get(prompt_id)

    def render_prompt(
        self,
        prompt_id: str,
        slots: Optional[Dict[str, str]] = None,
        language: str = "en",
    ) -> Optional[str]:
        """
        Render prompt with optional slot values.

        Args:
            prompt_id: Prompt identifier
            slots: Dictionary of slot values
            language: Language code

        Returns:
            Path to rendered audio file
        """
        template = self.get_prompt(prompt_id)
        if not template:
            logger.error(f"Prompt not found: {prompt_id}")
            return None

        if slots:
            return self.tts_engine.render_prompt_template(template, slots, language)
        else:
            return self.tts_engine.synthesize(template, language=language, use_cache=True)


# Global instances
_tts_engine = None
_prompt_bank = None


def get_tts_engine() -> TTSEngine:
    """Get global TTS engine instance."""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
    return _tts_engine


def get_prompt_bank() -> PromptBank:
    """Get global prompt bank instance."""
    global _prompt_bank
    if _prompt_bank is None:
        _prompt_bank = PromptBank()
    return _prompt_bank
