import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Sum, Count, Q
from products.models import PokemonProduct, CardSet

# Michael: "I just went into the site and had a look at the Trainer Gallery
# section! It's a disaster!!!!" -- turned out every TG card shows as grayscale
# "Out of Stock" on pokebulk.co.za. Confirmed via screenshots the images
# themselves ARE correct (right card each time, matches pkmn.gg reference),
# and Michael confirmed every TG card specifically is Out of Stock -- so this
# is the site's normal OOS styling, not an image bug.
#
# `stock` (live/purchasable) is separate from `pos_stock` (physical POS
# inventory) per models.py -- pos_stock never auto-flows into stock, moving
# it over is a deliberate manual step. This script checks whether TG products
# have real pos_stock sitting there un-migrated (a listing task, not a bug)
# vs. both fields genuinely being zero (no physical inventory to list) vs.
# every OTHER set also being broken the same way (a real sitewide bug).

TG_CODES = ['BRSTG', 'ASRTG', 'LORTG', 'SITTG', 'CRZGG']
# A few non-TG sets as a sanity-check control group
CONTROL_CODES = ['BRS', 'ASR', 'LOR', 'SIT', 'CRZ']

def report(codes, label):
    print(f"=== {label} ===")
    for code in codes:
        try:
            cs = CardSet.objects.get(code=code)
        except CardSet.DoesNotExist:
            print(f"  {code}: no such CardSet")
            continue
        qs = PokemonProduct.objects.filter(card_set=cs, is_active=True)
        total = qs.count()
        agg = qs.aggregate(
            total_stock=Sum('stock'),
            total_pos_stock=Sum('pos_stock'),
            in_stock_count=Count('id', filter=Q(stock__gt=0)),
            has_pos_stock_count=Count('id', filter=Q(pos_stock__gt=0)),
        )
        print(f"  {code:8} ({cs.name[:30]:30}) {total:4} products | "
              f"stock>0: {agg['in_stock_count']:4} (sum={agg['total_stock'] or 0:5}) | "
              f"pos_stock>0: {agg['has_pos_stock_count']:4} (sum={agg['total_pos_stock'] or 0:5})")
    print()

report(TG_CODES, "Trainer Gallery subsets")
report(CONTROL_CODES, "Parent sets (control group)")
