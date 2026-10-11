import json
import csv
import glob
import os
import difflib
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

EVENTS_DIR = os.path.expanduser("~/denidin-winprod-data/events")
CSV_PATH = os.path.join(PROJECT_ROOT, "reports", "data_exports", "clients (2).csv")
MAPPING_FILE = os.path.join(BASE_DIR, "client_mapping.json")
NOTES_FILE = os.path.join(BASE_DIR, "mapping_notes.json")
CLIENT_COMMENTS_FILE = os.path.join(BASE_DIR, "client_comments.json")
NEW_MORNING_CLIENTS_FILE = os.path.join(BASE_DIR, "new_morning_clients.json")
REMOVED_CLIENTS_FILE = os.path.join(BASE_DIR, "removed_clients.json")

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

_CACHED_EVENTS = None
_CACHED_MTIME = 0

def load_all_events(events_dir=EVENTS_DIR):
    global _CACHED_EVENTS, _CACHED_MTIME
    files = glob.glob(os.path.join(events_dir, "*.json"))
    if not files:
        return []
        
    latest_mtime = max(os.path.getmtime(f) for f in files) if files else 0
    if _CACHED_EVENTS is not None and len(_CACHED_EVENTS) == len(files) and latest_mtime <= _CACHED_MTIME:
        return list(_CACHED_EVENTS)
        
    from concurrent.futures import ThreadPoolExecutor
    
    def read_one(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=32) as executor:
        results = list(executor.map(read_one, files))
        
    _CACHED_EVENTS = [r for r in results if r is not None]
    _CACHED_MTIME = latest_mtime
    return list(_CACHED_EVENTS)

