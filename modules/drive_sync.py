"""
modules/drive_sync.py
Rclone wrapper for automated Google Drive synchronization.
Auto-extracts Folder ID from URLs and auto-detects remote section name.
"""

import os
import re
import base64
import subprocess
import logging
import configparser
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("DriveSync")

def extract_folder_id(raw_input: str) -> str:
    """
    Extracts raw folder ID if the user pasted a full Google Drive URL.
    Example: https://drive.google.com/drive/folders/1A2B3C4D5E?usp=sharing -> 1A2B3C4D5E
    """
    cleaned = raw_input.strip()
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", cleaned)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", cleaned)
    if match:
        return match.group(1)
    return cleaned


class DriveSyncManager:
    def __init__(self, rclone_config_base64: str, folder_id: str, workspace_dir: Path):
        self.folder_id = extract_folder_id(folder_id)
        self.workspace_dir = workspace_dir
        self.input_dir = workspace_dir / "input"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.conf_path = Path.home() / ".config" / "rclone" / "rclone.conf"
        
        self._init_config(rclone_config_base64)
        self.remote_name = self._detect_remote_name()

    def _init_config(self, raw_config: str):
        self.conf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = base64.b64decode(raw_config).decode("utf-8")
        except Exception:
            content = raw_config

        with open(self.conf_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(self.conf_path, 0o600)

    def _detect_remote_name(self) -> str:
        """Reads rclone.conf and dynamically finds the configured Google Drive remote."""
        try:
            cfg = configparser.ConfigParser()
            cfg.read(self.conf_path)
            for section in cfg.sections():
                if cfg.get(section, "type", fallback="") == "drive":
                    logger.info(f"Detected Google Drive remote: [{section}]")
                    return section
            if cfg.sections():
                return cfg.sections()[0]
        except Exception as e:
            logger.warning(f"Could not parse rclone.conf automatically: {e}")
        return "gdrive"

    def pull(self) -> Tuple[Path, Optional[Path]]:
        """Pulls files from the specific Google Drive folder."""
        logger.info(f"Pulling files for Folder ID: {self.folder_id} using remote [{self.remote_name}]...")
        
        # When --drive-root-folder-id is set, the root of remote is that folder itself.
        cmd = [
            "rclone", "copy",
            f"{self.remote_name}:",
            str(self.input_dir),
            "--drive-root-folder-id", self.folder_id,
            "-v"
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"Rclone stderr: {res.stderr}")
            raise RuntimeError(f"Rclone sync error: {res.stderr}")

        # Check for Script.txt
        script_file = None
        for f in self.input_dir.iterdir():
            if f.name.lower() == "script.txt":
                script_file = f
                break

        if not script_file:
            raise FileNotFoundError("Google Drive ফোল্ডারে 'Script.txt' ফাইলটি খুঁজে পাওয়া যায়নি।")

        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        audio_file = next((f for f in self.input_dir.iterdir() if f.suffix.lower() in audio_exts), None)
        return script_file, audio_file

    def push(self, video_file: Path):
        """Uploads the rendered video back to the exact same Google Drive folder."""
        logger.info(f"Uploading {video_file.name} to Google Drive folder [{self.folder_id}]...")
        
        cmd = [
            "rclone", "copy",
            str(video_file),
            f"{self.remote_name}:",
            "--drive-root-folder-id", self.folder_id,
            "-v"
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"Upload failed: {res.stderr}")
            raise RuntimeError(f"Upload failed: {res.stderr}")
            
        logger.info("ভিডিও সফলভাবে গুগল ড্রাইভে আপলোড হয়েছে!")
