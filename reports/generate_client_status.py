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
    # official_client_name -> { agreements: 0, deposits: 0, invoices_net: 0, raw_names: set(), events: [], latest_activity: None }
    stats = {c: {"agreements": 0.0, "deposits": 0.0, "invoices_net": 0.0, "raw_names": set(), "events": [], "latest_activity": None} for c in official_clients}
    
    # raw_name -> { agreements: 0, deposits: 0, raw_text: set() }
    unmatched = defaultdict(lambda: {"agreements": 0.0, "deposits": 0.0, "raw_text": set()})
    
    amount_to_clients = defaultdict(set)
    
    files = glob.glob(os.path.join(EVENTS_DIR, "*.json"))
    
    all_events_data = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                all_events_data.append(data)
            except Exception:
                pass
                
    import csv
    try:
        with open('reports/morning_docs_010925_100926.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get("תאריך ערך")
                if date_str:
                    d, m, y = map(int, date_str.split("/"))
                    if y == 2025:
                        all_events_data.append({
                            "source_type": "חשבונית",
                            "client_name": row.get("לקוח", "Unknown"),
                            "amount": row.get("סכום", "0").replace(",", ""),
                            "event_subtype": row.get("סוג המסמך", ""),
                            "event_datetime": f"{y}-{m:02d}-{d:02d}",
                            "description": row.get("תיאור", "")
                        })
    except Exception:
        pass
    
    plus_types = ["חשבונית מס קבלה", "חשבונית מס / קבלה", "קבלה", "320", "400", 320, 400]
    minus_types = []
    

    # Real deduplication logic based on CEO feedback
    deduped = []
    seen = set()
    for data in all_events_data:
        amount_val = str(data.get("amount", "0")).replace(",", "")
        client = data.get("client_name", "")
        event_datetime = data.get("event_datetime") or data.get("txn_date") or ""
        subtype = str(data.get("event_subtype", ""))
        
        date_part = event_datetime.split(" ")[0]
        if "/" in date_part:
            parts = date_part.split("/")
            if len(parts[0]) == 4:
                date_part = f"{parts[0]}-{parts[1]:0>2}-{parts[2]:0>2}"
            else:
                date_part = f"{parts[2]}-{parts[1]:0>2}-{parts[0]:0>2}"
                
        # Some floats like "1500" vs "1500.0"
        try:
            amount_f = float(amount_val)
        except ValueError:
            amount_f = 0.0
            
        h = (client, amount_f, date_part, subtype)
        if h not in seen:
            seen.add(h)
            deduped.append(data)
    all_events_data = deduped
    
    for data in all_events_data:
        event_datetime = data.get("event_datetime") or data.get("txn_date") or ""
        from datetime import datetime
        event_date_obj = None
        if event_datetime:
            try:
                date_part = event_datetime.split(" ")[0]
                # Format is DD/MM/YYYY or YYYY-MM-DD
                if "/" in date_part:
                    d, m, y = [int(x) for x in date_part.split("/")]
                    event_date_obj = datetime(y, m, d)
                else:
                    y, m, d = [int(x) for x in date_part.split("-")]
                    event_date_obj = datetime(y, m, d)
            except Exception:
                pass
                
        raw_client = data.get("client_name") or data.get("payer_name") or "Unknown"
        matched_client, original_name = fuzzy_match(raw_client, official_clients, manual_mapping)
        
        if event_date_obj and matched_client:
            current_latest = stats[matched_client]["latest_activity"]
            if current_latest is None or event_date_obj > current_latest:
                stats[matched_client]["latest_activity"] = event_date_obj
                
        if event_date_obj and event_date_obj < datetime(2025, 9, 1):
            continue
                
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
            if not matched_client:
                text = data.get("description") or data.get("trigger_condition") or "No description"
                date_prefix = f"[{event_date_obj.strftime('%d.%m.%y')}] " if event_date_obj else ""
                unmatched[original_name]["raw_text"].add(date_prefix + text)
        elif src_type == "בנק":
            pass  # Completely ignored per CEO instructions
        elif src_type == "חשבונית" and matched_client:
            if subtype in plus_types:
                target_dict["invoices_net"] += amount
            elif subtype in minus_types:
                target_dict["invoices_net"] -= amount

    import re
    import collections
    
    for c in stats:
        comment = client_comments.get(c, "")
        stats[c]["agreed_status"] = "WHITE"
        stats[c]["paid_status"] = "WHITE"
        
        if comment:
            unclear_flags = ["לבדוק", "לא ברור", "חסר"]
            is_unclear = any(flag in comment for flag in unclear_flags)
            
            # Agreements
            if "הסכם" in comment:
                # Extract date DD.MM.YY or DD.MM.YYYY
                date_match = re.search(r"הסכם\s+(\d{1,2})[./](\d{1,2})[./](\d{2,4})", comment)
                if date_match:
                    try:
                        d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                        if y < 100: y += 2000
                        comment_date_obj = datetime(y, m, d)
                        current_latest = stats[c]["latest_activity"]
                        if current_latest is None or comment_date_obj > current_latest:
                            stats[c]["latest_activity"] = comment_date_obj
                    except Exception:
                        pass

                # Manual agreement amount extraction
                total_match = re.search(r"סה[״\"']כ הסכמים\s*(?:-\s*)?([1-9][\d,]*)", comment)
                if total_match:
                    try:
                        manual_amt = float(total_match.group(1).replace(",", ""))
                        stats[c]["manual_agreement_amount"] = manual_amt
                        stats[c]["agreed_status"] = "YELLOW" if is_unclear else "GRAY"
                    except ValueError:
                        stats[c]["agreed_status"] = "YELLOW"
                else:
                    matches = re.findall(r"הסכם\s+(?:\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\s+)?(?:-\s*)?([1-9][\d,]{2,})", comment)
                    if matches:
                        try:
                            amt = sum(float(m.replace(",", "")) for m in matches)
                            if amt > 0:
                                stats[c]["manual_agreement_amount"] = amt
                                stats[c]["agreed_status"] = "YELLOW" if is_unclear else "GRAY"
                        except ValueError:
                            stats[c]["agreed_status"] = "YELLOW"
                    elif is_unclear:
                        stats[c]["agreed_status"] = "YELLOW"
            elif is_unclear:
                stats[c]["agreed_status"] = "YELLOW"
                
            # Deposits
            if "remove" in comment.lower() or "להוריד" in comment:
                dep_events = [ev for ev in stats[c]["events"] if ev["type"] == "בנק"]
                if dep_events:
                    amounts = [ev["amount"] for ev in dep_events]
                    counts = collections.Counter(amounts)
                    dups = [amt for amt, count in counts.items() if count > 1]
                    if len(dups) == 1:
                        dup_amt = dups[0]
                        stats[c]["deposits"] -= dup_amt
                        stats[c]["paid_status"] = "YELLOW" if is_unclear else "GRAY"
                    else:
                        stats[c]["paid_status"] = "YELLOW"
                else:
                    stats[c]["paid_status"] = "YELLOW"
            elif is_unclear and stats[c]["paid_status"] == "WHITE":
                stats[c]["paid_status"] = "YELLOW"

        if stats[c]["latest_activity"]:
            stats[c]["latest_activity"] = stats[c]["latest_activity"].isoformat()
            
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
        if any(term in note for term in ["להסיר", "לא לקוחה", "אוחד", "שיניתי את השם", "remove from the list"]):
            continue
        elif "לקוח חדש במורנינג" in note or "need a new morning client" in note:
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
