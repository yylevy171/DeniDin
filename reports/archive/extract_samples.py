import json
import glob
import os
from collections import defaultdict

EVENTS_DIR = os.path.expanduser("~/denidin-winprod-data/events")

def main():
    if not os.path.isdir(EVENTS_DIR):
        print(f"Error: Directory {EVENTS_DIR} not found.")
        return

    files = glob.glob(os.path.join(EVENTS_DIR, "*.json"))
    
    samples = defaultdict(list)
    counts = defaultdict(int)

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                continue
            
            src_type = data.get("source_type")
            if not src_type:
                continue
            
            # Sub-categorize Morning docs by document type if available
            doc_type = data.get("accounting_document_status_label") or data.get("invoice_type") or data.get("event_subtype") or "Unknown"

            key = src_type
            if src_type == "חשבונית":
                key = f"חשבונית ({doc_type})"

            counts[key] += 1

            if len(samples[key]) < 5:
                samples[key].append(data)

    print("Data Extraction Complete. Found the following categories and counts:\n")
    for k, v in counts.items():
        print(f"- {k}: {v} events")

    print("\nWriting samples to reports/data_samples.json...")
    with open("reports/data_samples.json", "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
