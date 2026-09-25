"""
modules/drive_sync.py
Rclone wrapper for automated Google Drive synchronization.
"""

import os
import base64
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("DriveSync")

class DriveSyncManager:
    def __init__(self, rclone_config_base64: str, folder_id: str, workspace_dir: Path):
        self.folder_id = folder_id.strip()
        self.input_dir = workspace_dir / "input"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.conf_path = Path.home() / ".config" / "rclone" / "rclone.conf"
        self._init_config(rclone_config_base64)

    def _init_config(self, raw_config: str):
        self.conf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = base64.b64decode(raw_config).decode("utf-8")
        except Exception:
            content = raw_config

        with open(self.conf_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(self.conf_path, 0o600)

    def pull(self) -> Tuple[Path, Optional[Path]]:
        remote = f"gdrive:{self.folder_id}"
        logger.info(f"Syncing input files from {remote}...")
        res = subprocess.run(["rclone", "copy", remote, str(self.input_dir), "--drive-root-folder-id", self.folder_id], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Rclone sync error: {res.stderr}")

        script_file = None
        for f in self.input_dir.iterdir():
            if f.name.lower() == "script.txt":
                script_file = f
                break

        if not script_file:
            raise FileNotFoundError("Target Drive folder must contain 'Script.txt'.")

        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        audio_file = next((f for f in self.input_dir.iterdir() if f.suffix.lower() in audio_exts), None)
        return script_file, audio_file

    def push(self, video_file: Path):
        remote = f"gdrive:{self.folder_id}"
        logger.info(f"Uploading {video_file.name} to {remote}...")
        res = subprocess.run(["rclone", "copy", str(video_file), remote, "--drive-root-folder-id", self.folder_id], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Upload failed: {res.stderr}")
        logger.info("Upload completed successfully.")
