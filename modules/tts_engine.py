"""
modules/tts_engine.py
Language detection and voiceover processing.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional
import soundfile as sf

logger = logging.getLogger("TTSEngine")

class TTSManager:
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")

    def detect_language(self, text: str) -> str:
        """Detects if script is Bengali or English based on Unicode frequency."""
        bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        total_letters = len(re.findall(r'\w', text))
        if total_letters > 0 and (bengali_chars / total_letters) > 0.15:
            return "bn"
        return "en"

    def synthesize_english(self, text: str, output_path: Path) -> Path:
        """High-speed, neural English voiceover via Kokoro TTS."""
        logger.info("Generating English voiceover using Kokoro TTS...")
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code='a')
        generator = pipeline(text, voice='af_heart', speed=1.0, split_pattern=r'\n+')
        
        segments = []
        for _, _, audio in generator:
            segments.append(audio)
            
        import numpy as np
        full_audio = np.concatenate(segments)
        sf.write(str(output_path), full_audio, 24000)
        return output_path

    def synthesize_bengali(self, text: str, output_path: Path) -> Path:
        """Authoritative Bengali documentary voiceover via Google GenAI."""
        logger.info("Generating Bengali voiceover via Google GenAI...")
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is required for Bengali narration.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Narrate this historical battle with a serious, documentary tone: {text}",
            config=types.GenerateContentConfig(response_mime_type="audio/mp3")
        )
        with open(output_path, "wb") as f:
            f.write(response.candidates[0].content.parts[0].inline_data.data)
        return output_path

    def process(self, script_file: Path, existing_audio: Optional[Path], output_dir: Path) -> Path:
        if existing_audio and existing_audio.exists():
            logger.info(f"Existing audio track found: {existing_audio.name}. Skipping TTS.")
            return existing_audio

        with open(script_file, "r", encoding="utf-8") as f:
            text = f.read().strip()

        lang = self.detect_language(text)
        if lang == "bn":
            return self.synthesize_bengali(text, output_dir / "voiceover.mp3")
        return self.synthesize_english(text, output_dir / "voiceover.wav")
