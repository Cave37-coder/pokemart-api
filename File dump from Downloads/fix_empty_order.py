with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "sets_empty      = [s for s in all_sets if s.card_count == 0]",
    "sets_empty      = sorted([s for s in all_sets if s.card_count == 0], key=lambda s: s.release_date or '1900-01-01', reverse=True)"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
