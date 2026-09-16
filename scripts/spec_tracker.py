#!/usr/bin/env python3
"""
spec_tracker.py — Unified Local & GitHub Spec Management Engine.

Single source of truth:
  - specs/repo/features/
  - specs/repo/bugfixes/

Lifecycle symlink folders:
  - specs/backlog/ (features waiting for dev)
  - specs/bugfixes/ (bugfixes waiting for dev)
  - specs/in-progress/ (features/bugfixes being coded)
  - specs/done/vX.Y.Z/ (features/bugfixes shipped in release vX.Y.Z)
  - specs/low-priority/ (deprioritized features/bugfixes)
  - specs/obsolete/ (discarded or superseded items)

Product category registries:
  - product/CAPABILITIES.md
  - product/TESTING.md
  - product/OPERATIONS.md
  - product/HYGIENE.md
"""

import os
import sys
import glob
import json
import argparse
import subprocess
from typing import Dict, List, Optional, Tuple, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPECS_DIR = os.path.join(REPO_ROOT, "specs")
REPO_FEATURES = os.path.join(SPECS_DIR, "repo", "features")
REPO_BUGFIXES = os.path.join(SPECS_DIR, "repo", "bugfixes")
PRODUCT_DIR = os.path.join(REPO_ROOT, "product")

STATUS_FOLDERS = {
    "backlog": os.path.join(SPECS_DIR, "backlog"),
    "bugfixes": os.path.join(SPECS_DIR, "bugfixes"),
    "in-progress": os.path.join(SPECS_DIR, "in-progress"),
    "low-priority": os.path.join(SPECS_DIR, "low-priority"),
    "obsolete": os.path.join(SPECS_DIR, "obsolete"),
    "done": os.path.join(SPECS_DIR, "done"),
}

CATEGORIES = {
    "capability": ("CAPABILITIES.md", "Product Capabilities", "Customer-facing functional features, conversational intelligence, and business capabilities."),
    "testing": ("TESTING.md", "Testing & Quality Assurance", "Test framework architecture, runners, test split strategies, and sanity verification suites."),
    "operations": ("OPERATIONS.md", "Operations & Production Infrastructure", "Production hosting, containerization, deployments, backups, data migrations, and runtime reliability."),
    "hygiene": ("HYGIENE.md", "Code & System Hygiene", "Architectural refactoring, prompt/constitution optimizations, code health, and dependency upgrades.")
}

STATE_FILE = os.path.join(REPO_ROOT, ".agents", "state", "spec_tracker_state.json")

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: Dict[str, Any]):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_item_status(item_type: str, item_id: str) -> Tuple[str, Optional[str]]:
    """Determine lifecycle status and optional release version from symlinks."""
    for done_file in glob.glob(os.path.join(SPECS_DIR, "done", "**", f"*{item_id}*"), recursive=True):
        rel = os.path.relpath(done_file, os.path.join(SPECS_DIR, "done"))
        parts = rel.split(os.sep)
        if len(parts) > 1 and parts[0].startswith("v"):
            return "done", parts[0]
        return "done", None
    
    for status, folder in STATUS_FOLDERS.items():
        if status == "done":
            continue
        for entry in glob.glob(os.path.join(folder, f"*{item_id}*")):
            return status, None
            
    return "repo", None