def get_report_data():
    official_clients = get_official_clients()
    manual_mapping = load_json_file(MAPPING_FILE)
    notes = load_json_file(NOTES_FILE)
    client_comments = load_json_file(CLIENT_COMMENTS_FILE)
    
    # official_client_name -> { agreements: 0, deposits: 0, invoices_net: 0, raw_names: set(), events: [] }
    stats = {c: {"agreements": 0.0, "deposits": 0.0, "invoices_net": 0.0, "raw_names": set(), "events": [], "latest_activity": None} for c in official_clients}
    
    # raw_name -> { agreements: 0, deposits: 0, raw_text: set() }
    unmatched = defaultdict(lambda: {"agreements": 0.0, "deposits": 0.0, "raw_text": set()})
    
    amount_to_clients = defaultdict(set)
    
    all_events_data = load_all_events()

                
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
                text = data.get("description") or data.get("trigger_condition") or "הסכם ללא פירוט"
                date_prefix = f"[{event_date_obj.strftime('%d.%m.%y')}] " if event_date_obj else ""
                unmatched[original_name]["raw_text"].add(f"{date_prefix}הסכם (₪{amount:,.2f}): {text}")
        elif src_type == "בנק":
            if not matched_client:
                text = data.get("description") or data.get("trigger_condition") or "הפקדת בנק / שיק"
                date_prefix = f"[{event_date_obj.strftime('%d.%m.%y')}] " if event_date_obj else ""
                unmatched[original_name]["raw_text"].add(f"{date_prefix}הפקדת בנק (₪{amount:,.2f}): {text}")
        elif src_type == "חשבונית":
            if matched_client:
                if subtype in plus_types:
                    target_dict["invoices_net"] += amount
                elif subtype in minus_types:
                    target_dict["invoices_net"] -= amount
            else:
                text = data.get("description") or data.get("trigger_condition") or subtype or "מסמך מורנינג"
                date_prefix = f"[{event_date_obj.strftime('%d.%m.%y')}] " if event_date_obj else ""
                unmatched[original_name]["raw_text"].add(f"{date_prefix}חשבונית/מסמך (₪{amount:,.2f}): {text}")

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
                    matches = re.findall(r"הסכם\s+(?:\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\s+)?(?:-\s*)?([1-9][\d,+]{2,})", comment)
                    if matches:
                        try:
                            total_amt = 0.0
                            for m in matches:
                                clean_m = m.rstrip(",").rstrip(".").strip()
                                if "+" in clean_m:
                                    total_amt += sum(float(part.replace(",", "").strip()) for part in clean_m.split("+") if part.replace(",", "").strip())
                                else:
                                    total_amt += float(clean_m.replace(",", ""))
                            if total_amt > 0:
                                stats[c]["manual_agreement_amount"] = total_amt
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

        if stats[c]["latest_activity"] and hasattr(stats[c]["latest_activity"], "isoformat"):
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

    # Apply Directives from client_comments:
    # 1. Merge (לאחד / אוחד): add numbers & events to target client, remove source client
    # 2. Check (לבדוק): flag for dedicated follow-up section at bottom
    # 3. Close (לסגור): adjust missing numbers to match, mark as manually settled green

    # Collect merge directives
    merges_to_apply = [] # (source_client, target_client)
    for c, comment_text in client_comments.items():
        if not comment_text:
            continue
        if "לאחד" in comment_text or "אוחד" in comment_text:
            m = re.search(r'[״\"\'׳]([^״\"\'׳]+)[״\"\'׳]', comment_text)
            if m:
                target_raw = m.group(1).strip()
                norm = target_raw.replace('׳', '').replace('״', '').replace("'", '').replace('"', '').strip()
                resolved_target = None
                if target_raw in stats:
                    resolved_target = target_raw
                else:
                    for oc in official_clients:
                        oc_norm = oc.replace('׳', '').replace('״', '').replace("'", '').replace('"', '').strip()
                        if norm == oc_norm:
                            resolved_target = oc
                            break
                    if not resolved_target:
                        words = [w for w in norm.split() if len(w) > 2]
                        best_candidate = None
                        best_score = 0
                        for oc in official_clients:
                            if 'קאולה' in oc and ('קואלה' in norm or 'פאות' in norm):
                                best_candidate = oc
                                best_score = 999
                                break
                            score = sum(1 for w in words if w in oc)
                            if score > best_score:
                                best_score = score
                                best_candidate = oc
                        if best_score > 0:
                            resolved_target = best_candidate
                        else:
                            matches = difflib.get_close_matches(target_raw, official_clients, n=1, cutoff=0.4)
                            if matches:
                                resolved_target = matches[0]

                if resolved_target and resolved_target in stats and resolved_target != c:
                    merges_to_apply.append((c, resolved_target))

    for src, tgt in merges_to_apply:
        if src in stats and tgt in stats:
            src_data = stats[src]
            tgt_data = stats[tgt]
            # Merge amounts
            tgt_data["agreements"] += src_data["agreements"]
            tgt_data["deposits"] += src_data["deposits"]
            tgt_data["invoices_net"] += src_data["invoices_net"]
            if src_data.get("manual_agreement_amount") is not None:
                if tgt_data.get("manual_agreement_amount") is not None:
                    tgt_data["manual_agreement_amount"] += src_data["manual_agreement_amount"]
                else:
                    tgt_data["manual_agreement_amount"] = tgt_data["agreements"] + src_data["manual_agreement_amount"]
            # Merge events and raw names
            tgt_data["events"].extend(src_data["events"])
            tgt_data["raw_names"].extend([r for r in src_data["raw_names"] if r not in tgt_data["raw_names"]])
            if src not in tgt_data["raw_names"]:
                tgt_data["raw_names"].append(src)
            # Mark source as merged away
            src_data["is_merged_away"] = True

    # Process Check, Close, Active, and Delete flags
    removed_clients = []
    for c in stats:
        comment_text = client_comments.get(c, "")
        if not comment_text:
            continue

        # Active Client directive (לקוח פעיל)
        if "לקוח פעיל" in comment_text or "לקוחה פעילה" in comment_text:
            stats[c]["is_active_client"] = True

        # Delete directive (למחוק / להסיר) -> Move to Past Clients
        if "למחוק" in comment_text or (comment_text.strip() == "להסיר") or ("להסיר מהרשימה" in comment_text and not stats[c].get("is_merged_away")):
            stats[c]["is_delete_past"] = True
            removed_clients.append({
                "client_name": c,
                "reason": comment_text,
                "agreements": stats[c]["agreements"],
                "invoices_net": stats[c]["invoices_net"]
            })
            continue

        # Check directive (לבדוק)
        if "לבדוק" in comment_text:
            stats[c]["is_check"] = True

        # Close directive (לסגור / אפשר לסגור) - strictly close, not triggered by incidental words like 'נסגר'
        is_explicit_close = ("לסגור" in comment_text or "אפשר לסגור" in comment_text) and not stats[c].get("is_check")
        if is_explicit_close:
            stats[c]["is_manually_settled"] = True
            cur_agreed = stats[c].get("manual_agreement_amount")
            if cur_agreed is None:
                cur_agreed = stats[c]["agreements"]
            cur_paid = stats[c].get("invoices_net", 0.0)

            matched_val = max(cur_agreed, cur_paid)
            if matched_val > 0:
                stats[c]["manual_agreement_amount"] = matched_val
                stats[c]["invoices_net"] = matched_val
                # If agreement was shifted up, color agreement YELLOW (inferred)
                if cur_agreed < matched_val:
                    stats[c]["agreed_status"] = "YELLOW"
                    stats[c]["agreed_inferred"] = True
                # If payment was shifted up, color payment YELLOW (inferred)
                if cur_paid < matched_val:
                    stats[c]["paid_status"] = "YELLOW"
                    stats[c]["paid_inferred"] = True

    with open(REMOVED_CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(removed_clients, f, ensure_ascii=False, indent=4)
        
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

def export_static_reports():
    official_clients, stats, final_unmatched, manual_mapping, notes, amount_to_clients, client_comments = get_report_data()
    
    rows = []
    
    # 1. Unmatched rows
    for raw_name, udata in sorted(final_unmatched.items()):
        agreed = udata["agreements"]
        rows.append({
            "name": f"UNMATCHED: {raw_name}",
            "agreed": agreed,
            "open": 0.0,
            "paid": 0.0,
            "gap": agreed
        })
        
    # 2. Official clients
    for client in sorted(official_clients):
        data = stats[client]
        agreed = data["agreements"]
        manual_agreed = data.get("manual_agreement_amount")
        display_agreed = manual_agreed if manual_agreed is not None else agreed
        invoices_net = data.get("invoices_net", 0.0)
        gap = display_agreed - invoices_net
        
        # Only include if there is activity
        if display_agreed > 0 or invoices_net > 0 or data["events"]:
            rows.append({
                "name": client,
                "agreed": display_agreed,
                "open": 0.0,
                "paid": invoices_net,
                "gap": gap
            })

    # Write CSV
    with open("reports/final_client_status.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Client Name", "Agreements (Ceiling)", "Invoiced (Open)", "Invoiced (Paid)", "Uninvoiced Gap"])
        for r in rows:
            writer.writerow([r["name"], r["agreed"], r["open"], r["paid"], r["gap"]])
            
    # Write MD
    md_content = """# Client Status & Payments Report

> **Note on Logic:**
> - **Agreements (Ceiling)**: Total of all WhatsApp agreements. This is often excluding VAT and may contain conditionals.
> - **Invoiced (Paid / Net)**: Fully captured documents in Morning.
> - **Uninvoiced Gap**: Agreements minus all Invoices (Paid). A positive number means we have an agreement but haven't collected/invoiced fully yet. A negative number means we invoiced more than the base agreement.

| Client Name | Agreements (Ceiling) | Invoiced (Open) | Invoiced (Paid) | Uninvoiced Gap |
|-------------|----------------------|-----------------|-----------------|----------------|
"""
    for r in rows:
        md_content += f"| {r['name']} | ₪{r['agreed']:,.2f} | ₪{r['open']:,.2f} | ₪{r['paid']:,.2f} | ₪{r['gap']:,.2f} |\n"
        
    with open("reports/final_client_status.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Static reports successfully updated: {len(rows)} rows (Unmatched: {len(final_unmatched)}, Official active: {len(rows)-len(final_unmatched)})")

if __name__ == "__main__":
    export_static_reports()

