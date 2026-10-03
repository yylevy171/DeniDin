import os
import glob
import subprocess

# 1. Rename 086 README to spec.md
f086_dir = "specs/repo/features/086-combo-doc-closing-multiple-300-accounts"
if os.path.exists(f"{f086_dir}/README.md"):
    os.rename(f"{f086_dir}/README.md", f"{f086_dir}/spec.md")

# 2. Find and link orphans
repo_features = glob.glob("specs/repo/features/*")
repo_bugfixes = glob.glob("specs/repo/bugfixes/*.md")

status_dirs = ["specs/backlog", "specs/bugfixes", "specs/in-progress", "specs/low-priority", "specs/obsolete"]
status_dirs.extend(glob.glob("specs/done/*"))

linked_items = set()
for d in status_dirs:
    if os.path.isdir(d):
        linked_items.update([os.path.basename(p).replace('.md', '') for p in glob.glob(f"{d}/*")])

# Also link 072 to backlog
subprocess.run(["python3", "scripts/spec_tracker.py", "move", "072", "backlog"])

# Re-read linked items after 072 move
linked_items = set()
for d in status_dirs:
    if os.path.isdir(d):
        linked_items.update([os.path.basename(p).replace('.md', '') for p in glob.glob(f"{d}/*")])

for f in repo_features:
    basename = os.path.basename(f)
    if basename not in linked_items:
        target = f"../repo/features/{basename}"
        link_name = f"specs/backlog/{basename}"
        if not os.path.exists(link_name):
            os.symlink(target, link_name)
            print(f"Linked feature {basename} to backlog")

for b in repo_bugfixes:
    basename = os.path.basename(b).replace('.md', '')
    if basename not in linked_items:
        target = f"../repo/bugfixes/{basename}.md"
        link_name = f"specs/bugfixes/{basename}"
        if not os.path.exists(link_name):
            os.symlink(target, link_name)
            print(f"Linked bugfix {basename} to bugfixes")
