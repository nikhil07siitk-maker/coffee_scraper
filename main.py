import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add icfie to path
sys.path.insert(0, str(Path(__file__).parent))

from icfie.config.settings import Settings
from icfie.pipeline.phase1_discovery import DiscoveryOrchestrator
from icfie.pipeline.phase2_deepweb import DeepWebEnricher
from icfie.pipeline.phase3_cognitive import CognitiveEnricher
from icfie.pipeline.phase4_verify import AuthorityVerifier
from icfie.pipeline.phase5_resolve import ResolutionEngine
from icfie.storage.local_db import init_db, get_session, CoffeeEstate
from icfie.storage.exporters import CSVExporter

from icfie.config.targets import validate_state_district

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("icfie.main")


async def main(district: str, state: str):
    # Normalize inputs (e.g., "Coorg" -> "Kodagu")
    try:
        state, district = validate_state_district(state, district)
    except ValueError as e:
        logger.warning(f"Validation warning: {e}")

    settings = Settings()
    settings.ensure_paths()
    init_db(settings.DATABASE_URL)

    logger.info(f"Starting ICFIE Pipeline for {district}, {state}")

    try:
        # PHASE 1
        p1 = DiscoveryOrchestrator(settings)
        raw_seeds = await p1.run(district, state)
        if not raw_seeds:
            logger.error("Phase 1: Zero seeds discovered. Abort.")
            return

        # PHASE 2
        p2 = DeepWebEnricher(settings)
        corpus = await p2.run(raw_seeds)

        # PHASE 3
        p3 = CognitiveEnricher(settings)
        enriched = await p3.run(corpus)

        # PHASE 4
        p4 = AuthorityVerifier(settings)
        verified = p4.run(enriched)

        # PHASE 5
        p5 = ResolutionEngine(settings)
        golden_records = await p5.run(verified)

        # PERSIST
        session = get_session()
        for rec in golden_records:
            # Upsert
            existing = session.query(CoffeeEstate).filter_by(estate_id=rec["estate_id"]).first()
            if existing:
                for key, value in rec.items():
                    setattr(existing, key, value)
            else:
                session.add(CoffeeEstate(**rec))
        session.commit()

        # EXPORT
        export_path = settings.output_path / f"{district.lower()}_farms.csv"
        CSVExporter.export(golden_records, str(export_path))

        active_count = len([r for r in golden_records if r['record_status'] == 'active'])
        logger.info(f"Pipeline complete. Active records: {active_count}")
        logger.info(f"Exported to {export_path}")

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indian Coffee Farm Intelligence Engine")
    parser.add_argument("--district", required=True, help="Target district (e.g., Chikmagalur)")
    parser.add_argument("--state", required=True, help="Target state (e.g., Karnataka)")

    args = parser.parse_args()
    asyncio.run(main(args.district, args.state))