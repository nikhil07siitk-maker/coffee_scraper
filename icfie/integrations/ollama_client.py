"""Local LLM inference wrapper using Ollama."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger("icfie.ollama")

class OllamaExtractor:
    """Ollama client for structured extraction."""

    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self.endpoint = f"{host}/api/generate"
        self._semaphore = asyncio.Semaphore(3)  # Max concurrent requests

        self.system_prompt = """
You are an expert Indian coffee agronomy data extractor.
Read the estate text and output ONLY a JSON object. No markdown, no explanation.

Rules:
- Estate names often end with "Estate", "Plantations", "Coffee Works".
- Indian coffee varietals: S795, CxR, Raro, Chandragiri, Kent, Selection 9, Arabica, Robusta.
- Certifications: Organic, Rainforest Alliance, UTZ, Fairtrade, Jaivik Bharat, Shade Grown.
- Processing: Washed, Natural, Honey, Monsooned, Pulped Natural.
- If field unknown, use null.

JSON Schema:
{
  "estate_name": string|null,
  "varietals_grown": [string]|null,
  "processing_methods": [string]|null,
  "certifications": [string]|null,
  "farm_size_acres": number|null,
  "contact_person": string|null,
  "export_mentions": boolean,
  "address_hint": string|null,
  "confidence_reasoning": string
}
"""

    async def extract_estate_profile(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Sends text to Ollama with strict system prompt.
        Returns parsed JSON or None if unparseable.
        """
        if not text or len(text.strip()) < 50:
            return None

        prompt = f"Text to analyze:\n\n{text[:8000]}" # Truncate to avoid context window limits

        async with self._semaphore:
            try:
                response_text = await self._call_ollama(prompt)
                if not response_text:
                    return None

                return self._parse_json(response_text, prompt)

            except Exception as e:
                logger.error(f"Ollama extraction error: {e}")
                return None

    async def _call_ollama(self, prompt: str) -> Optional[str]:
        payload = {
            "model": self.model,
            "system": self.system_prompt,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, json=payload, timeout=120) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("response", "")
        except asyncio.TimeoutError:
            logger.warning("Ollama timeout after 120s")
            return None
        except Exception as e:
            logger.error(f"Ollama connection error: {e}")
            return None

    def _parse_json(self, response_text: str, original_prompt: str) -> Optional[Dict]:
        """Attempt to parse JSON, handle markdown code blocks if present."""
        text = response_text.strip()

        # Strip markdown blocks if the model ignored the system prompt
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            data = json.loads(text)
            return data
        except json.JSONDecodeError:
            logger.warning("Ollama returned invalid JSON. Attempting recovery.")
            # Basic fallback for common single-quote issue
            try:
                import ast
                data = ast.literal_eval(text)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

            return None