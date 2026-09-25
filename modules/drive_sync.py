"""
modules/drive_sync.py
Ultra-Verbose Diagnostic Rclone Sync Manager.
Prints full live debug output directly to GitHub Actions console.
"""

import os
import re
import sys
import base64
import subprocess
import logging
import configparser
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DriveSync")

def run_command_live(cmd: list) -> Tuple[int, str]:
    """Runs a command and streams its output in real-time to the console."""
    print(f"\n=======================================================", flush=True)
    print(f"▶ EXEC: {' '.join(cmd)}", flush=True)
    print(f"=======================================================", flush=True)
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    output_lines = []
    for line in iter(process.stdout.readline, ''):
        print(line, end='', flush=True)
        output_lines.append(line)
    process.stdout.close()
    returncode = process.wait()
    return returncode, ''.join(output_lines)

def extract_id_and_type(raw_input: str) -> Tuple[str, str]:
    """Extracts raw ID and detects whether user passed a folder or file link."""
    cleaned = raw_input.strip()
    # Check folder URL
    m_folder = re.search(r"folders/([a-zA-Z0-9_-]+)", cleaned)
    if m_folder:
        return m_folder.group(1), "folder"
    # Check document or file URL
    m_doc = re.search(r"/d/([a-zA-Z0-9_-]+)", cleaned)
    if m_doc:
        return m_doc.group(1), "file"
    m_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", cleaned)
    if m_id:
        return m_id.group(1), "folder"
    return cleaned, "raw_id"

