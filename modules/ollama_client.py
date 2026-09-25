"""
modules/ollama_client.py
Ollama Cloud API client with resilient round-robin multi-key rotation.
Guarantees 100% code-driven tactical motion output without living creatures.
"""

import json
import logging
import requests
import re
from typing import List, Dict, Any

logger = logging.getLogger("OllamaClient")

class OllamaCloudRotator:
    def __init__(self, api_keys_raw: str, model: str = "llama3.3:70b", endpoint: str = "https://api.ollama.com/v1"):
        self.api_keys: List[str] = [k.strip() for k in api_keys_raw.splitlines() if k.strip()]
        if not self.api_keys:
            raise ValueError("No Ollama Cloud API keys supplied.")
        self.current_index = 0
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    def _get_active_key(self) -> str:
        return self.api_keys[self.current_index]

    def _rotate(self) -> None:
        old_idx = self.current_index
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        logger.warning(f"Rate limit / API error encountered. Switching key: {old_idx} -> {self.current_index}")

    def generate_battle_plan(self, script_text: str, total_duration: float) -> List[Dict[str, Any]]:
        """
        Queries Ollama Cloud to generate mathematical coordinate steps for the Manim scene.
        """
        system_prompt = (
            "You are an expert military cartographer for documentary animations like 'Kings and Generals'.\n"
            "CRITICAL RULES:\n"
            "1. STRICT ANICONISM: Absolutely NO living creatures, NO humans, NO animals, and NO faces.\n"
            "2. 100% CODE-DRIVEN: Only output tactical vector layout coordinates and actions.\n"
            "3. Units must be classified as: 'infantry', 'cavalry', 'archers', or 'command'.\n"
            "4. Positions are 2D coordinates [x, y, 0] with x in [-7, 7] and y in [-3.5, 3.5].\n"
            "5. The total durations of all scenes MUST strictly add up to the requested voiceover duration.\n"
            "Output ONLY a raw, valid JSON array matching this format:\n"
            "[\n"
            "  {\n"
            "    \"scene_id\": 1,\n"
            "    \"duration\": 8.5,\n"
            "    \"phase_title\": \"Initial Roman Deployment\",\n"
            "    \"sfx_cue\": \"drums\",\n"
            "    \"camera_focus\": {\"pos\": [0, 0, 0], \"zoom\": 1.0},\n"
            "    \"blue_units\": [{\"id\": \"B1\", \"label\": \"Roman Left Wing\", \"type\": \"cavalry\", \"pos\": [-4, 2, 0], \"count\": \"2,000\"}],\n"
            "    \"red_units\": [{\"id\": \"R1\", \"label\": \"Numidian Horse\", \"type\": \"cavalry\", \"pos\": [4, 2, 0], \"count\": \"3,500\"}],\n"
            "    \"actions\": [\n"
            "      {\"type\": \"flank_arrow\", \"start\": [4, 2, 0], \"end\": [-1, 3, 0], \"color\": \"#EF4444\"},\n"
            "      {\"type\": \"advance\", \"unit_id\": \"B1\", \"target_pos\": [-2, 2, 0]},\n"
            "      {\"type\": \"clash\", \"center\": [-1, 2.5, 0]}\n"
            "    ]\n"
            "  }\n"
            "]"
        )

        user_prompt = (
            f"Battle Script Narrative:\n\"\"\"{script_text}\"\"\"\n\n"
            f"Total Audio Duration: {total_duration:.2f} seconds.\n"
            "Generate the tactical maneuver sequence covering this entire duration."
        )

        attempts = 0
        max_attempts = len(self.api_keys) * 3

        while attempts < max_attempts:
            active_key = self._get_active_key()
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.15
            }

            try:
                response = requests.post(f"{self.endpoint}/chat/completions", headers=headers, json=payload, timeout=120)

                if response.status_code == 200:
                    raw_content = response.json()["choices"][0]["message"]["content"]
                    return self._parse_json_response(raw_content)
                elif response.status_code in [401, 403, 429, 500, 502, 503]:
                    logger.warning(f"Key returned HTTP {response.status_code}. Rotating.")
                    self._rotate()
                else:
                    logger.error(f"Unexpected response: {response.text}")
                    self._rotate()

            except requests.RequestException as e:
                logger.error(f"Request exception: {e}")
                self._rotate()

            attempts += 1

        raise RuntimeError("Failed to obtain tactical battle plan after rotating all available Ollama Cloud keys.")

    def _parse_json_response(self, raw_str: str) -> List[Dict[str, Any]]:
        cleaned = re.sub(r"^```(?:json)?", "", raw_str.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        if isinstance(data, dict):
            for key in ["scenes", "timeline", "battle_plan"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        return data
