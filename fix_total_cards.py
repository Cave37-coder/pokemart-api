import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import CardSet
from django.db.models import Count

# 2026-11-03: this used to overwrite EVERY set's total_cards with its product-row count (variants included),
# which silently changed every checklist card number ("001/154" -> "001/170"), reset all My Sets progress and
# broke the 30C Pikachu sub-set. total_cards is the PRINTED set total and must never be recalculated from
# the catalog. Now it only fills sets whose total_cards is still 0 (brand-new sets), and only with --apply.
# For a new set, prefer setting the printed total by hand (e.g. DLR = 103).
import sys

APPLY = '--apply' in sys.argv
sets = CardSet.objects.annotate(pc=Count('products')).filter(total_cards=0).all()
updated = 0
for s in sets:
    print(f'{s.code}: total_cards is 0 -> would use product-row count {s.pc} (printed total is usually lower; set it by hand)')
    if APPLY and s.pc:
        s.total_cards = s.pc
        s.save(update_fields=['total_cards'])
        updated += 1
print(f'Done. Updated {updated} sets.' if APPLY else 'Dry run only (add --apply). Sets with a non-zero total are never touched.')
