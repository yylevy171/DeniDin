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

def _match_item_entry(entry_name: str, item_type: str, item_id: str) -> bool:
    if item_type == "feature":
        return entry_name.startswith(f"{item_id}-") or entry_name == item_id
    else:
        return (
            entry_name.startswith(f"bugfix-{item_id}-")
            or entry_name == f"bugfix-{item_id}"
            or entry_name == f"bugfix_{item_id}"
            or entry_name.startswith(f"bugfix_{item_id}_")
        )

def get_item_status(item_type: str, item_id: str) -> Tuple[str, Optional[str]]:
    """Determine lifecycle status and optional release version from symlinks."""
    # 1. Check specs/done/vX.Y.Z/
    done_root = os.path.join(SPECS_DIR, "done")
    if os.path.exists(done_root):
        for ver in sorted(os.listdir(done_root)):
            if not ver.startswith("v"):
                continue
            v_path = os.path.join(done_root, ver)
            if os.path.isdir(v_path):
                for entry in os.listdir(v_path):
                    if _match_item_entry(entry, item_type, item_id):
                        return "done", ver

    # 2. Check active lifecycle folders (in-progress, backlog/bugfixes, low-priority, obsolete)
    for status in ("in-progress", "backlog", "bugfixes", "low-priority", "obsolete"):
        folder = STATUS_FOLDERS.get(status)
        if folder and os.path.exists(folder):
            for entry in os.listdir(folder):
                if _match_item_entry(entry, item_type, item_id):
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
    features = []
    bugfixes = []
    
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
                features.append({
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
            bugfixes.append({
                "type": "bugfix",
                "id": bid,
                "name": clean_name,
                "path": os.path.join(REPO_BUGFIXES, entry),
                "status": status,
                "release": release,
                "category": category
            })
            
    # Strictly sort features 001 -> 086
    features.sort(key=lambda x: (int(x["id"]) if x["id"].isdigit() else 999, x["name"]))
    # Strictly sort bugfixes 001 -> 062
    bugfixes.sort(key=lambda x: (int(x["id"]) if x["id"].isdigit() else 999, x["name"]))
    
    return features + bugfixes

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

def get_milestone_dates() -> Dict[str, Tuple[str, str]]:
    """Derive release dates (YYYY-MM-DDTHH:MM:SSZ) and associated git tag for each version.
    
    Returns: { 'vX.Y.Z': ('2026-09-12T12:00:00Z', 'denidin-app-v0.7.0') }
    """
    code, tag_out, _ = run_cmd(["git", "tag", "-l", "--format=%(refname:short)|%(creatordate:iso8601)|%(authordate:iso8601)"])
    tag_info = {}
    if code == 0 and tag_out:
        for line in tag_out.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            tag = parts[0]
            date = parts[1] or (parts[2] if len(parts) > 2 else "")
            import re
            m = re.search(r"v([0-9]+\.[0-9]+\.[0-9]+)", tag)
            if m:
                v = "v" + m.group(1)
                d_str = date.split(" ")[0] if date else ""
                if v not in tag_info or (d_str and d_str < tag_info[v][0]):
                    tag_info[v] = (d_str, tag)

    # Fallback to specs/done/vX.Y.Z git commit log if no tag exists
    done_root = os.path.join(SPECS_DIR, "done")
    final_dates = {}
    if os.path.exists(done_root):
        for v in sorted(os.listdir(done_root)):
            if not v.startswith("v"):
                continue
            if v in tag_info and tag_info[v][0]:
                d_str, tag = tag_info[v]
                final_dates[v] = (f"{d_str}T12:00:00Z", tag)
            else:
                p = os.path.join(done_root, v)
                c, out, _ = run_cmd(["git", "log", "-n", "1", "--format=%ci", "--", p])
                d_str = out.split(" ")[0] if (c == 0 and out) else "2026-09-07"
                final_dates[v] = (f"{d_str}T12:00:00Z", "")

    return final_dates

def cmd_sync_github(dry_run: bool = False):
    """Sync all local features and bugfixes to GitHub Issues & Milestones."""
    print("Syncing local specifications to GitHub Issues & Milestones...")
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
            
    # 1b. Derive milestone completion dates & tags
    milestone_dates = get_milestone_dates()
    print(f"Derived dates for {len(milestone_dates)} milestones from git tags/logs.")

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

    # 2b. Sync/backfill milestones with dates & tags
    for m_title, (due_on, rel_tag) in milestone_dates.items():
        desc = f"Release {m_title}"
        if rel_tag:
            desc += f" (Git tag: `{rel_tag}`)"
            
        m_num = existing_milestones.get(m_title)
        if not m_num:
            if not dry_run:
                c, m_out, _ = run_cmd([
                    "gh", "api", "/repos/yylevy171/DeniDin/milestones",
                    "-f", f"title={m_title}",
                    "-f", f"due_on={due_on}",
                    "-f", f"description={desc}",
                    "-f", "state=closed"
                ])
                if c == 0:
                    try:
                        m_obj = json.loads(m_out)
                        existing_milestones[m_title] = m_obj["number"]
                        print(f"+ Created GitHub Milestone {m_title} (Due: {due_on}, State: closed)")
                    except Exception:
                        pass
        else:
            if not dry_run:
                run_cmd([
                    "gh", "api", "-X", "PATCH", f"/repos/yylevy171/DeniDin/milestones/{m_num}",
                    "-f", f"due_on={due_on}",
                    "-f", f"description={desc}",
                    "-f", "state=closed"
                ])
                print(f"✓ Updated GitHub Milestone {m_title} #{m_num} (Due: {due_on}, State: closed)")

    # 3. Process each item
    for item in items:
        item_key = f"{item['type']}_{item['id']}"
        issue_number = gh_map.get(item_key)
        
        # Prepare milestone if done
        milestone_title = item.get("release")
        milestone_arg = []
        if item["status"] == "done" and milestone_title:
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
            # Check if issue already exists on remote by exact prefix search
            prefix = f"[{item['type'].upper()} {item['id']}]"
            c, out, _ = run_cmd(["gh", "issue", "list", "--search", prefix, "--state", "all", "--json", "number,title"])
            if c == 0 and out:
                try:
                    found = json.loads(out)
                    for candidate in found:
                        if candidate["title"].startswith(prefix):
                            issue_number = candidate["number"]
                            gh_map[item_key] = issue_number
                            break
                except Exception:
                    pass

        if dry_run:
            print(f"[DRY-RUN] Sync {title} (Issue: #{issue_number or 'NEW'}, Status: {item['status']})")
            continue

        if not issue_number:
            create_cmd = ["gh", "issue", "create", "--title", title, "--body", body]
            for l in labels:
                create_cmd.extend(["--label", l])
            code, out, err = run_cmd(create_cmd)
            if code == 0 and out:
                issue_num = out.strip().split("/")[-1]
                if issue_num.isdigit():
                    gh_map[item_key] = int(issue_num)
                    print(f"+ Created GitHub Issue #{issue_num} for {title}")
                    if milestone_title and milestone_title in existing_milestones:
                        m_number = existing_milestones[milestone_title]
                        run_cmd(["gh", "api", "-X", "PATCH", f"/repos/yylevy171/DeniDin/issues/{issue_num}", "-F", f"milestone={m_number}"])
                    if item["status"] in ("done", "obsolete"):
                        run_cmd(["gh", "issue", "close", issue_num])
            else:
                print(f"! Failed to create issue for {title}: {err}")
        else:
            edit_cmd = ["gh", "issue", "edit", str(issue_number), "--title", title]
            for l in labels:
                edit_cmd.extend(["--add-label", l])
            run_cmd(edit_cmd)
            if milestone_title and milestone_title in existing_milestones:
                m_number = existing_milestones[milestone_title]
                run_cmd(["gh", "api", "-X", "PATCH", f"/repos/yylevy171/DeniDin/issues/{issue_number}", "-F", f"milestone={m_number}"])
            if item["status"] in ("done", "obsolete"):
                run_cmd(["gh", "issue", "close", str(issue_number)])
            else:
                run_cmd(["gh", "issue", "reopen", str(issue_number)])
            print(f"✓ Updated GitHub Issue #{issue_number} for {title}")

    state["github_issues"] = gh_map
    save_state(state)
    print("✓ GitHub sync complete.")

def cmd_move(item_id: str, target_status: str, version: Optional[str] = None):
    """Move a feature or bugfix to a new lifecycle status folder and sync registries.
    
    Target statuses:
      - backlog: maps to specs/backlog/ (for features) or specs/bugfixes/ (for bugfixes)
      - bugfixes: maps to specs/bugfixes/ (explicitly for bugfixes)
      - in-progress: maps to specs/in-progress/
      - done: maps to specs/done/vX.Y.Z/ (requires --version) or flat specs/done/
      - low-priority: maps to specs/low-priority/
      - obsolete: maps to specs/obsolete/
    """
    items = collect_all_items()
    # Find matching item by ID or name
    matched = None
    for item in items:
        if item["id"] == item_id or item["id"] == item_id.zfill(3) or item["name"] == item_id:
            matched = item
            break
            
    if not matched:
        print(f"Error: Could not find feature or bugfix matching '{item_id}' in specs/repo/.")
        sys.exit(1)

    item_type = matched["type"]
    item_name = matched["name"]
    clean_id = matched["id"]
    current_status = matched["status"]
    current_release = matched["release"]

    # Normalize target status
    target_status = target_status.lower()
    if target_status == "backlog" and item_type == "bugfix":
        target_folder_key = "bugfixes"
    elif target_status in STATUS_FOLDERS:
        target_folder_key = target_status
    else:
        valid_destinations = list(STATUS_FOLDERS.keys())
        print(f"Error: Invalid target status '{target_status}'. Must be one of: {valid_destinations}")
        sys.exit(1)

    # Calculate target directory and symlink path
    if target_folder_key == "done":
        if version:
            v_tag = version if version.startswith("v") else f"v{version}"
            dest_dir = os.path.join(SPECS_DIR, "done", v_tag)
            rel_target = f"../../repo/{'features' if item_type == 'feature' else 'bugfixes'}/{item_name}{'.md' if item_type == 'bugfix' else ''}"
        else:
            dest_dir = os.path.join(SPECS_DIR, "done")
            rel_target = f"../repo/{'features' if item_type == 'feature' else 'bugfixes'}/{item_name}{'.md' if item_type == 'bugfix' else ''}"
    else:
        dest_dir = STATUS_FOLDERS[target_folder_key]
        rel_target = f"../repo/{'features' if item_type == 'feature' else 'bugfixes'}/{item_name}{'.md' if item_type == 'bugfix' else ''}"

    os.makedirs(dest_dir, exist_ok=True)
    symlink_name = f"{item_name}.md" if item_type == "bugfix" else item_name
    dest_symlink = os.path.join(dest_dir, symlink_name)

    # 1. Remove existing symlinks across all status folders
    removed_from = []
    # Check done subdirectories
    done_root = os.path.join(SPECS_DIR, "done")
    if os.path.exists(done_root):
        for root, dirs, files in os.walk(done_root):
            for entry in dirs + files:
                if _match_item_entry(entry, item_type, clean_id):
                    full_p = os.path.join(root, entry)
                    if os.path.islink(full_p) or os.path.isfile(full_p):
                        try:
                            os.remove(full_p)
                            removed_from.append(os.path.relpath(full_p, REPO_ROOT))
                        except Exception as e:
                            print(f"! Failed to remove old link {full_p}: {e}")

    # Check other status folders
    for s_key, s_dir in STATUS_FOLDERS.items():
        if s_key == "done" or not os.path.exists(s_dir):
            continue
        for entry in os.listdir(s_dir):
            if _match_item_entry(entry, item_type, clean_id):
                full_p = os.path.join(s_dir, entry)
                if os.path.islink(full_p) or os.path.isfile(full_p):
                    try:
                        os.remove(full_p)
                        removed_from.append(os.path.relpath(full_p, REPO_ROOT))
                    except Exception as e:
                        print(f"! Failed to remove old link {full_p}: {e}")

    # 2. Create new relative symlink
    if os.path.lexists(dest_symlink):
        os.remove(dest_symlink)
    os.symlink(rel_target, dest_symlink)
    print(f"✓ Moved {item_type.upper()} {clean_id} ('{item_name}') from [{current_status}] -> [{target_status}]")
    if removed_from:
        print(f"  - Removed old link(s): {', '.join(removed_from)}")
    print(f"  - Created link: {os.path.relpath(dest_symlink, REPO_ROOT)} -> {rel_target}")

    # 3. Synchronize product registries
    cmd_sync_product_files()
    print(f"✓ Synchronized product category registries (CAPABILITIES.md, etc.)")

    # 4. Sync to GitHub Issues
    print(f"Syncing state change to GitHub Issues...")
    cmd_sync_github()

def main():
    parser = argparse.ArgumentParser(description="DeniDin Specification & Roadmap Tracker")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("sync", help="Synchronize product registry markdown files")
    subparsers.add_parser("board", help="Display ASCII Kanban board")
    
    gh_parser = subparsers.add_parser("sync-github", help="Synchronize local specs to GitHub Issues")
    gh_parser.add_argument("--dry-run", action="store_true", help="Preview GitHub changes without executing")
    
    move_parser = subparsers.add_parser("move", help="Move a feature or bugfix to a new lifecycle status")
    move_parser.add_argument("id", help="Feature or bugfix ID (e.g. 051, 063, 087, bugfix-064)")
    move_parser.add_argument("status", help="Target status: backlog, bugfixes, in-progress, done, low-priority, obsolete")
    move_parser.add_argument("--version", help="Release version if moving to done (e.g. 0.7.5 or v0.7.5)")

    args = parser.parse_args()
    if args.command == "sync":
        cmd_sync_product_files()
    elif args.command == "board":
        cmd_board()
    elif args.command == "sync-github":
        cmd_sync_github(dry_run=args.dry_run)
    elif args.command == "move":
        cmd_move(item_id=args.id, target_status=args.status, version=args.version)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
