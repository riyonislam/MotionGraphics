"""
modules/ollama_client.py
Official Ollama Cloud API Client.
Prioritizes gemma4:31b, falls back to token-efficient models,
and reserves heavy models as quality-preserving backstops.
"""

import json
import logging
import requests
import re
import os
from typing import List, Dict, Any

logger = logging.getLogger("OllamaClient")

# স্মার্ট ক্রমানুসারে সাজানো Ollama Cloud মডেল তালিকা (টোকেন সাশ্রয়ী ও হাই-কোয়ালিটি)
ORDERED_CLOUD_MODELS = [
    "gemma4:31b",           # ১. সর্বপ্রথম চেষ্টা হবে (User's #1 Priority: Fast, Smart, Low Token)
    "deepseek-v4.1-flash",  # ২. সেকেন্ড চয়েস (সুপার ফাস্ট ফ্লাশ আর্কিটেকচার, কম টোকেন)
    "glm-5.3-flash",        # ৩. ১৮বি লাইটওয়েট ফ্রন্টিয়ার মডেল (মিনিমাল টোকেন খরচ)
    "gpt-oss:20b",          # ৪. ২০বি কমপ্যাক্ট রিজনিং মডেল
    "gemma4:cloud",         # ৫. ক্লাউড অ্যালিয়াস ট্যাগ
    "gpt-oss:120b",         # ৬. হেভি মডেল (টোকেন বেশি খাবে কিন্তু কোয়ালিটি সেরা)
    "deepseek-v4-pro",      # ৭. ফ্ল্যাগশিপ প্রো রিজনিং মডেল
    "glm-5.3"               # ৮. লার্জ ক্যাপাসিটি মডেল
]

