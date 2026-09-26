"""
modules/ollama_client.py
Ollama Cloud API client with resilient round-robin multi-key rotation.
Optimized for long-form battle documentaries (20+ minutes) and strict aniconism.
"""

import json
import logging
import requests
import re
import os
from typing import List, Dict, Any

logger = logging.getLogger("OllamaClient")

class OllamaCloudRotator:
    def __init__(self, api_keys_raw: str, model: str = None):
        self.api_keys: List[str] = [k.strip() for k in api_keys_raw.splitlines() if k.strip()]
        if not self.api_keys:
            raise ValueError("কোনো Ollama Cloud API Key পাওয়া যায়নি।")
        self.current_index = 0
        # Default to llama3.3:70b or configurable via env
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.3:70b")
        
        # Official Ollama Cloud Endpoints
        self.endpoints = [
            "https://ollama.com/api/chat",            # Native Ollama Cloud
            "https://ollama.com/v1/chat/completions"  # OpenAI Compatibility Mode
        ]

    def _get_active_key(self) -> str:
        return self.api_keys[self.current_index]

    def _rotate(self) -> None:
        old_idx = self.current_index
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        logger.warning(f"Ollama API Key পরিবর্তন করা হচ্ছে: {old_idx} -> {self.current_index}")

    def generate_battle_plan(self, script_text: str, total_duration: float) -> List[Dict[str, Any]]:
        """
        Ollama Cloud-এর মাধ্যমে সম্পূর্ণ ভিডিওর ট্যাকটিক্যাল ম্যাপ প্ল্যান তৈরি করে।
        """
        # ২২ মিনিটের ভিডিওর জন্য ১৫-২০টি মূল ঐতিহাসিক পর্যায়
        num_scenes = max(10, min(25, int(total_duration // 60)))
        avg_scene_duration = round(total_duration / num_scenes, 2)

        system_prompt = (
            "You are a master tactical cartographer for grand historical battle documentary animations.\n"
            "CRITICAL CONSTRAINTS (STRICT ANICONISM):\n"
            "1. NEVER depict, draw, or render living creatures (NO humans, NO faces, NO soldiers, NO animals).\n"
            "2. Armies are represented ONLY by geometric formations of dots: 'white' (Faction 1) or 'black' (Faction 2).\n"
            "3. Commanders are represented ONLY by a glowing 'star'.\n"
            f"4. The entire video lasts {total_duration:.2f} seconds. Divide it into exactly {num_scenes} strategic scenes.\n"
            f"5. Each scene must have a duration of approximately {avg_scene_duration} seconds so the sum equals {total_duration:.2f}s.\n"
            "Return ONLY valid JSON matching this schema:\n"
            "[\n"
            "  {\n"
            "    \"scene_id\": 1,\n"
            f"    \"duration\": {avg_scene_duration},\n"
            "    \"phase_title\": \"Deployment of Armies\",\n"
            "    \"sfx_cue\": \"drums\",\n"
            "    \"camera_focus\": {\"pos\": [0, 0, 0], \"zoom\": 1.0},\n"
            "    \"formations\": [\n"
            "      {\"id\": \"W1\", \"faction\": \"white\", \"shape\": \"line\", \"count\": 20, \"pos\": [-3, 0, 0], \"has_commander\": true},\n"
            "      {\"id\": \"B1\", \"faction\": \"black\", \"shape\": \"line\", \"count\": 20, \"pos\": [3, 0, 0], \"has_commander\": false}\n"
            "    ],\n"
            "    \"actions\": [\n"
            "      {\"type\": \"move\", \"formation_id\": \"W1\", \"target\": [-1, 0, 0]},\n"
            "      {\"type\": \"clash\"}\n"
            "    ]\n"
            "  }\n"
            "]"
        )

        # স্ক্রিপ্টের মূল অংশ এআই-কে সংক্ষেপিত আকারে পাঠানো (যাতে প্রম্পট সাইজ অতিরিক্ত বড় না হয়)
        script_summary = script_text[:8000] if len(script_text) > 8000 else script_text
        user_prompt = (
            f"Battle Script Overview:\n\"\"\"{script_summary}\"\"\"\n\n"
            f"Total Narration Duration: {total_duration:.2f} seconds.\n"
            f"Generate a strategic battle progression with {num_scenes} sequential scenes covering the entire duration."
        )

        attempts = 0
        max_attempts = len(self.api_keys) * len(self.endpoints) * 2

        while attempts < max_attempts:
            active_key = self._get_active_key()
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json"
            }

            for endpoint in self.endpoints:
                logger.info(f"Ollama Cloud কল করা হচ্ছে: {endpoint} (Key Index: {self.current_index}, Model: {self.model})...")

                if "/api/chat" in endpoint:
                    # Native Ollama API
                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "stream": False,
                        "format": "json"
                    }
                else:
                    # OpenAI Compatible API
                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }

                try:
                    response = requests.post(endpoint, headers=headers, json=payload, timeout=180)

                    if response.status_code == 200:
                        res_json = response.json()
                        if "message" in res_json and "content" in res_json["message"]:
                            content = res_json["message"]["content"]
                        elif "choices" in res_json:
                            content = res_json["choices"][0]["message"]["content"]
                        else:
                            content = str(res_json)
                        
                        logger.info("✅ Ollama Cloud থেকে সফলভাবে ট্যাকটিক্যাল প্ল্যান তৈরি হয়েছে!")
                        return self._parse_json_response(content, total_duration)

                    elif response.status_code in [401, 403, 429]:
                        logger.warning(f"Key {self.current_index} লিমিট শেষ বা অথেন্টিকেশন এরর ({response.status_code})। পরবর্তী কি-তে যাওয়া হচ্ছে।")
                        self._rotate()
                        break
                    else:
                        logger.warning(f"Endpoint {endpoint} রেসপন্স কোড {response.status_code}: {response.text[:150]}")

                except requests.RequestException as e:
                    logger.warning(f"Network error on {endpoint}: {e}")

            attempts += 1

        raise RuntimeError("সবগুলো Ollama Cloud API Key এবং এন্ডপয়েন্ট ব্যর্থ হয়েছে। দয়া করে আপনার OLLAMA_API_KEYS যাচাই করুন।")

    def _parse_json_response(self, raw_str: str, total_duration: float) -> List[Dict[str, Any]]:
        cleaned = re.sub(r"^```(?:json)?", "", raw_str.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned)

        if isinstance(data, dict):
            for k in ["scenes", "battle_plan", "timeline", "phases"]:
                if k in data and isinstance(data[k], list):
                    data = data[k]
                    break
            else:
                data = [data]

        # সময়কাল যাতে হুবহু অডিওর সাথে মিলে যায় তা নিশ্চিত করা
        total_assigned = sum(float(s.get("duration", 10.0)) for s in data)
        if total_assigned > 0:
            scale = total_duration / total_assigned
            for s in data:
                s["duration"] = round(float(s.get("duration", 10.0)) * scale, 2)

        return data
