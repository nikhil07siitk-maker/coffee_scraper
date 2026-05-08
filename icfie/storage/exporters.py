"""Data exporters."""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

class CSVExporter:
    @staticmethod
    def export(records: List[Dict[str, Any]], filepath: str) -> None:
        if not records:
            return

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get all keys to form headers
        headers = set()
        for r in records:
            headers.update(r.keys())

        # Ensure ID and name are first
        header_list = list(headers)
        for field in ["estate_name", "estate_id"]:
            if field in header_list:
                header_list.remove(field)
                header_list.insert(0, field)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header_list)
            writer.writeheader()

            for record in records:
                # Convert dicts/lists to JSON strings for CSV
                row = {}
                for k, v in record.items():
                    if isinstance(v, (list, dict)):
                        row[k] = json.dumps(v)
                    else:
                        row[k] = v
                writer.writerow(row)

class JSONLExporter:
    @staticmethod
    def export(records: List[Dict[str, Any]], filepath: str) -> None:
        if not records:
            return

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record) + '\n')