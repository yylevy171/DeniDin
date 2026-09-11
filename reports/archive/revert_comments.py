import json

with open("reports/client_comments.json", "r", encoding="utf-8") as f:
    comments = json.load(f)

for c, text in list(comments.items()):
    lines = text.split("\n")
    new_lines = [l for l in lines if "מתוך צ'אט" not in l and "שכר טרחה מקובץ word" not in l]
    if new_lines:
        comments[c] = "\n".join(new_lines)
    else:
        del comments[c]

with open("reports/client_comments.json", "w", encoding="utf-8") as f:
    json.dump(comments, f, ensure_ascii=False, indent=4)
print("Reverted comments.")
