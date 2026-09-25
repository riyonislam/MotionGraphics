"""
pipeline.py
End-to-End Orchestrator for Historical Battle Video Generation.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

from modules.drive_sync import DriveSyncManager
from modules.tts_engine import TTSManager
from modules.ollama_client import OllamaCloudRotator
from modules.sfx_manager import SFXManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Pipeline")

def get_audio_duration(path: Path) -> float:
    if path.suffix.lower() == ".mp3":
        return MP3(str(path)).info.length
    elif path.suffix.lower() == ".wav":
        return WAVE(str(path)).info.length
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]).decode().strip()
    return float(out)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", required=True)
    args = parser.parse_args()

    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)

    rclone_cfg = os.getenv("RCLONE_CONFIG_BASE64")
    ollama_keys = os.getenv("OLLAMA_API_KEYS")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not rclone_cfg or not ollama_keys:
        logger.error("Missing mandatory secrets (RCLONE_CONFIG_BASE64 or OLLAMA_API_KEYS).")
        sys.exit(1)

    # 1. Drive Sync
    drive = DriveSyncManager(rclone_cfg, args.folder_id, workspace)
    script_path, existing_audio = drive.pull()

    # 2. Audio Processing (Kokoro / Gemini)
    tts = TTSManager(gemini_key)
    voiceover_path = tts.process(script_path, existing_audio, workspace)
    audio_duration = get_audio_duration(voiceover_path)
    logger.info(f"Total narration duration: {audio_duration:.2f}s")

    # 3. Ollama Cloud Tactical Planning
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()

    rotator = OllamaCloudRotator(api_keys_raw=ollama_keys)
    plan = rotator.generate_battle_plan(script_text, audio_duration)

    plan_file = workspace / "battle_plan.json"
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    # 4. Contextual Procedural SFX Layering
    sfx = SFXManager(workspace)
    soundtrack = workspace / "master_soundtrack.wav"
    sfx.mix_soundtrack(voiceover_path, plan, soundtrack)

    # 5. 100% Code-Driven Manim Render
    logger.info("Executing 60 FPS Manim vector rendering...")
    manim_cmd = [
        "manim", "render",
        "-qh",
        "--format=mp4",
        "--media_dir", str(workspace / "manim_media"),
        "modules/battle_renderer.py",
        "TacticalBattleScene"
    ]
    res = subprocess.run(manim_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"Manim rendering failed:\n{res.stderr}")
        raise RuntimeError("Manim render failed.")

    raw_video = workspace / "manim_media" / "videos" / "battle_renderer" / "1080p60" / "TacticalBattleScene.mp4"
    final_output = workspace / "final_battle_video.mp4"

    # 6. Mux Audio & Video with FFmpeg
    logger.info("Muxing final video stream...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-i", str(soundtrack),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(final_output)
    ], check=True)

    # 7. Upload to Google Drive
    drive.push(final_output)
    logger.info("Pipeline completed successfully!")

if __name__ == "__main__":
    main()
