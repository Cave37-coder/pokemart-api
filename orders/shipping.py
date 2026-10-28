"""
shipping.py -- parcel size and what we charge for it (2026-10-28).

Michael: "we need to build in the correct Pudo size to the order sheet, so we keep the R16 difference, it
pays for packaging materials! Customer must NOT decide, we do!"

* Parcel size is decided by us from the number of cards: 1-600 cards = Extra Small, then one size up for
  every further 600 (Small, Medium, Large, Extra Large).
* What the customer pays = the standard delivery price for the method they picked (the old fixed prices,
  R75 locker / R85 kiosk / R95 medium-tins / R105 door) PLUS the extra Pudo charges us for the bigger
  parcel. Pudo's L2L rates (2026-10-28): XS R59, S R69, M R79, L R109, XL R149 -- so the extras over XS are
  0 / 10 / 20 / 50 / 90 and our R16 packaging margin stays the same at every size.
* The price is worked out HERE (server side); the checkout page just displays it. Update SIZE_EXTRA if
  Pudo's prices change (pudo_check --to <locker> prints the current ones).
"""
import os
from decimal import Decimal

SIZE_NAMES = ['Extra Small', 'Small', 'Medium', 'Large', 'Extra Large']
SIZE_SHORT = ['XS', 'S', 'M', 'L', 'XL']
SIZE_CODES = ['L2LXS - ECO', 'L2LS - ECO', 'L2LM - ECO', 'L2LL - ECO', 'L2LXL - ECO']
SIZE_EXTRA = [Decimal('0'), Decimal('10'), Decimal('20'), Decimal('50'), Decimal('90')]

BASE_PRICE = {
    'collection': Decimal('0'),
    'pudo_locker': Decimal('75'),
    'pudo_kiosk': Decimal('85'),
    'pudo_medium': Decimal('95'),   # tins: already priced at Medium size
    'pudo_door': Decimal('105'),
}
MEDIUM_TIER = 2


def cards_per_size():
    try:
        return max(1, int(os.environ.get('PUDO_CARDS_PER_SIZE', '600')))
    except ValueError:
        return 600


def max_cards():
    return cards_per_size() * len(SIZE_NAMES)


def tier_for(n_cards, method=''):
    """Size tier 0..4 for a number of cards (tins / 'pudo_medium' are never smaller than Medium)."""
    per = cards_per_size()
    n = max(0, int(n_cards or 0))
    tier = min(len(SIZE_NAMES) - 1, max(0, (n - 1) // per)) if n else 0
    if method == 'pudo_medium':
        tier = max(tier, MEDIUM_TIER)
    return tier


def shipping_price(method, n_cards):
    """What the customer is charged for delivery by `method` for an order of n_cards cards."""
    if method not in BASE_PRICE:
        return Decimal('0')
    base = BASE_PRICE[method]
    if method == 'collection':
        return base
    tier = tier_for(n_cards, method)
    floor = MEDIUM_TIER if method == 'pudo_medium' else 0
    return base + SIZE_EXTRA[tier] - SIZE_EXTRA[floor]


def quote(n_cards):
    """Everything the checkout needs for a cart of n_cards cards."""
    tier = tier_for(n_cards)
    per = cards_per_size()
    return {
        'cards': int(n_cards or 0),
        'size': SIZE_NAMES[tier],
        'size_short': SIZE_SHORT[tier],
        'up_to_cards': per * (tier + 1),
        'prices': {m: str(shipping_price(m, n_cards)) for m in BASE_PRICE},
    }


def parcel_label(n_cards, method=''):
    """e.g. 'Extra Small (L2LXS)' for the pull sheet / staff views; '' for collection."""
    if method == 'collection':
        return ''
    tier = tier_for(n_cards, method)
    return f"{SIZE_NAMES[tier]} ({SIZE_CODES[tier].split(' ')[0]})"
