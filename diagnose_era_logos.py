"""
diagnose_era_logos.py

Read-only: compares every Era row's exact `name` (and whatever logo_url is
currently set) against the era label strings the CHECKLIST FRONTEND
actually uses to look logos up by. The frontend does an exact string match
(eraLogos[label]), so if a DB Era.name doesn't character-for-character
match one of these labels, its logo will never show up even with a
perfectly valid logo_url saved -- it'll silently keep showing the old
text-pill fallback instead.

Usage:
    python manage.py shell -c "exec(open('diagnose_era_logos.py').read())"
"""

from products.models import Era

# Exact strings the frontend's ERA_ORDER / era labels use (checklists/page.tsx)
FRONTEND_ERA_LABELS = {
    "WotC Base", "WotC Neo", "WotC Legendary", "WotC Other",
    "EX Era", "Diamond & Pearl", "HG&SS", "Black & White", "XY Era",
    "Sun & Moon", "Sword & Shield", "Scarlet & Violet", "Mega Evolution",
    "Special - Prize Pack", "Special - Trick or Trade",
}

print("=" * 70)
print("Every Era row: name, logo_url, and whether the frontend can match it")
print("=" * 70)
eras = Era.objects.all().order_by("name")
for e in eras:
    has_logo = bool(e.logo_url)
    matches = e.name in FRONTEND_ERA_LABELS
    flag = ""
    if has_logo and not matches:
        flag = "  <-- LOGO SET BUT NAME DOESN'T MATCH THE FRONTEND LABEL -- won't show!"
    elif has_logo and matches:
        flag = "  (should be showing)"
    print(f"  code={e.code:<8} name={e.name!r:<28} logo_url={'SET' if has_logo else '(blank)':<6}{flag}")

print()
print("=" * 70)
print("Frontend labels with NO matching Era row at all (can never get a logo)")
print("=" * 70)
db_names = set(eras.values_list("name", flat=True))
for label in sorted(FRONTEND_ERA_LABELS):
    if label not in db_names and not label.startswith("Special - "):
        print(f"  {label!r} -- no Era row in the database has this exact name")