def get_category_for_item(item_type: str, item_id: str) -> str:
    """Read existing classification from product/ markdown registries or default to capability."""
    for cat, (filename, _, _) in CATEGORIES.items():
        filepath = os.path.join(PRODUCT_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read()
                if f"**{item_id}**:" in content:
                    return cat
    return "capability"

def collect_all_items() -> List[Dict[str, Any]]:
    items = []
    
    # Features
    if os.path.exists(REPO_FEATURES):
        for entry in sorted(os.listdir(REPO_FEATURES)):
            if entry.startswith("."):
                continue
            path = os.path.join(REPO_FEATURES, entry)
            if os.path.isdir(path):
                fid = entry.split("-")[0]
                status, release = get_item_status("feature", fid)
                category = get_category_for_item("feature", fid)
                items.append({
                    "type": "feature",
                    "id": fid,
                    "name": entry,
                    "path": path,
                    "status": status,
                    "release": release,
                    "category": category
                })
                
    # Bugfixes
    if os.path.exists(REPO_BUGFIXES):
        for entry in sorted(os.listdir(REPO_BUGFIXES)):
            if entry.startswith(".") or not (entry.startswith("bugfix-") or entry.startswith("bugfix_")):
                continue
            clean_name = entry.replace(".md", "")
            parts = clean_name.split("-")
            bid = parts[1] if len(parts) > 1 else clean_name
            status, release = get_item_status("bugfix", bid)
            category = get_category_for_item("bugfix", bid)
            items.append({
                "type": "bugfix",
                "id": bid,
                "name": clean_name,
                "path": os.path.join(REPO_BUGFIXES, entry),
                "status": status,
                "release": release,
                "category": category
            })
            
    return items

def cmd_sync_product_files():
    """Regenerate CAPABILITIES.md, TESTING.md, OPERATIONS.md, HYGIENE.md."""
    items = collect_all_items()
    os.makedirs(PRODUCT_DIR, exist_ok=True)
    
    for cat, (filename, title, desc) in CATEGORIES.items():
        cat_feats = [i for i in items if i["type"] == "feature" and i["category"] == cat]
        cat_bugs = [i for i in items if i["type"] == "bugfix" and i["category"] == cat]
        
        # Sort recent first (numerically descending by id)
        cat_feats.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
        cat_bugs.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
        
        filepath = os.path.join(PRODUCT_DIR, filename)
        with open(filepath, "w") as f:
            f.write(f"# {title}\n\n{desc}\n*Sorted recent first.*\n\n## Features\n\n")
            if cat_feats:
                for i in cat_feats:
                    stat_str = f"Done ({i['release']})" if i["status"] == "done" and i["release"] else i["status"].capitalize()
                    f.write(f"- **{i['id']}**: `{i['name']}` — Status: {stat_str}\n")
            else:
                f.write("*No features in this category.*\n")
                
            f.write("\n## Bugfixes\n\n")
            if cat_bugs:
                for b in cat_bugs:
                    stat_str = f"Done ({b['release']})" if b["status"] == "done" and b["release"] else b["status"].capitalize()
                    f.write(f"- **{b['id']}**: `{b['name']}` — Status: {stat_str}\n")
            else:
                f.write("*No bugfixes in this category.*\n")
                
    print("✓ Successfully synchronized product/ registry files.")

def cmd_board():
    """Display an interactive terminal ASCII Kanban board."""
    items = collect_all_items()
    
    backlog = [i for i in items if i["status"] in ("backlog", "bugfixes")]
    in_progress = [i for i in items if i["status"] == "in-progress"]
    done = [i for i in items if i["status"] == "done"]
    
    print("\n" + "=" * 80)
    print(f"{'DENIDIN PM ROADMAP & KANBAN BOARD':^80}")
    print("=" * 80)
    print(f"| {'BACKLOG (' + str(len(backlog)) + ')':<24} | {'IN-PROGRESS (' + str(len(in_progress)) + ')':<24} | {'RECENT DONE (' + str(len(done)) + ')':<24} |")
    print("-" * 80)
    
    max_len = max(len(backlog), len(in_progress), min(len(done), 10))
    for idx in range(max_len):
        col1 = f"[{backlog[idx]['id']}] {backlog[idx]['name'][:16]}" if idx < len(backlog) else ""
        col2 = f"[{in_progress[idx]['id']}] {in_progress[idx]['name'][:16]}" if idx < len(in_progress) else ""
        col3 = f"[{done[idx]['id']}] {done[idx]['name'][:14]} ({done[idx]['release'] or 'done'})" if idx < len(done) else ""
        print(f"| {col1:<24} | {col2:<24} | {col3:<24} |")
    print("=" * 80 + "\n")

def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def cmd_sync_github(dry_run: bool = False):
    """Sync all local features and bugfixes to GitHub Issues & Milestones."""
    print("Syncing local specifications to GitHub Issues...")
    items = collect_all_items()
    state = load_state()
    gh_map = state.get("github_issues", {})
    
    # 1. Fetch existing GitHub milestones
    code, out, _ = run_cmd(["gh", "api", "/repos/yylevy171/DeniDin/milestones?state=all"])
    existing_milestones = {}
    if code == 0 and out:
        try:
            m_list = json.loads(out)
            for m in m_list:
                existing_milestones[m["title"]] = m["number"]
        except Exception:
            pass
            
    # 2. Ensure labels exist
    required_labels = [
        ("type:feature", "a2eeef", "Feature specification"),
        ("type:bugfix", "d73a4a", "Bugfix specification"),
        ("cat:capability", "7057ff", "Customer-facing capabilities"),
        ("cat:testing", "0e8a16", "Testing and QA"),
        ("cat:operations", "fbca04", "Production and infrastructure"),
        ("cat:hygiene", "0075ca", "Code and system hygiene"),
        ("status:backlog", "fef2c0", "Awaiting development"),
        ("status:in-progress", "1d76db", "Actively in development"),
        ("status:low-priority", "e4e669", "Deprioritized backlog item"),
        ("status:obsolete", "cfd3d7", "Obsolete or superseded"),
    ]
    
    for label, color, desc in required_labels:
        run_cmd(["gh", "label", "create", label, "--color", color, "--description", desc, "--force"])
        
    # 3. Process each item
    for item in items:
        item_key = f"{item['type']}_{item['id']}"
        issue_number = gh_map.get(item_key)
        
        # Prepare milestone if done
        milestone_title = item.get("release")
        milestone_arg = []
        if item["status"] == "done" and milestone_title:
            if milestone_title not in existing_milestones:
                c, m_out, _ = run_cmd(["gh", "api", "/repos/yylevy171/DeniDin/milestones", "-f", f"title={milestone_title}"])
                if c == 0:
                    try:
                        m_obj = json.loads(m_out)
                        existing_milestones[milestone_title] = m_obj["number"]
                    except Exception:
                        pass
            if milestone_title in existing_milestones:
                milestone_arg = ["--milestone", milestone_title]

        labels = [f"type:{item['type']}", f"cat:{item['category']}"]
        if item["status"] in ("backlog", "bugfixes"):
            labels.append("status:backlog")
        elif item["status"] == "in-progress":
            labels.append("status:in-progress")
        elif item["status"] == "low-priority":
            labels.append("status:low-priority")
        elif item["status"] == "obsolete":
            labels.append("status:obsolete")

        title = f"[{item['type'].upper()} {item['id']}] {item['name']}"
        body = f"Source specification: `{os.path.relpath(item['path'], REPO_ROOT)}`\n\nLifecycle Status: **{item['status']}**\nCategory: **{item['category']}**"
        
        # Read spec excerpt if available
        spec_file = item["path"] if os.path.isfile(item["path"]) else os.path.join(item["path"], "spec.md")
        if os.path.exists(spec_file):
            try:
                with open(spec_file, "r") as sf:
                    body += "\n\n---\n" + sf.read()[:1500] + "\n\n*(Full spec on disk)*"
            except Exception:
                pass
                
        if not issue_number:
            # Check if issue already exists on remote by title
            c, out, _ = run_cmd(["gh", "issue", "list", "--search", f"[{item['type'].upper()} {item['id']}]", "--state", "all", "--json", "number"])
            if c == 0 and out:
                try:
                    found = json.loads(out)
                    if found:
                        issue_number = found[0]["number"]
                        gh_map[item_key] = issue_number
                except Exception:
                    pass

        if dry_run:
            print(f"[DRY-RUN] Sync {title} (Issue: #{issue_number or 'NEW'}, Status: {item['status']})")
            continue

        if not issue_number:
            create_cmd = ["gh", "issue", "create", "--title", title, "--body", body]
            for l in labels:
                create_cmd.extend(["--label", l])
            if milestone_arg:
                create_cmd.extend(milestone_arg)
            code, out, err = run_cmd(create_cmd)
            if code == 0 and out:
                # out is url e.g. https://github.com/.../issues/123
                issue_num = out.strip().split("/")[-1]
                if issue_num.isdigit():
                    gh_map[item_key] = int(issue_num)
                    print(f"+ Created GitHub Issue #{issue_num} for {title}")
                    if item["status"] in ("done", "obsolete"):
                        run_cmd(["gh", "issue", "close", issue_num])
            else:
                print(f"! Failed to create issue for {title}: {err}")
        else:
            edit_cmd = ["gh", "issue", "edit", str(issue_number), "--title", title]
            for l in labels:
                edit_cmd.extend(["--add-label", l])
            if milestone_arg:
                edit_cmd.extend(milestone_arg)
            run_cmd(edit_cmd)
            if item["status"] in ("done", "obsolete"):
                run_cmd(["gh", "issue", "close", str(issue_number)])
            else:
                run_cmd(["gh", "issue", "reopen", str(issue_number)])
            print(f"✓ Updated GitHub Issue #{issue_number} for {title}")

    state["github_issues"] = gh_map
    save_state(state)
    print("✓ GitHub sync complete.")

def main():
    parser = argparse.ArgumentParser(description="DeniDin Specification & Roadmap Tracker")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("sync", help="Synchronize product registry markdown files")
    subparsers.add_parser("board", help="Display ASCII Kanban board")
    
    gh_parser = subparsers.add_parser("sync-github", help="Synchronize local specs to GitHub Issues")
    gh_parser.add_argument("--dry-run", action="store_true", help="Preview GitHub changes without executing")
    
    args = parser.parse_args()
    if args.command == "sync":
        cmd_sync_product_files()
    elif args.command == "board":
        cmd_board()
    elif args.command == "sync-github":
        cmd_sync_github(dry_run=args.dry_run)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
