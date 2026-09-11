import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import difflib

from generate_client_status import get_report_data, MAPPING_FILE, NOTES_FILE, CLIENT_COMMENTS_FILE

def render_html():
    official_clients, stats, unmatched, manual_mapping, notes, amount_to_clients, client_comments = get_report_data()
    
    html = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="utf-8">
    <title>DeniDin - Interactive Resolution Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-hover: #334155;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --accent-color: #3b82f6;
            --success-color: #10b981;
            --danger-color: #ef4444;
            --warning-color: #f59e0b;
            --border-color: #334155;
        }
        
        body { 
            font-family: 'Inter', sans-serif; 
            margin: 0; 
            padding: 40px; 
            background: var(--bg-color); 
            color: var(--text-color); 
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1, h2 { 
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
            font-weight: 800;
        }
        
        .glass-panel {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        
        table { 
            border-collapse: separate; 
            border-spacing: 0;
            width: 100%; 
        }
        
        th, td { 
            padding: 16px; 
            text-align: right; 
            border-bottom: 1px solid var(--border-color);
        }
        
        th { 
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Row Status Colors */
        .row-green { background-color: rgba(16, 185, 129, 0.15); }
        .row-red { background-color: rgba(239, 68, 68, 0.15); }
        .row-yellow { background-color: rgba(250, 204, 21, 0.35); color: #fff; }
        
        .row-green:hover { background-color: rgba(16, 185, 129, 0.25); }
        .row-red:hover { background-color: rgba(239, 68, 68, 0.25); }
        .row-yellow:hover { background-color: rgba(250, 204, 21, 0.5); }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        .events-row {
            background-color: #0f172a;
        }
        
        .events-table {
            width: 95%;
            margin: 10px auto;
            background-color: var(--surface-color);
            border-radius: 8px;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
        }
        
        .events-table th, .events-table td {
            padding: 8px 12px;
            font-size: 0.85em;
        }
        
        .toggle-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            font-weight: bold;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        
        .toggle-btn:hover {
            background: var(--accent-color);
        }
        
        select, input[type="text"] {
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 10px 14px;
            border-radius: 8px;
            width: 100%;
            font-family: inherit;
            transition: all 0.3s ease;
        }
        
        select:focus, input[type="text"]:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
        }
        
        button.primary-btn {
            background: linear-gradient(135deg, #3b82f6, #6366f1);
            color: white;
            border: none;
            padding: 14px 28px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            position: fixed;
            bottom: 40px;
            right: 40px;
            z-index: 100;
        }
        
        button.primary-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        }
        
        .flex-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .comment-input-row {
            background-color: rgba(255,255,255,0.02);
            border-top: 1px dashed rgba(255,255,255,0.1);
        }
        
        .comment-input-row td {
            padding: 15px 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>DeniDin - Interactive Resolution Engine</h1>
        <p style="color: var(--text-muted); margin-bottom: 40px;">Displaying verified data from 2026 onwards.</p>
        
        <form action="/submit_mapping" method="POST">
            <button class="primary-btn" type="submit">Save State & Recalculate</button>

            <div class="glass-panel">
                <h2>Official Client Roster (2026)</h2>
                <table>
                    <tr>
                        <th style="width: 40px;"></th>
                        <th>Client Name</th>
                        <th>Raw Ledger Matches</th>
                        <th>Agreed (Ceiling)</th>
                        
                        <th>Invoices (Net)</th>
                    </tr>
"""
    
    import uuid
    from datetime import datetime
    counters = {"settled": {"count":0, "agreed":0, "deposits":0, "invoices":0}, "ongoing": {"count":0, "agreed":0, "deposits":0, "invoices":0}, "missing": {"count":0, "agreed":0, "deposits":0, "invoices":0}, "past": {"count":0, "agreed":0, "deposits":0, "invoices":0}}
    settled_rows_html = ""
    ongoing_rows_html = ""
    missing_rows_html = ""
    past_rows_html = ""
    
    for client in sorted(official_clients):
        data = stats[client]
        agreed = data["agreements"]
        paid = data["deposits"]
        invoices_net = data.get("invoices_net", 0.0)
        manual_agreed = data.get("manual_agreement_amount")
        latest_act_str = data.get("latest_activity")
        
        is_past = True
        if latest_act_str:
            try:
                dt = datetime.fromisoformat(latest_act_str)
                if dt > datetime(2025, 9, 1):
                    is_past = False
            except ValueError:
                pass
                
        if is_past:
            manual_agreed = None
            
        display_agreed = manual_agreed if manual_agreed is not None else agreed
        is_manual = (manual_agreed is not None)
            
        agreed_status = data.get("agreed_status", "WHITE")
        paid_status = data.get("paid_status", "WHITE")
        display_paid = invoices_net
        
        if agreed_status == "GRAY":
            agreed_html = f'<span style="color: #888; font-weight: bold;">₪{display_agreed:,.2f}</span>'
        elif agreed_status == "YELLOW":
            agreed_html = f'<span style="color: #eab308; font-weight: bold;">₪{display_agreed:,.2f}</span>'
        else:
            agreed_html = f'₪{display_agreed:,.2f}'
            
        if paid_status == "GRAY":
            paid_html = f'<span style="color: #888; font-weight: bold;">₪{display_paid:,.2f}</span>'
        elif paid_status == "YELLOW":
            paid_html = f'<span style="color: #eab308; font-weight: bold;">₪{display_paid:,.2f}</span>'
        else:
            paid_html = f'₪{display_paid:,.2f}'
            
        # Re-evaluate row colors with rounded values
        row_class = ""
        agreed_round = round(display_agreed, 2)
        paid_round = round(display_paid, 2)
        
        if agreed_round > 0 and paid_round == agreed_round:
            row_class = "row-green"
        elif agreed_round > 0 and paid_round < agreed_round:
            row_class = "row-red"
        elif (agreed_round == 0 and paid_round > 0) or (paid_round > agreed_round):
            row_class = "row-yellow"
            
        raw_names_str = ", ".join(data["raw_names"]) if data["raw_names"] else "-"
        client_id = str(uuid.uuid4())[:8]
        current_comment = client_comments.get(client, "")
        current_comment_escaped = current_comment.replace('"', '&quot;')
        
        row_html = (
            f'<tr class="{row_class}">'
            f'<td><button type="button" class="toggle-btn" onclick="toggleEvents(\'{client_id}\', this)">+</button></td>'
            f'<td style="font-weight: 600;">{client}</td>'
            f'<td style="color: var(--text-muted); font-size: 0.9em;">{raw_names_str}</td>'
            f'<td>{agreed_html}</td>'
            f''
            f'<td>₪{invoices_net:,.2f}</td>'
            f'</tr>'
            f'<tr id="events_{client_id}" class="events-row" style="display: none;">'
            f'<td colspan="5" style="padding: 0;">'
            f'<table class="events-table">'
            f'<tr><th>Date</th><th>Type</th><th>Sub Type</th><th>Description / Component</th><th>Amount</th></tr>'
        )
        if data["events"]:
            for ev in data["events"]:
                row_html += (
                    f'<tr>'
                    f'<td>{ev["date"]}</td>'
                    f'<td>{ev["type"]}</td>'
                    f'<td>{ev["subtype"]}</td>'
                    f'<td>{ev["desc"]}</td>'
                    f'<td>₪{ev["amount"]:,.2f}</td>'
                    f'</tr>'
                )
        else:
            row_html += '<tr><td colspan="5" style="text-align:center;color:gray;">No events found (active strictly prior to 2026)</td></tr>'
                                
        row_html += (
            f'<tr class="comment-input-row">'
            f'<td colspan="5">'
            f'<input type="text" name="comment_{client}" placeholder="Operations Directives / Comments..." value="{current_comment_escaped}">'
            f'</td>'
            f'</tr>'
            f'</table></td></tr>'
        )
        if is_past:
            past_rows_html += row_html
            counters["past"]["count"] += 1
            counters["past"]["agreed"] += display_agreed
            counters["past"]["deposits"] += display_paid
            counters["past"]["invoices"] += invoices_net
        else:
            if display_agreed == 0 and paid == 0 and invoices_net == 0:
                continue
                
            if row_class == "row-green":
                settled_rows_html += row_html
                counters["settled"]["count"] += 1
                counters["settled"]["agreed"] += display_agreed
                counters["settled"]["deposits"] += display_paid
                counters["settled"]["invoices"] += invoices_net
            elif row_class == "row-red":
                ongoing_rows_html += row_html
                counters["ongoing"]["count"] += 1
                counters["ongoing"]["agreed"] += display_agreed
                counters["ongoing"]["deposits"] += display_paid
                counters["ongoing"]["invoices"] += invoices_net
            else:
                missing_rows_html += row_html
                counters["missing"]["count"] += 1
                counters["missing"]["agreed"] += display_agreed
                counters["missing"]["deposits"] += display_paid
                counters["missing"]["invoices"] += invoices_net
            
    def make_section(title, color, section_id, html_content, stats, expanded=True):
        if not html_content:
            html_content = '<tr><td colspan="5" style="text-align:center;color:gray;padding:20px;">No clients in this category</td></tr>'
        display_style = '' if expanded else 'none'
        toggle_icon = '-' if expanded else '+'
        return (
            '<table style="margin-top: 40px; margin-bottom: 0; box-shadow: none;">\n'
            f'<tr style="background: var(--surface-color); cursor: pointer;" onclick="var b = document.getElementById(\'{section_id}-body\'); b.style.display = b.style.display === \'none\' ? \'\' : \'none\'; this.querySelector(\'.toggle-icon\').innerText = b.style.display === \'none\' ? \'+\' : \'-\';">\n'
            f'<td colspan="5" style="font-weight: bold; border-top: 2px solid var(--border-color); border-bottom: 2px solid var(--border-color); padding: 15px 10px;">\n'
            f'<span class="toggle-icon" style="display:inline-block; width:20px; text-align:center;">{toggle_icon}</span> '
            f'<span style="color: {color}; font-size: 1.1em;">{title}</span> '
            '</td></tr>\n'
            '</table>\n'
            f'<table id="{section_id}-body" style="display: {display_style}; margin-top: 0;">\n'
            '<tr><th style="width: 40px;"></th><th>Client Name</th><th>Raw Ledger Matches</th><th>Agreed (Ceiling)</th><th>Invoices (Net)</th></tr>\n'
            + html_content +
            f'<tr style="background: rgba(0,0,0,0.03); font-weight: bold;">'
            f'<td></td><td style="color: {color}">TOTALS: {stats["count"]} clients</td><td></td>'
            f'<td>₪{stats["agreed"]:,.2f}</td><td>₪{stats["invoices"]:,.2f}</td>'
            f'</tr>\n'
            '</table>\n'
        )

    html += '\n<div class="glass-panel">\n<h2>Official Client Roster (Active since Sep 1, 2025)</h2>\n'
    html += make_section('Settled (Agreements match Payments)', '#10b981', 'settled-clients', settled_rows_html, counters['settled'])
    html += make_section('Ongoing / Collecting (Agreements &gt; Payments)', '#ef4444', 'ongoing-clients', ongoing_rows_html, counters['ongoing'])
    html += make_section('Missing Agreement / Overpaid (Payments &gt; Agreements)', '#eab308', 'missing-clients', missing_rows_html, counters['missing'])
    html += make_section('Past Clients (Latest Activity &le; Sep 1, 2025)', 'var(--text-color)', 'past-clients', past_rows_html, counters['past'], expanded=False)
    html += '</div>\n\n'

    if unmatched:
        html += """
            <div class="glass-panel" style="border-left: 4px solid var(--danger-color);">
                <div class="flex-container">
                    <h2>Resolution Queue (Unmatched Names)</h2>
                    <span style="background: rgba(239, 68, 68, 0.2); color: var(--danger-color); padding: 4px 12px; border-radius: 20px; font-weight: bold;">{num} Items Remaining</span>
                </div>
                
                <table>
                    <tr>
                        <th>Raw Name (from ledger)</th>
                        <th>Resolution (Matched Candidates)</th>
                        <th>Notes / Commands</th>
                        <th>Agreement Amount / Source Text</th>
                        
                    </tr>
""".replace("{num}", str(len(unmatched)))
            
        for raw_name, data in sorted(unmatched.items()):
            agreed_val = data['agreements']
            current_note = notes.get(raw_name, "")
            
            # Smart Candidate Generation
            candidates_amount = amount_to_clients.get(agreed_val, set()) if agreed_val > 0 else set()
            candidates_fuzzy = set(difflib.get_close_matches(raw_name, official_clients, n=3, cutoff=0.5))
            candidates_family = set()
            
            words = raw_name.split()
            if len(words) > 1:
                last_word = words[-1]
                for oc in official_clients:
                    if last_word in oc:
                        candidates_family.add(oc)
                        
            all_smart_candidates = candidates_amount.union(candidates_fuzzy).union(candidates_family)
            
            options_html = '<option value="">--- Select Match ---</option>'
            options_html += '<option value="Unknown">Unknown (Skip for now)</option>'
            
            if all_smart_candidates:
                options_html += '<optgroup label="Smart Suggestions">'
                for oc in sorted(all_smart_candidates):
                    reasons = []
                    if oc in candidates_amount: reasons.append("Amount")
                    if oc in candidates_fuzzy: reasons.append("Fuzzy")
                    if oc in candidates_family: reasons.append("Family Name")
                    options_html += f'<option value="{oc}">{oc} ({", ".join(reasons)})</option>'
                options_html += '</optgroup>'
                
            options_html += '<optgroup label="All Clients">'
            for oc in sorted(official_clients):
                if oc not in all_smart_candidates:
                    options_html += f'<option value="{oc}">{oc}</option>'
            options_html += '</optgroup>'
                
            raw_text_display = "<br>".join(data['raw_text']) if data['raw_text'] else "No Source Text"
            if agreed_val == 0:
                agreement_display = f"<span style='color: var(--warning-color); font-size: 0.9em;'>{raw_text_display}</span>"
            else:
                agreement_display = f"₪{agreed_val:,.2f}<br><span style='color: var(--text-muted); font-size: 0.8em;'>{raw_text_display}</span>"
                
            html += f"""
                    <tr>
                        <td style="font-weight: 600;">{raw_name}</td>
                        <td>
                            <select name="mapping_{raw_name}">
                                {options_html}
                            </select>
                        </td>
                        <td>
                            <input type="text" name="notes_{raw_name}" placeholder="Type notes or commands..." value="{current_note}">
                        </td>
                        <td>{agreement_display}</td>
                        
                    </tr>"""
                    
        html += """
                </table>
            </div>
"""
    else:
        html += """
            <div class="glass-panel" style="text-align: center; border-left: 4px solid var(--success-color);">
                <h2>Resolution Queue is Empty!</h2>
                <p style="color: var(--text-muted);">All raw ledger events have been successfully mapped to official Morning clients.</p>
            </div>
"""
        
    html += """
        </form>
    </div>
    <script>
        function toggleEvents(clientId, btn) {
            var row = document.getElementById('events_' + clientId);
            if (row.style.display === 'none') {
                row.style.display = 'table-row';
                btn.textContent = '-';
            } else {
                row.style.display = 'none';
                btn.textContent = '+';
            }
        }
    </script>
</body>
</html>
"""
    return html


class MappingRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html_content = render_html()
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/submit_mapping':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data)
            
            manual_mapping = {}
            if os.path.exists(MAPPING_FILE):
                with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                    manual_mapping = json.load(f)
                    
            notes = {}
            if os.path.exists(NOTES_FILE):
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    notes = json.load(f)
                    
            client_comments = {}
            if os.path.exists(CLIENT_COMMENTS_FILE):
                with open(CLIENT_COMMENTS_FILE, "r", encoding="utf-8") as f:
                    client_comments = json.load(f)
            
            for key, values in parsed_data.items():
                val = values[0].strip()
                if not val:
                    continue
                    
                if key.startswith("mapping_"):
                    raw_name = key.replace("mapping_", "", 1)
                    manual_mapping[raw_name] = val
                elif key.startswith("notes_"):
                    raw_name = key.replace("notes_", "", 1)
                    notes[raw_name] = val
                elif key.startswith("comment_"):
                    official_client = key.replace("comment_", "", 1)
                    client_comments[official_client] = val
                    
            with open(MAPPING_FILE, "w", encoding="utf-8") as f:
                json.dump(manual_mapping, f, ensure_ascii=False, indent=4)
                
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=4)
                
            with open(CLIENT_COMMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(client_comments, f, ensure_ascii=False, indent=4)
            
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()

def run_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, MappingRequestHandler)
    print("Server running on port 8080. Open http://localhost:8080 in your browser.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Server stopped.")

if __name__ == '__main__':
    run_server()
