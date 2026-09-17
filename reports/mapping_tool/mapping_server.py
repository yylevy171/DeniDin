import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import difflib
from datetime import datetime
import uuid

from generate_client_status import get_report_data, MAPPING_FILE, NOTES_FILE, CLIENT_COMMENTS_FILE

def render_html():
    official_clients, stats, unmatched, manual_mapping, notes, amount_to_clients, client_comments = get_report_data()
    
    html = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="utf-8">
    <title>דני-דין · מנוע סנכרון והתאמות לקוחות</title>
    <link rel="icon" type="image/png" href="/honigman-law-logo.png" />
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
        .row-green-manual { background-color: rgba(6, 182, 212, 0.22); border-left: 4px solid #06b6d4; }
        .row-red { background-color: rgba(239, 68, 68, 0.15); }
        .row-yellow { background-color: rgba(250, 204, 21, 0.35); color: #fff; }
        
        .row-green:hover { background-color: rgba(16, 185, 129, 0.25); }
        .row-green-manual:hover { background-color: rgba(6, 182, 212, 0.35); }
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
        <h1>דני-דין - מנוע סנכרון והתאמות</h1>
        <p style="color: var(--text-muted); margin-bottom: 40px;">נתונים מאומתים החל משנת 2026 ואילך.</p>
        
        <form action="/submit_mapping" method="POST">
            <button class="primary-btn" type="submit">שמור מצב וחשב מחדש</button>
"""
    
    counters = {
        "active": {"count":0, "agreed":0, "deposits":0, "invoices":0},
        "settled": {"count":0, "agreed":0, "deposits":0, "invoices":0},
        "ongoing": {"count":0, "agreed":0, "deposits":0, "invoices":0},
        "missing": {"count":0, "agreed":0, "deposits":0, "invoices":0},
        "past": {"count":0, "agreed":0, "deposits":0, "invoices":0},
        "check": {"count":0, "agreed":0, "deposits":0, "invoices":0}
    }
    active_rows_html = ""
    settled_rows_html = ""
    ongoing_rows_html = ""
    missing_rows_html = ""
    past_rows_html = ""
    check_rows_html = ""
    
    for client in sorted(official_clients):
        data = stats[client]
        
        # Rule 3: Merged away clients are suppressed
        if data.get("is_merged_away"):
            continue

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

        # Rule 5: Clients marked to delete (למחוק / להסיר) are routed to Past section
        if data.get("is_delete_past"):
            is_past = True
                
        if is_past and not data.get("is_manually_settled"):
            manual_agreed = None
            
        display_agreed = manual_agreed if manual_agreed is not None else agreed
        is_manual = (manual_agreed is not None)
            
        agreed_status = data.get("agreed_status", "WHITE")
        paid_status = data.get("paid_status", "WHITE")
        display_paid = invoices_net
        
        # Format agreement display with inferred coloring
        if data.get("agreed_inferred") or agreed_status == "YELLOW":
            agreed_html = f'<span style="color: #eab308; font-weight: bold;">₪{display_agreed:,.2f}</span>'
        elif agreed_status == "GRAY":
            agreed_html = f'<span style="color: #888; font-weight: bold;">₪{display_agreed:,.2f}</span>'
        else:
            agreed_html = f'₪{display_agreed:,.2f}'
            
        # Format paid display with inferred coloring
        if data.get("paid_inferred") or paid_status == "YELLOW":
            paid_html = f'<span style="color: #eab308; font-weight: bold;">₪{display_paid:,.2f}</span>'
        elif paid_status == "GRAY":
            paid_html = f'<span style="color: #888; font-weight: bold;">₪{display_paid:,.2f}</span>'
        else:
            paid_html = f'₪{display_paid:,.2f}'
            
        # Re-evaluate row colors with rounded values
        row_class = ""
        agreed_round = round(display_agreed, 2)
        paid_round = round(display_paid, 2)
        
        if data.get("is_manually_settled"):
            row_class = "row-green-manual"
        elif agreed_round > 0 and paid_round == agreed_round:
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
            f'<td>{paid_html}</td>'
            f'</tr>'
            f'<tr id="events_{client_id}" class="events-row" style="display: none;">'
            f'<td colspan="5" style="padding: 0;">'
            f'<table class="events-table">'
            f'<tr><th>תאריך</th><th>סוג</th><th>תת-סוג</th><th>תיאור / רכיב</th><th>סכום</th></tr>'
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
            row_html += '<tr><td colspan="5" style="text-align:center;color:gray;">לא נמצאו אירועים</td></tr>'
                                
        row_html += (
            f'<tr class="comment-input-row">'
            f'<td colspan="5">'
            f'<input type="text" name="comment_{client}" placeholder="הנחיות תפעול / הערות ללקוח..." value="{current_comment_escaped}">'
            f'</td>'
            f'</tr>'
            f'</table></td></tr>'
        )

        # Section Routing:
        # Priority 1: Rule 2: To check (לבדוק) goes to dedicated follow-up section at the bottom
        if data.get("is_check"):
            check_rows_html += row_html
            counters["check"]["count"] += 1
            counters["check"]["agreed"] += display_agreed
            counters["check"]["deposits"] += display_paid
            counters["check"]["invoices"] += invoices_net
            continue

        # Priority 2: Section (f): Current clients (לקוחות פעילים)
        if data.get("is_active_client"):
            active_rows_html += row_html
            counters["active"]["count"] += 1
            counters["active"]["agreed"] += display_agreed
            counters["active"]["deposits"] += display_paid
            counters["active"]["invoices"] += invoices_net
            continue

        # Priority 3: Manually settled clients ALWAYS go to Settled section
        if data.get("is_manually_settled"):
            settled_rows_html += row_html
            counters["settled"]["count"] += 1
            counters["settled"]["agreed"] += display_agreed
            counters["settled"]["deposits"] += display_paid
            counters["settled"]["invoices"] += invoices_net
            continue

        # Priority 4: Past clients
        if is_past:
            past_rows_html += row_html
            counters["past"]["count"] += 1
            counters["past"]["agreed"] += display_agreed
            counters["past"]["deposits"] += display_paid
            counters["past"]["invoices"] += invoices_net
        else:
            if display_agreed == 0 and paid == 0 and invoices_net == 0:
                continue
                
            if row_class in ["row-green", "row-green-manual"]:
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
            
    def make_section(title, color, section_id, html_content, stats, expanded=False):
        if not html_content:
            html_content = '<tr><td colspan="5" style="text-align:center;color:gray;padding:20px;">אין לקוחות בקטגוריה זו</td></tr>'
        display_style = '' if expanded else 'none'
        toggle_icon = '-' if expanded else '+'
        return (
            '<table style="margin-top: 25px; margin-bottom: 0; box-shadow: none;">\n'
            f'<tr style="background: var(--surface-color); cursor: pointer;" onclick="var b = document.getElementById(\'{section_id}-body\'); b.style.display = b.style.display === \'none\' ? \'\' : \'none\'; this.querySelector(\'.toggle-icon\').innerText = b.style.display === \'none\' ? \'+\' : \'-\';">\n'
            f'<td colspan="5" style="font-weight: bold; border-top: 2px solid var(--border-color); border-bottom: 2px solid var(--border-color); padding: 15px 10px;">\n'
            f'<span class="toggle-icon" style="display:inline-block; width:20px; text-align:center;">{toggle_icon}</span> '
            f'<span style="color: {color}; font-size: 1.1em;">{title}</span> '
            '</td></tr>\n'
            '</table>\n'
            f'<table id="{section_id}-body" style="display: {display_style}; margin-top: 0;">\n'
            '<tr><th style="width: 40px;"></th><th>שם לקוח</th><th>שמות מקבילים בספרים</th><th>סכום בהסכם (תקרה)</th><th>חשבוניות וקבלות (נטו)</th></tr>\n'
            + html_content +
            f'<tr style="background: rgba(0,0,0,0.03); font-weight: bold;">'
            f'<td></td><td style="color: {color}">סה״כ: {stats["count"]} לקוחות</td><td></td>'
            f'<td>₪{stats["agreed"]:,.2f}</td><td>₪{stats["invoices"]:,.2f}</td>'
            f'</tr>\n'
            '</table>\n'
        )

    html += '\n<div class="glass-panel">\n<h2>לקוחות</h2>\n'
    html += make_section('לקוחות פעילים', '#38bdf8', 'active-clients', active_rows_html, counters['active'], expanded=False)
    html += make_section('לקוחות סגורים - הכל שולם', '#10b981', 'settled-clients', settled_rows_html, counters['settled'], expanded=False)
    html += make_section('לקוחות שחסר תשלומים', '#ef4444', 'ongoing-clients', ongoing_rows_html, counters['ongoing'], expanded=False)
    html += make_section('לקוחות שחסר הסכמים', '#eab308', 'missing-clients', missing_rows_html, counters['missing'], expanded=False)
    html += make_section('לקוחות עבר', 'var(--text-color)', 'past-clients', past_rows_html, counters['past'], expanded=False)
    html += '</div>\n\n'

    # Rule 2: Dedicated לבדוק! section brought up above Resolution Queue, with remaining count badge
    check_count = counters['check']['count']
    html += f"""
        <div class="glass-panel" style="border-left: 4px solid #3b82f6;">
            <div class="flex-container" style="cursor: pointer;" onclick="var b = document.getElementById('check-clients-panel-body'); b.style.display = b.style.display === 'none' ? '' : 'none'; this.querySelector('.toggle-icon').innerText = b.style.display === 'none' ? '+' : '-';">
                <h2><span class="toggle-icon" style="display:inline-block; width:25px; text-align:center;">+</span> לבדוק!</h2>
                <span style="background: rgba(59, 130, 246, 0.2); color: #38bdf8; padding: 4px 12px; border-radius: 20px; font-weight: bold;">{check_count} לקוחות לבדיקה</span>
            </div>
            <div id="check-clients-panel-body" style="display: none; margin-top: 15px;">
                <p style="color: var(--text-muted); margin-bottom: 20px;">לקוחות שסומנו לבדיקה או המשך מעקב. הצבע מעיד על מאזן החשבון (אדום: הסכמים גבוהים מתשלומים, צהוב: תשלומים גבוהים מהסכמים / חסר הסכם).</p>
                {make_section('רשימת לקוחות לבדיקה', '#3b82f6', 'check-clients', check_rows_html, counters['check'], expanded=True)}
            </div>
        </div>
"""

    if unmatched:
        html += """
            <div class="glass-panel" style="border-left: 4px solid var(--danger-color);">
                <div class="flex-container" style="cursor: pointer;" onclick="var b = document.getElementById('res-queue-panel-body'); b.style.display = b.style.display === 'none' ? '' : 'none'; this.querySelector('.toggle-icon').innerText = b.style.display === 'none' ? '+' : '-';">
                    <h2><span class="toggle-icon" style="display:inline-block; width:25px; text-align:center;">+</span> שמות לקוחות לתייג</h2>
                    <span style="background: rgba(239, 68, 68, 0.2); color: var(--danger-color); padding: 4px 12px; border-radius: 20px; font-weight: bold;">נותרו {num} שמות לתיוג</span>
                </div>
                <div id="res-queue-panel-body" style="display: none; margin-top: 15px;">
                <table>
                    <tr>
                        <th>שם מקור (מהספרים)</th>
                        <th>שיוך ללקוח (הצעות והתאמות)</th>
                        <th>הערות / פקודות תפעוליות</th>
                        <th>סכום בהסכם / טקסט מקור</th>
                    </tr>
""".replace("{num}", str(len(unmatched)))
            
        for raw_name, data in sorted(unmatched.items()):
            agreed_val = data['agreements']
            current_note = notes.get(raw_name, "")
            
            # Smart Candidate Generation
            candidates_amount = amount_to_clients.get(agreed_val, set()) if agreed_val > 0 else set()
            # Filter out merged and deleted clients from candidate dropdowns
            active_official_clients = [c for c in official_clients if not stats.get(c, {}).get("is_merged_away") and not stats.get(c, {}).get("is_deleted")]
            candidates_fuzzy = set(difflib.get_close_matches(raw_name, active_official_clients, n=3, cutoff=0.5))
            candidates_family = set()
            
            words = raw_name.split()
            if len(words) > 1:
                last_word = words[-1]
                for oc in active_official_clients:
                    if last_word in oc:
                        candidates_family.add(oc)
                        
            all_smart_candidates = candidates_amount.union(candidates_fuzzy).union(candidates_family)
            all_smart_candidates = {oc for oc in all_smart_candidates if oc in active_official_clients}
            
            options_html = '<option value="">--- בחר התאמה ---</option>'
            options_html += '<option value="Unknown">לא ידוע (דלג כרגע)</option>'
            
            if all_smart_candidates:
                options_html += '<optgroup label="הצעות חכמות">'
                for oc in sorted(all_smart_candidates):
                    reasons = []
                    if oc in candidates_amount: reasons.append("סכום זהה")
                    if oc in candidates_fuzzy: reasons.append("דמיון בשם")
                    if oc in candidates_family: reasons.append("שם משפחה")
                    options_html += f'<option value="{oc}">{oc} ({", ".join(reasons)})</option>'
                options_html += '</optgroup>'
                
            options_html += '<optgroup label="כל הלקוחות">'
            for oc in sorted(active_official_clients):
                if oc not in all_smart_candidates:
                    options_html += f'<option value="{oc}">{oc}</option>'
            options_html += '</optgroup>'
                
            raw_text_display = "<br>".join(data['raw_text']) if data['raw_text'] else "אין טקסט מקור"
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
                            <input type="text" name="notes_{raw_name}" placeholder="הערות או פקודות תפעול..." value="{current_note}">
                        </td>
                        <td>{agreement_display}</td>
                        
                    </tr>"""
                    
        html += """
                </table>
                </div>
            </div>
"""
    else:
        html += """
            <div class="glass-panel" style="text-align: center; border-left: 4px solid var(--success-color);">
                <h2>תור התיוג ריק!</h2>
                <p style="color: var(--text-muted);">כל האירועים הגולמיים בספרים שויכו בהצלחה ללקוחות מורנינג הרשמיים.</p>
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
        elif self.path in ('/honigman-law-logo.png', '/favicon.ico'):
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../apps/webapp/frontend/public/honigman-law-logo.png'))
            if os.path.exists(logo_path):
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                with open(logo_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
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

from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run_server():
    server_address = ('', 8080)
    httpd = ThreadedHTTPServer(server_address, MappingRequestHandler)
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

