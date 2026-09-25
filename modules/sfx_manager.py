"""
modules/sfx_manager.py
Sound Effect manager with procedural waveform generation and master mixing.
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from typing import List, Dict, Any
from pydub import AudioSegment

class SFXManager:
    def __init__(self, workspace_dir: Path):
        self.sfx_dir = workspace_dir / "sfx_cache"
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self._generate_procedural_sfx_library()

    def _generate_procedural_sfx_library(self):
        """Generates crisp audio cues programmatically to eliminate reliance on external downloads."""
        sr = 44100

        # 1. War Drums (Deep low sine with exponential decay)
        t_drum = np.linspace(0, 1.5, int(sr * 1.5), False)
        drum_decay = np.exp(-t_drum * 7.0)
        drum_wave = (np.sin(2 * np.pi * 55 * t_drum) + 0.3 * np.sin(2 * np.pi * 110 * t_drum)) * drum_decay
        drum_wave += np.random.normal(0, 0.08, len(t_drum)) * np.exp(-t_drum * 12.0)
        sf.write(str(self.sfx_dir / "drums.wav"), drum_wave / (np.max(np.abs(drum_wave)) + 1e-6), sr)

        # 2. Swords / Shield Clash (Inharmonic metallic frequencies)
        t_clash = np.linspace(0, 1.2, int(sr * 1.2), False)
        clash_decay = np.exp(-t_clash * 9.0)
        clash_wave = (np.sin(2 * np.pi * 1350 * t_clash) + np.sin(2 * np.pi * 2150 * t_clash) + np.sin(2 * np.pi * 3100 * t_clash)) * clash_decay
        clash_wave += np.random.normal(0, 0.25, len(t_clash)) * np.exp(-t_clash * 18.0)
        sf.write(str(self.sfx_dir / "clash.wav"), clash_wave / (np.max(np.abs(clash_wave)) + 1e-6), sr)

        # 3. Marching Boots (Low frequency rhythmic thud)
        t_march = np.linspace(0, 0.8, int(sr * 0.8), False)
        march_decay = np.exp(-t_march * 12.0)
        march_wave = (np.sin(2 * np.pi * 75 * t_march) + np.random.normal(0, 0.05, len(t_march))) * march_decay
        sf.write(str(self.sfx_dir / "marching.wav"), march_wave / (np.max(np.abs(march_wave)) + 1e-6), sr)

        # 4. Wind / Tactical Ambiance
        t_wind = np.linspace(0, 4.0, int(sr * 4.0), False)
        wind_noise = np.random.normal(0, 0.1, len(t_wind))
        wind_wave = np.convolve(wind_noise, np.ones(80)/80, mode='same')
        sf.write(str(self.sfx_dir / "wind.wav"), wind_wave / (np.max(np.abs(wind_wave)) + 1e-6), sr)

    def mix_soundtrack(self, voiceover_path: Path, scenes: List[Dict[str, Any]], output_path: Path) -> Path:
        """Composes voiceover, subtle background ambience, and synchronized battle sound cues."""
        voice = AudioSegment.from_file(str(voiceover_path))
        total_len = len(voice)
        master = voice

        # Ambient Tactical Wind Bed (-24 dB)
        wind = AudioSegment.from_file(str(self.sfx_dir / "wind.wav")) - 24
        ambience = AudioSegment.silent(duration=total_len)
        for offset in range(0, total_len, len(wind)):
            ambience = ambience.overlay(wind, position=offset)
        master = master.overlay(ambience)

        # Tactical Event Cues
        curr_time_ms = 0
        for sc in scenes:
            cue = sc.get("sfx_cue", "").lower()
            duration_ms = int(sc.get("duration", 5.0) * 1000)

            chosen = None
            if "clash" in cue or "fight" in cue:
                chosen = self.sfx_dir / "clash.wav"
            elif "drum" in cue or "charge" in cue:
                chosen = self.sfx_dir / "drums.wav"
            elif "march" in cue:
                chosen = self.sfx_dir / "marching.wav"

            if chosen and chosen.exists():
                sfx_audio = AudioSegment.from_file(str(chosen)) - 10
                master = master.overlay(sfx_audio, position=curr_time_ms + 250)

            curr_time_ms += duration_ms

        master.export(str(output_path), format="wav")
        return output_path
