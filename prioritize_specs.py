import os, glob, subprocess

def move_spec(spec_id, target, version=None):
    cmd = ["python3", "scripts/spec_tracker.py", "move", spec_id, target]
    if version:
        cmd.extend(["--version", version])
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

# Features
for f in ["055", "060", "077", "079", "081", "082"]:
    move_spec(f, "low-priority")

# 051 should already be obsolete, but just in case
move_spec("051", "obsolete")

# Bugfixes (try using full name or ID)
bugfixes = glob.glob("specs/repo/bugfixes/*.md")

def find_bugfix(bid):
    for b in bugfixes:
        if f"bugfix-{bid}" in os.path.basename(b):
            return os.path.basename(b).replace('.md', '')
    return None

for bid in ["033", "042", "049", "050", "051", "053", "055"]:
    bname = find_bugfix(bid)
    if bname:
        move_spec(bname, "obsolete")
    else:
        print(f"Could not find bugfix-{bid}")

# Move 061 to done
bname_061 = find_bugfix("061")
if bname_061:
    move_spec(bname_061, "done", "0.7.8")

# Remove small-bugfixes
try:
    os.remove("specs/repo/bugfixes/small-bugfixes-027-032-054-058-061-tests-to-run.md")
except:
    pass
try:
    os.remove("specs/bugfixes/small-bugfixes-027-032-054-058-061-tests-to-run.md")
except:
    pass
