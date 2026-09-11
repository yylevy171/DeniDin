import os
import json
import subprocess
import difflib
import re

from generate_client_status import get_report_data, CLIENT_COMMENTS_FILE

def clean_word(w):
    return re.sub(r'[^\w\s]', '', w)

def get_zero_agreement_clients():
    official_clients, stats, _, _, _, _, _ = get_report_data()
    zero_clients = []
    for client, data in stats.items():
        if data["agreements"] == 0:
            zero_clients.append(client)
    return zero_clients

def extract_from_docx(zero_clients):
    folder = "reports/19.8.26 whatsapp export"
    files = [f for f in os.listdir(folder) if f.endswith(".docx")]
    
    extracted = {}
    
    for f in files:
        base_name = f.replace(".docx", "").replace("הצעת שכט", "").replace("הסכם שכט", "").strip()
        matches = difflib.get_close_matches(base_name, zero_clients, n=1, cutoff=0.7)
        
        if matches:
            client = matches[0]
            # Use textutil to read content
            path = os.path.join(folder, f)
            result = subprocess.run(["textutil", "-stdout", "-cat", "txt", path], capture_output=True, text=True)
            text = result.stdout
            
            # Find amounts
            amounts = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*₪', text)
            if not amounts:
                 amounts = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*ש"ח', text)
            if amounts:
                max_amt = max([int(a.replace(",", "")) for a in amounts])
                extracted[client] = f"הסכם 01.01.26 - {max_amt}, מקובץ: {f}"
    
    return extracted

def extract_from_whatsapp(zero_clients):
    chat_file = "reports/19.8.26 whatsapp export/WhatsApp Chat with $$ גבייה אילה $$.txt"
    extracted = {}
    
    with open(chat_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    valid_lines = []
    for line in lines:
        if "₪" in line or "שכט" in line or "שכר" in line or "הסכם" in line or "ש\"ח" in line:
            valid_lines.append((line, [clean_word(w) for w in line.split() if w.strip()]))
            
    for client in zero_clients:
        client_words = [clean_word(w) for w in client.split() if w.strip()]
        if not client_words:
            continue
            
        for line, text_words in valid_lines:
            # Stricter match: ALL words of the client name must find a close match in the line
            all_matched = True
            for cw in client_words:
                if not difflib.get_close_matches(cw, text_words, n=1, cutoff=0.85):
                    all_matched = False
                    break
                    
            if all_matched:
                # extract amount
                amounts = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*₪', line)
                if not amounts:
                    amounts = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*ש"ח', line)
                if not amounts:
                    amounts = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*שח', line)
                    
                if amounts:
                    max_amt = max([int(a.replace(",", "")) for a in amounts])
                    
                    # extract date: 12/20/23 -> DD.MM.YY
                    date_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})', line)
                    if date_match:
                        m, d, y = date_match.groups()
                        date_str = f"{int(d):02d}.{int(m):02d}.{y}"
                    else:
                        date_str = "01.01.26"
                    
                    exact_msg = line.strip()
                    extracted[client] = f"הסכם {date_str} - {max_amt}, {exact_msg}"
                    break
                        
    return extracted

def main():
    zero_clients = get_zero_agreement_clients()
    print(f"Found {len(zero_clients)} official clients with 0 agreements.")
    
    docx_extracted = extract_from_docx(zero_clients)
    chat_extracted = extract_from_whatsapp(zero_clients)
    
    # Merge
    all_extracted = {}
    for c, val in docx_extracted.items():
        all_extracted[c] = val
    for c, val in chat_extracted.items():
        if c not in all_extracted:
            all_extracted[c] = val
            
    print(f"Successfully extracted {len(all_extracted)} missing agreements.")
    
    if os.path.exists(CLIENT_COMMENTS_FILE):
        with open(CLIENT_COMMENTS_FILE, "r", encoding="utf-8") as f:
            comments = json.load(f)
    else:
        comments = {}
        
    for c, val in all_extracted.items():
        if c in comments and comments[c]:
            if val not in comments[c]:
                comments[c] = comments[c] + "\n" + val
        else:
            comments[c] = val
            
    with open(CLIENT_COMMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=4)
        
    print(f"Updated {CLIENT_COMMENTS_FILE}")

if __name__ == "__main__":
    main()
