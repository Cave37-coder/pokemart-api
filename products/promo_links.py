"""
promo_links.py -- promo cards that belong to a main set's checklist (2026-11-05).

Michael: promos (Prerelease / Staff / ETB / Pokemon Center / stamped ...) must show on the checklist of the set
they belong to. A promo lives in its own promo set (SVP, MEP, SMP, PR-XY ...); linking it to a main set just adds
that set to the product's `also_in_sets` (the same mechanism shared Energy cards use). On the linked set's
checklist the promo shows as its own extra card numbered "PR-<promo number>", so it sorts after the numbered run
and only counts in the Full Master / Complete tier. generate_checklist_data.py and completion.py BOTH use
promo_display_num() so a customer's ticks and their progress always agree.
"""

PROMO_HOME_PREFIXES = ('PR-', 'SVP', 'MEP', 'SMP', 'SWSHP', 'XYP', 'BWP', 'DPP', 'HSP')


def is_promo_home(set_code):
    return bool(set_code) and str(set_code).startswith(PROMO_HOME_PREFIXES)


def promo_display_num(raw_number, card_number):
    """Key for a linked promo on its parent set's checklist."""
    base = (raw_number or '').strip() or (str(card_number).zfill(3) if card_number is not None else '')
    return f"PR-{base}"
