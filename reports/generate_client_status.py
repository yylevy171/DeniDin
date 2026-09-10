import json
import csv
import glob
import os
import difflib
from collections import defaultdict

EVENTS_DIR = os.path.expanduser("~/denidin-winprod-data/events")
CSV_PATH = "reports/clients (1).csv"
MAPPING_FILE = "reports/client_mapping.json"
NOTES_FILE = "reports/mapping_notes.json"
CLIENT_COMMENTS_FILE = "reports/client_comments.json"
NEW_MORNING_CLIENTS_FILE = "reports/new_morning_clients.json"

def get_official_clients():
    clients = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("שם לקוח", "").strip()
            if name:
                clients.append(name)
    return clients

def load_json_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def fuzzy_match(name, official_clients, manual_mapping):
    if not name:
        return None, name
        
    name = name.strip()
    
    if name in manual_mapping and manual_mapping[name]:
        if manual_mapping[name] == "Unknown":
            return None, name
        if manual_mapping[name] in official_clients:
            return manual_mapping[name], name
            
    if name in official_clients:
        return name, name
        
    matches = difflib.get_close_matches(name, official_clients, n=1, cutoff=0.8)
    if matches:
        return matches[0], name
        
    return None, name

def get_report_data():
    official_clients = get_official_clients()
    manual_mapping = load_json_file(MAPPING_FILE)
    notes = load_json_file(NOTES_FILE)
    client_comments = load_json_file(CLIENT_COMMENTS_FILE)
    
    # official_client_name -> { agreements: 0, deposits: 0, invoices_net: 0, raw_names: set(), events: [] }
    stats = {c: {"agreements": 0.0, "deposits": 0.0, "invoices_net": 0.0, "raw_names": set(), "events": []} for c in official_clients}
    
    # raw_name -> { agreements: 0, deposits: 0, raw_text: set() }
    unmatched = defaultdict(lambda: {"agreements": 0.0, "deposits": 0.0, "raw_text": set()})
    
    amount_to_clients = defaultdict(set)
    
    files = glob.glob(os.path.join(EVENTS_DIR, "*.json"))
    
    plus_types = ["חשבונית מס קבלה", "חשבונית מס / קבלה", "קבלה"]
    minus_types = ["חשבון זיכוי", "חשבונית זיכוי"]
    
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                continue
            
            event_datetime = data.get("event_datetime") or data.get("txn_date") or ""
            if event_datetime:
                try:
                    date_part = event_datetime.split(" ")[0]
                    year = int(date_part.split("/")[2])
                    if year < 2026:
                        continue
                except Exception:
                    pass
            
            src_type = data.get("source_type")
            if not src_type:
                continue
                
            raw_client = data.get("client_name") or data.get("payer_name") or "Unknown"
            matched_client, original_name = fuzzy_match(raw_client, official_clients, manual_mapping)
            
            amount_val = data.get("amount")
            if amount_val is None:
                continue
                
            try:
                amount = float(amount_val)
            except ValueError:
                continue
                
            subtype = data.get("event_subtype", "")
            
            if src_type == "חשבונית" and matched_client:
                amount_to_clients[amount].add(matched_client)

            if matched_client:
                target_dict = stats[matched_client]
                if original_name != matched_client:
                    target_dict["raw_names"].add(original_name)
                    
                desc = data.get("description") or data.get("trigger_condition") or data.get("component_label") or ""
                target_dict["events"].append({
                    "date": event_datetime,
                    "amount": amount,
                    "type": src_type,
                    "subtype": subtype,
                    "desc": desc
                })
            else:
                target_dict = unmatched[original_name]
                
            if src_type == "הסכם":
                target_dict["agreements"] += amount
                if amount == 0 and not matched_client:
                    text = data.get("description") or data.get("trigger_condition") or "No description"
                    unmatched[original_name]["raw_text"].add(text)
            elif src_type == "בנק":
                target_dict["deposits"] += amount
            elif src_type == "חשבונית" and matched_client:
                if subtype in plus_types:
                    target_dict["invoices_net"] += amount
                elif subtype in minus_types:
                    target_dict["invoices_net"] -= amount

    import re
    for c in stats:
        comment = client_comments.get(c, "")
        if "הסכם" in comment:
            match = re.search(r"הסכם.*?-\s*([\d,]+)", comment)
            if match:
                manual_amt = float(match.group(1).replace(",", ""))
                stats[c]["manual_agreement_amount"] = manual_amt

        stats[c]["raw_names"] = list(stats[c]["raw_names"])
        def sort_key(e):
            dt = e["date"]
            if not dt:
                return "00000000"
            parts = dt.split(" ")
            d_parts = parts[0].split("/")
            if len(d_parts) == 3:
                d_str = d_parts[2] + d_parts[1] + d_parts[0]
            else:
                d_str = dt
            if len(parts) > 1:
                d_str += parts[1]
            return d_str
            
        stats[c]["events"].sort(key=sort_key)
        
    final_unmatched = {}
    new_morning_clients = []
    
    # Process notes and filter unmatched queue
    for u, udata in unmatched.items():
        udata["raw_text"] = list(udata["raw_text"])
        note = notes.get(u, "").lower()
        if "remove from the list" in note:
            continue
        elif "need a new morning client" in note:
            new_morning_clients.append({
                "raw_name": u,
                "agreements": udata["agreements"],
                "deposits": udata["deposits"],
                "note": notes.get(u, "")
            })
            continue
        else:
            final_unmatched[u] = udata

    # Save new morning clients to file
    with open(NEW_MORNING_CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_morning_clients, f, ensure_ascii=False, indent=4)
        
    return official_clients, stats, final_unmatched, manual_mapping, notes, amount_to_clients, client_comments

if __name__ == "__main__":
    print("This module provides get_report_data(). Run reports/mapping_server.py to see the interactive UI.")