class OllamaCloudRotator:
    def __init__(self, api_keys_raw: str, model: str = None):
        self.api_keys: List[str] = [k.strip() for k in api_keys_raw.splitlines() if k.strip()]
        if not self.api_keys:
            raise ValueError("কোনো Ollama Cloud API Key পাওয়া যায়নি।")
        self.current_key_idx = 0
        self.preferred_model = model or os.getenv("OLLAMA_MODEL")
        self.base_url = "https://ollama.com"
        
        # Endpoints
        self.endpoint_native = f"{self.base_url}/api/chat"
        self.endpoint_openai = f"{self.base_url}/v1/chat/completions"

    def _get_active_key(self) -> str:
        return self.api_keys[self.current_key_idx]

    def _rotate_key(self) -> None:
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        logger.warning(f"🔄 রেট লিমিট বা কি এরর! API Key পরিবর্তন: {old_idx} -> {self.current_key_idx}")

    def get_candidate_models(self) -> List[str]:
        """User preferred model first, then the token-optimized ordered list."""
        candidates = []
        if self.preferred_model:
            candidates.append(self.preferred_model)
        for m in ORDERED_CLOUD_MODELS:
            if m not in candidates:
                candidates.append(m)
        return candidates

    def generate_battle_plan(self, script_text: str, total_duration: float) -> List[Dict[str, Any]]:
        # ২২ মিনিটের ভিডিওর জন্য ১৫-২০টি মূল ঐতিহাসিক পর্যায়
        num_scenes = max(10, min(25, int(total_duration // 60)))
        avg_scene_duration = round(total_duration / num_scenes, 2)

        system_prompt = (
            "You are a master military cartographer for historical documentary animations (Circle/Star particle map style).\n"
            "STRICT CONSTRAINTS (ANICONISM):\n"
            "1. NEVER render living creatures (NO humans, NO faces, NO animals).\n"
            "2. Armies are represented ONLY by formations of dots: 'white' (Faction 1) or 'black' (Faction 2).\n"
            "3. Commanders are represented ONLY by a glowing 'star'.\n"
            f"4. The video lasts {total_duration:.2f} seconds. Divide it into exactly {num_scenes} strategic scenes.\n"
            f"5. Each scene duration must be approximately {avg_scene_duration} seconds.\n"
            "Return ONLY valid JSON matching this schema:\n"
            "[\n"
            "  {\n"
            "    \"scene_id\": 1,\n"
            f"    \"duration\": {avg_scene_duration},\n"
            "    \"phase_title\": \"Deployment & Terrain Analysis\",\n"
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

        script_summary = script_text[:8000] if len(script_text) > 8000 else script_text
        user_prompt = (
            f"Battle Script Narrative:\n\"\"\"{script_summary}\"\"\"\n\n"
            f"Total Duration: {total_duration:.2f} seconds.\n"
            f"Output the tactical progression covering all {num_scenes} phases in valid JSON."
        )

        models_to_try = self.get_candidate_models()
        logger.info(f"📋 ট্রাই করার জন্য মডেল সিকোয়েন্স: {models_to_try}")

        for model_name in models_to_try:
            logger.info(f"\n=======================================================")
            logger.info(f"🤖 মডেল দিয়ে চেষ্টা করা হচ্ছে: [{model_name}]")
            logger.info(f"=======================================================")

            # এই মডেলের জন্য উপলব্ধ সবগুলো কি দিয়ে চেষ্টা করা হবে
            keys_attempted = 0
            while keys_attempted < len(self.api_keys):
                active_key = self._get_active_key()
                headers = {
                    "Authorization": f"Bearer {active_key}",
                    "Content-Type": "application/json"
                }

                # ১. প্রথমে অফিসিয়াল Native Ollama Cloud API ট্রাই
                native_payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "format": "json"
                }

                try:
                    logger.info(f"কল করা হচ্ছে: {self.endpoint_native} | Model: {model_name} | Key Index: {self.current_key_idx}")
                    resp = requests.post(self.endpoint_native, headers=headers, json=native_payload, timeout=180)

                    if resp.status_code == 200:
                        content = resp.json()["message"]["content"]
                        logger.info(f"🎉 সাফল্য! মডেল [{model_name}] সফলভাবে ট্যাকটিক্যাল প্ল্যান তৈরি করেছে!")
                        return self._parse_json_response(content, total_duration)

                    elif resp.status_code == 404:
                        logger.warning(f"⚠️ মডেল [{model_name}] পাওয়া যায়নি (404 Not Found)। সরাসরি পরবর্তী মডেলে যাচ্ছি...")
                        break  # ব্রেক করে সরাসরি পরবর্তী মডেলে চলে যাবে

                    elif resp.status_code in [401, 403, 429]:
                        logger.warning(f"⚠️ Key {self.current_key_idx} রেট লিমিট বা অথ এরর ({resp.status_code})। কি রোটেট হচ্ছে...")
                        self._rotate_key()
                        keys_attempted += 1
                        continue

                    else:
                        logger.warning(f"অপ্রত্যাশিত কোড {resp.status_code}: {resp.text[:150]}")

                except requests.RequestException as e:
                    logger.warning(f"কানেকশন এরর on {model_name}: {e}")

                # ২. যদি Native ফেল করে, তবে OpenAI Compatibility মোড ট্রাই
                openai_payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }

                try:
                    resp_openai = requests.post(self.endpoint_openai, headers=headers, json=openai_payload, timeout=180)
                    if resp_openai.status_code == 200:
                        content = resp_openai.json()["choices"][0]["message"]["content"]
                        logger.info(f"🎉 সাফল্য (OpenAI Mode)! মডেল [{model_name}] দিয়ে প্ল্যান তৈরি সম্পন্ন হয়েছে।")
                        return self._parse_json_response(content, total_duration)
                    elif resp_openai.status_code == 404:
                        break
                    elif resp_openai.status_code in [401, 403, 429]:
                        self._rotate_key()
                        keys_attempted += 1
                        continue
                except requests.RequestException:
                    pass

                keys_attempted += 1

        raise RuntimeError("সবগুলো Ollama Cloud মডেল ও API Key চেষ্টা করা হয়েছে কিন্তু প্ল্যান তৈরি করা যায়নি।")

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

        total_assigned = sum(float(s.get("duration", 10.0)) for s in data)
        if total_assigned > 0:
            scale = total_duration / total_assigned
            for s in data:
                s["duration"] = round(float(s.get("duration", 10.0)) * scale, 2)

        return data
