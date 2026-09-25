"""
modules/drive_sync.py
Rclone wrapper for automated Google Drive synchronization.
Auto-extracts Folder ID, handles Google Docs (.docx / .txt), and syncs media.
"""

import os
import re
import base64
import subprocess
import logging
import configparser
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("DriveSync")

def extract_folder_id(raw_input: str) -> str:
    """Extracts raw folder ID if user pasted full URL."""
    cleaned = raw_input.strip()
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", cleaned)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", cleaned)
    if match:
        return match.group(1)
    return cleaned

def extract_text_from_docx(file_path: Path) -> str:
    """Extracts plain text from a docx file without external dependencies."""
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        paragraphs = []
        for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            texts = [node.text for node in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs)


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
            logger.warning(f"Could not parse rclone.conf: {e}")
        return "gdrive"

    def pull(self) -> Tuple[Path, Optional[Path]]:
        """Pulls files from the specific Google Drive folder."""
        logger.info(f"Pulling files for Folder ID: {self.folder_id} using remote [{self.remote_name}]...")
        
        # We tell rclone to export Google Docs as txt or docx
        cmd = [
            "rclone", "copy",
            f"{self.remote_name}:",
            str(self.input_dir),
            "--drive-root-folder-id", self.folder_id,
            "--drive-export-formats", "txt,docx",
            "-v"
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"Rclone stderr: {res.stderr}")
            raise RuntimeError(f"Rclone sync error: {res.stderr}")

        downloaded_files = list(self.input_dir.iterdir())
        logger.info(f"ফোল্ডারে নামানো ফাইলগুলো: {[f.name for f in downloaded_files]}")

        target_script = self.workspace_dir / "Script.txt"
        found_script = False

        # 1. Look for plain txt or docx exported from Google Docs
        for f in downloaded_files:
            fname = f.name.lower()
            if "script" in fname and fname.endswith((".txt", ".docx")):
                if fname.endswith(".docx"):
                    logger.info(f"Google Doc (.docx) সনাক্ত হয়েছে: {f.name}, টেক্সট রূপান্তর করা হচ্ছে...")
                    text_content = extract_text_from_docx(f)
                    with open(target_script, "w", encoding="utf-8") as out:
                        out.write(text_content)
                else:
                    target_script = f
                found_script = True
                break

        # 2. Fallback: If named differently, take any text or docx file
        if not found_script:
            for f in downloaded_files:
                if f.suffix.lower() in [".txt", ".docx"]:
                    if f.suffix.lower() == ".docx":
                        text_content = extract_text_from_docx(f)
                        with open(target_script, "w", encoding="utf-8") as out:
                            out.write(text_content)
                    else:
                        target_script = f
                    found_script = True
                    break

        if not found_script or not target_script.exists():
            raise FileNotFoundError(f"গুগল ড্রাইভ ফোল্ডারে কোনো স্ক্রিপ্ট পাওয়া যায়নি। ফাইল লিস্ট: {[f.name for f in downloaded_files]}")

        # Audio file detection
        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        audio_file = next((f for f in downloaded_files if f.suffix.lower() in audio_exts), None)
        
        logger.info(f"ব্যবহারযোগ্য স্ক্রিপ্ট ফাইল: {target_script.name}")
        return target_script, audio_file

    def push(self, video_file: Path):
        """Uploads the rendered video back to Google Drive."""
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
            raise RuntimeError(f"Upload failed: {res.stderr}")
        logger.info("ভিডিও সফলভাবে গুগল ড্রাইভে আপলোড হয়েছে!")
