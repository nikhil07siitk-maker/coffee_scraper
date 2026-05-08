"""Phase 3: Cognitive Extraction using Ollama."""

import asyncio
import logging
from typing import List, Dict, Any

from ..config.settings import Settings
from ..integrations.ollama_client import OllamaExtractor

logger = logging.getLogger("icfie.phase3")

class CognitiveEnricher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ollama = OllamaExtractor(
            model=settings.OLLAMA_MODEL,
            host=settings.OLLAMA_HOST
        )

    async def run(self, corpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract structured data from unstructured text."""
        logger.info(f"Starting Phase 3 for {len(corpus)} records")

        enriched_results = []

        # We need to limit concurrent LLM calls heavily
        semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_OLLAMA)

        async def process_record(record: Dict):
            async with semaphore:
                seed = record["seed"]
                enrichment = record["enrichment"]

                # Combine available text
                text_parts = []

                # Add title/snippet context if from search
                if seed.get("snippet"):
                    text_parts.append(f"Search Result Context:\n{seed['snippet']}")

                # Add markdown
                if enrichment.get("website_markdown"):
                    text_parts.append(f"Website Content:\n{enrichment['website_markdown']}")

                # Add social
                if enrichment.get("social_bio"):
                    text_parts.append(f"Social Media Bio:\n{enrichment['social_bio']}")

                full_text = "\n\n".join(text_parts)

                if full_text.strip():
                    llm_data = await self.ollama.extract_estate_profile(full_text)
                    if llm_data:
                        # Merge LLM data into enrichment
                        enrichment["estate_name"] = llm_data.get("estate_name")
                        enrichment["varietals_grown"] = llm_data.get("varietals_grown")
                        enrichment["processing_methods"] = llm_data.get("processing_methods")
                        enrichment["certifications"] = llm_data.get("certifications")
                        enrichment["farm_size_acres"] = llm_data.get("farm_size_acres")
                        enrichment["contact_person"] = llm_data.get("contact_person")
                        enrichment["export_mentions"] = llm_data.get("export_mentions", False)
                        enrichment["address_hint"] = llm_data.get("address_hint")

                        # Add confidence if available (usually requires parsing reasoning, setting static for now)
                        enrichment["llm_confidence_score"] = 0.85
                        enrichment["llm_confidence_reasoning"] = llm_data.get("confidence_reasoning", "")

                return record

        # Run tasks
        tasks = [process_record(r) for r in corpus]
        enriched_results = await asyncio.gather(*tasks)

        logger.info("Phase 3 complete")
        return enriched_results