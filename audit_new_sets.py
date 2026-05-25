"""
Audit all newly added sets — query DB directly
Run: python manage.py shell --command="exec(open('audit_new_sets.py').read())"
"""
from products.models import PokemonProduct, CardSet

NEW_SETS = [
    'ASRTG', 'BST', 'CRZGG', 'DEP', 'DRV', 'GENRC', 'HIFSV', 'KSS',
    'LORTG', 'LTRRC', 'MCD11', 'MCD12', 'MCD14', 'MCD15', 'MCD16',
    'MCD17', 'MCD18', 'MCD19', 'MCD21', 'MCD22', 'MCD23', 'MCD24',
    'MEE', 'MEP', 'POP1', 'POP2', 'POP3', 'POP4', 'POP5', 'POP6',
    'POP7', 'POP8', 'POP9', 'PR-BEST', 'PR-BLW', 'PR-DP', 'PR-HS',
    'PR-NB', 'PR-SM', 'PR-SWSH', 'PR-WB', 'PR-XY', 'PRIZEPACK',
    'RUM', 'SHFSV', 'SI1', 'ST', 'SVE', 'SW', 'TCGCL',
    'TOT22', 'TOT23', 'TOT24', 'TRR',
]

print(f"{'Set':<12} {'DB records':>10} {'CardSet':>8}  Status")
print("-"*45)

missing = []
empty = []
ok = []

for code in sorted(NEW_SETS):
    try:
        card_set = CardSet.objects.get(code=code)
        set_exists = True
        db_count = PokemonProduct.objects.filter(card_set=card_set).count()
    except CardSet.DoesNotExist:
        set_exists = False
        db_count = 0

    if not set_exists:
        status = "MISSING CARDSET"
        missing.append(code)
    elif db_count == 0:
        status = "NO PRODUCTS"
        empty.append(code)
    else:
        status = "OK"
        ok.append(code)

    print(f"{code:<12} {db_count:>10} {str(set_exists):>8}  {status}")

print(f"\nOK: {len(ok)} | Empty: {len(empty)} | Missing: {len(missing)}")
if empty:
    print(f"Still empty: {empty}")
if missing:
    print(f"Missing CardSet: {missing}")
