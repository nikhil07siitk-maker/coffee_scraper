"""Phase 5: Resolution, Deduplication, Geolock."""

import logging
from typing import List, Dict, Any, Tuple
import math

from ..config.settings import Settings
from ..core.models import EstateRecord, RecordStatus, GeoAccuracy
from ..integrations.nominatim_client import NominatimClient
from ..services.geo_utils import haversine_distance

logger = logging.getLogger("icfie.phase5")

class ResolutionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.nominatim = NominatimClient()

    async def run(self, verified_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate and convert to Golden Records."""
        logger.info(f"Starting Phase 5 for {len(verified_records)} records")

        import json
        from pathlib import Path
        import asyncio

        # 1. Cluster by name
        clusters = self._cluster_by_name(verified_records)

        # 2. Merge clusters
        golden_records = []
        invalid_records = []

        for cluster in clusters:
            if not cluster:
                continue

            merged = self._merge_cluster(cluster)

            # 3. Reverse Geocode (Nominatim)
            if merged.get("latitude") and merged.get("longitude"):
                geo_info = await self.nominatim.reverse_geocode(merged["latitude"], merged["longitude"])
                if geo_info and geo_info.get("village_taluka"):
                    merged["village_taluka"] = geo_info["village_taluka"]

            # Validation
            if self._validate_mandatory_fields(merged):
                merged["record_status"] = RecordStatus.ACTIVE.value
                golden_records.append(merged)
            else:
                logger.warning(f"Record failed mandatory validation: {merged.get('estate_name')}")
                invalid_records.append({
                    "raw_data": merged,
                    "failure_reason": "Tier 1 fields missing",
                    "failure_phase": "Phase 5"
                })

        if invalid_records:
            quarantine_file = self.settings.quarantine_path / "invalid_records.json"
            try:
                # Append to existing
                existing = []
                if quarantine_file.exists():
                    with open(quarantine_file, "r") as f:
                        try:
                            existing = json.load(f)
                        except json.JSONDecodeError:
                            pass

                existing.extend(invalid_records)
                with open(quarantine_file, "w") as f:
                    json.dump(existing, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to write to quarantine file: {e}")

        logger.info(f"Phase 5 complete. Created {len(golden_records)} golden records. Invalid: {len(invalid_records)}")
        return golden_records

    def _cluster_by_name(self, records: List[Dict]) -> List[List[Dict]]:
        """Group records that represent the same estate."""
        try:
            from rapidfuzz import fuzz
            has_fuzz = True
        except ImportError:
            has_fuzz = False

        if not records:
            return []

        clusters = []
        unassigned = records.copy()

        while unassigned:
            current = unassigned.pop(0)
            cluster = [current]

            c_seed = current["seed"]
            c_enr = current["enrichment"]
            c_name = c_enr.get("estate_name") or c_seed.get("estate_name_raw", "")

            if not c_name:
                # Can't cluster without name, just add as single cluster
                clusters.append(cluster)
                continue

            # Find matches
            i = 0
            while i < len(unassigned):
                candidate = unassigned[i]
                cand_seed = candidate["seed"]
                cand_enr = candidate["enrichment"]
                cand_name = cand_enr.get("estate_name") or cand_seed.get("estate_name_raw", "")

                is_match = False

                # Check URL match first (strongest)
                c_url = c_seed.get("website") or c_seed.get("link")
                cand_url = cand_seed.get("website") or cand_seed.get("link")

                if c_url and cand_url and c_url == cand_url:
                    is_match = True

                # Check Name match
                elif cand_name and has_fuzz:
                    score = fuzz.token_set_ratio(c_name.lower(), cand_name.lower())
                    if score >= self.settings.FUZZY_MATCH_THRESHOLD:
                        is_match = True
                elif cand_name and c_name.lower() == cand_name.lower():
                    is_match = True

                # If matched by name/url, verify geo distance if both have coords
                if is_match:
                    c_lat, c_lon = c_seed.get("latitude"), c_seed.get("longitude")
                    cand_lat, cand_lon = cand_seed.get("latitude"), cand_seed.get("longitude")

                    if c_lat and c_lon and cand_lat and cand_lon:
                        dist = haversine_distance(c_lat, c_lon, cand_lat, cand_lon)
                        if dist > self.settings.GEO_DEDUP_DISTANCE_METERS:
                            # Too far apart, probably same name diff place
                            is_match = False

                if is_match:
                    cluster.append(candidate)
                    unassigned.pop(i)
                else:
                    i += 1

            clusters.append(cluster)

        return clusters

    def _merge_cluster(self, cluster: List[Dict]) -> Dict:
        """Merge a cluster of raw records into a single Golden Record dict."""

        # Find best name
        names = []
        for r in cluster:
            if n := r["enrichment"].get("estate_name"): names.append(n)
            if n := r["seed"].get("estate_name_raw"): names.append(n)

        best_name = max(names, key=len) if names else "Unknown Estate"

        # Merge sources
        sources = list(set([r["seed"].get("source") for r in cluster if r["seed"].get("source")]))

        # Find best coords
        best_lat, best_lon = None, None
        best_geo_acc = GeoAccuracy.UNKNOWN.value

        # Prefer OSM way/node > Google Maps > Unknown
        for r in cluster:
            s = r["seed"]
            if s.get("latitude") and s.get("longitude"):
                acc = s.get("geo_accuracy", "unknown")
                if acc == "rooftop":
                    best_lat, best_lon = s["latitude"], s["longitude"]
                    best_geo_acc = acc
                    break
                elif best_lat is None:
                    best_lat, best_lon = s["latitude"], s["longitude"]
                    best_geo_acc = acc

        # Aggregate lists
        varietals = set()
        processing = set()
        certs = set()
        flags = set()

        # Other simple fields
        website = None
        phone = None
        ig = None
        export = "unknown"
        address = None
        altitude = None
        rating = None
        rating_total = None

        # Iterate to collect
        for r in cluster:
            s = r["seed"]
            e = r["enrichment"]

            # Lists
            if v := e.get("varietals_grown"): varietals.update(v)
            if p := e.get("processing_methods"): processing.update(p)
            if c := e.get("certifications"): certs.update(c)
            if f := e.get("quality_flag"): flags.update(f)

            # Strings and floats (take first valid)
            if not website and (w := s.get("website") or s.get("link")): website = w
            if not phone and (p := s.get("phone")): phone = p
            if not ig and (i := s.get("instagram")): ig = i
            if not address and (a := s.get("address_raw") or e.get("address_hint")): address = a
            if not altitude and (alt := e.get("altitude_meters")): altitude = alt

            if not rating and (rt := e.get("rating")):
                rating = rt
                rating_total = e.get("user_ratings_total")

            # Export (escalate)
            if e.get("export_readiness") == "verified_exporter":
                export = "verified_exporter"
            elif export == "unknown" and e.get("export_readiness") == "mentions_export":
                export = "mentions_export"

        # Base record
        base = cluster[0]["seed"]

        record = {
            "estate_name": best_name,
            "estate_name_raw": names[0] if names else None,
            "state": base.get("state", "Unknown"),
            "district": base.get("district", "Unknown"),
            "discovery_sources": sources or ["manual"],
            "latitude": best_lat,
            "longitude": best_lon,
            "geo_accuracy": best_geo_acc,
            "website": website,
            "primary_phone": phone,
            "instagram_handle": ig,
            "address_raw": address,
            "altitude_meters": altitude,
            "rating": rating,
            "user_ratings_total": rating_total,
            "varietals_grown": list(varietals) if varietals else None,
            "processing_methods": list(processing) if processing else None,
            "certifications": list(certs) if certs else None,
            "quality_flag": list(flags) if flags else [],
            "export_readiness": export,
            "rcmc_verified": "rcmc_holder" in flags,
            "apeda_registered": "apeda_exporter" in flags,
        }

        # If no coordinates were found, assign district_center or unknown
        if best_lat is None or best_lon is None:
            best_geo_acc = "district_center" if record.get("district") else "unknown"
            record["geo_accuracy"] = best_geo_acc

        # Add ID for DB - use existing or deterministic
        best_id = None
        for r in cluster:
            if "estate_id" in r["enrichment"]:
                best_id = str(r["enrichment"]["estate_id"])
                break

        if not best_id:
            import uuid
            # Deterministic uuid based on name and coords
            name_str = best_name or "unknown"
            coord_str = f"{best_lat or 0}_{best_lon or 0}"
            seed_str = f"{name_str}_{coord_str}"
            best_id = str(uuid.uuid5(uuid.NAMESPACE_OID, seed_str))

        record["estate_id"] = best_id

        return record

    def _validate_mandatory_fields(self, record: Dict) -> bool:
        """Check if Tier 1 fields are present."""
        try:
            EstateRecord(**record)
            return True
        except Exception as e:
            logger.debug(f"Validation failed: {e}")
            return False