def extract_text_from_docx(file_path: Path) -> str:
    """Extracts plain text from docx."""
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
        self.raw_id, self.id_type = extract_id_and_type(folder_id)
        self.workspace_dir = workspace_dir
        self.input_dir = workspace_dir / "input"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.conf_path = Path.home() / ".config" / "rclone" / "rclone.conf"
        
        self._init_config(rclone_config_base64)
        self.remote_name = self._inspect_and_detect_remote()

    def _init_config(self, raw_config: str):
        self.conf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = base64.b64decode(raw_config).decode("utf-8")
        except Exception:
            content = raw_config

        with open(self.conf_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(self.conf_path, 0o600)

    def _inspect_and_detect_remote(self) -> str:
        """Inspects rclone.conf and prints diagnostic details to the log."""
        print("\n🔍 [ডায়াগনস্টিক] Rclone কনফিগারেশন যাচাই করা হচ্ছে...")
        cfg = configparser.ConfigParser()
        cfg.read(self.conf_path)
        sections = cfg.sections()
        print(f"-> rclone.conf-এ প্রাপ্ত রিমোটের সংখ্যা: {len(sections)} ({sections})", flush=True)

        chosen = "gdrive"
        for s in sections:
            r_type = cfg.get(s, "type", fallback="")
            scope = cfg.get(s, "scope", fallback="not_set")
            print(f"-> Remote: [{s}], Type: {r_type}, Scope: {scope}", flush=True)
            
            if scope == "drive.file":
                print("\n⚠️ [সতর্কবার্তা] আপনার rclone-এ 'scope = drive.file' সেট করা আছে!", flush=True)
                print("⚠️ এর ফলে Rclone শুধুমাত্র নিজের তৈরি ফাইল পড়তে পারে, গুগল ড্রাইভে ম্যানুয়ালি আপলোড করা ফাইল দেখতে পারে না!", flush=True)
                print("⚠️ সমাধান: কম্পিউটারে rclone config-এ scope হিসেবে '1' (drive - Full access) সিলেক্ট করুন।\n", flush=True)

            if r_type == "drive":
                chosen = s

        return chosen

    def pull(self) -> Tuple[Path, Optional[Path]]:
        print(f"\n🚀 [ডায়াগনস্টিক] ড্রাইভ থেকে ফাইল ডাউনলোড প্রক্রিয়া শুরু হচ্ছে...", flush=True)
        print(f"-> Target ID: {self.raw_id} (Detected Type: {self.id_type})", flush=True)
        print(f"-> Target Remote: [{self.remote_name}]", flush=True)

        # ১. রিমোট ড্রাইভ সংযোগ টেস্ট
        print("\n--- [ধাপ ১: ড্রাইভ কানেক্টিভিটি টেস্ট] ---", flush=True)
        run_command_live(["rclone", "about", f"{self.remote_name}:", "-v"])

        # ২. ফোল্ডারের ফাইল তালিকা পরীক্ষা (lsf)
        print("\n--- [ধাপ ২: ফোল্ডারের ফাইল তালিকা স্ক্যান] ---", flush=True)
        rc, file_list = run_command_live([
            "rclone", "lsf",
            f"{self.remote_name}:",
            "--drive-root-folder-id", self.raw_id,
            "-vv"
        ])

        # ৩. কপি কমান্ড চালানো
        print("\n--- [ধাপ ৩: ফাইল কপি করার চেষ্টা] ---", flush=True)
        cmd_copy = [
            "rclone", "copy",
            f"{self.remote_name}:",
            str(self.input_dir),
            "--drive-root-folder-id", self.raw_id,
            "--drive-export-formats", "txt,docx",
            "-vv"
        ]
        rc, copy_log = run_command_live(cmd_copy)

        # ৪. যদি সাধারণ কপিতে ফাইল না আসে, তবে --drive-shared-with-me দিয়ে চেষ্টা
        downloaded = list(self.input_dir.iterdir())
        if not downloaded:
            print("\n--- [ধাপ ৪: সাধারণ কপিতে ফাইল মেলেনি, Shared-with-me দিয়ে চেষ্টা করা হচ্ছে...] ---", flush=True)
            cmd_shared = [
                "rclone", "copy",
                f"{self.remote_name}:",
                str(self.input_dir),
                "--drive-root-folder-id", self.raw_id,
                "--drive-shared-with-me",
                "--drive-export-formats", "txt,docx",
                "-vv"
            ]
            run_command_live(cmd_shared)
            downloaded = list(self.input_dir.iterdir())

        print(f"\n=======================================================", flush=True)
        print(f"📥 ডাউনলোড সম্পন্ন! লোকাল ফোল্ডারে প্রাপ্ত ফাইল: {[f.name for f in downloaded]}", flush=True)
        print(f"=======================================================\n", flush=True)

        if not downloaded:
            raise FileNotFoundError(
                f"\n❌ [ERROR] ড্রাইভ থেকে কোনো ফাইল নামানো সম্ভব হয়নি!\n"
                f"সম্ভাব্য কারণসমূহ:\n"
                f"১. আপনি যে গুগল একাউন্ট দিয়ে rclone config করেছেন, সেটিতে এই ফোল্ডারের 'Editor' এক্সেস নেই।\n"
                f"২. ফোল্ডার আইডি ভুল অথবা 'Script.txt' ফাইলের লিংক দেওয়া হয়েছে (ফোল্ডারের নয়)।\n"
                f"৩. rclone.conf-এ Scope হিসেবে 'drive.file' দেওয়া আছে (যাতে ফুল এক্সেস থাকে না)।\n"
                f"উপরের লাইভ লগ বিস্তারিত দেখুন।"
            )

        # স্ক্রিপ্ট ফাইল শনাক্তকরণ
        target_script = self.workspace_dir / "Script.txt"
        found = False

        for f in downloaded:
            fname = f.name.lower()
            if "script" in fname and fname.endswith((".txt", ".docx")):
                if fname.endswith(".docx"):
                    print(f"-> Google Doc (.docx) পাওয়া গেছে: {f.name}, টেক্সট এক্সট্রাক্ট করা হচ্ছে...", flush=True)
                    text_data = extract_text_from_docx(f)
                    with open(target_script, "w", encoding="utf-8") as out:
                        out.write(text_data)
                else:
                    target_script = f
                found = True
                break

        if not found:
            # Fallback: যে কোনো টেক্সট বা docx ফাইল
            for f in downloaded:
                if f.suffix.lower() in [".txt", ".docx"]:
                    if f.suffix.lower() == ".docx":
                        text_data = extract_text_from_docx(f)
                        with open(target_script, "w", encoding="utf-8") as out:
                            out.write(text_data)
                    else:
                        target_script = f
                    found = True
                    break

        if not found or not target_script.exists():
            raise FileNotFoundError("ডাউনলোড করা ফাইলগুলোর মধ্যে কোনো টেক্সট বা স্ক্রিপ্ট ফাইল পাওয়া যায়নি।")

        # স্ক্রিপ্টের প্রথম কিছু অংশ লগে প্রিন্ট করা
        with open(target_script, "r", encoding="utf-8") as sc:
            preview = sc.read()[:200]
            print(f"✅ স্ক্রিপ্ট সফলভাবে প্রস্তুত! প্রিভিউ:\n\"{preview}...\"\n", flush=True)

        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
        audio_file = next((f for f in downloaded if f.suffix.lower() in audio_exts), None)
        if audio_file:
            print(f"🎵 অডিও ট্র্যাক পাওয়া গেছে: {audio_file.name}", flush=True)
        else:
            print(f"ℹ️ কোনো অডিও ফাইল পাওয়া যায়নি। AI দিয়ে নতুন ভয়েসওভার তৈরি হবে।", flush=True)

        return target_script, audio_file

    def push(self, video_file: Path):
        print(f"\n📤 রেন্ডার করা ভিডিও ড্রাইভে আপলোড করা হচ্ছে: {video_file.name}...", flush=True)
        cmd = [
            "rclone", "copy",
            str(video_file),
            f"{self.remote_name}:",
            "--drive-root-folder-id", self.raw_id,
            "-v"
        ]
        rc, out = run_command_live(cmd)
        if rc != 0:
            raise RuntimeError(f"ভিডিও আপলোড ব্যর্থ হয়েছে।")
        print("\n🎉 অভিনন্দন! ভিডিও সফলভাবে গুগল ড্রাইভে আপলোড হয়েছে!", flush=True)
