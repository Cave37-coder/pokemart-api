"""
Computes PokemonProduct.legal_standard for the whole catalog, per the
official Pokemon TCG rules:

  - Pokemon cards: legal only if their OWN printing's CardSet.regulation_mark
    is currently legal. A reprint with a legal mark does NOT make an older
    printing of that same Pokemon legal — there is no pass-through for
    Pokemon cards.

  - Special (non-Basic) Energy cards: same strict per-print rule as Pokemon.

  - Basic Energy cards: always legal, regardless of regulation mark.

  - Trainer cards (Item / Supporter / Stadium / Tool): if ANY printing
    sharing the same base card name has a currently-legal regulation mark,
    then EVERY printing of that card becomes legal, regardless of that
    specific printing's own mark (including printings with no mark at all).
    This is the official Trainer "reprint pass-through" rule.

CONFIGURATION:
  ROTATED_OUT_REGULATION_MARKS below must be updated after each Standard
  rotation (typically each spring) by adding the newly-rotated-out letter.
  Everything NOT in this set is treated as currently legal, so newly
  released marks (e.g. K, L...) need no code change — only retiring a mark
  does.

Usage:
    python manage.py compute_standard_legality            # apply for real
    python manage.py compute_standard_legality --dry-run   # preview only
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import PokemonProduct

# Update this set after each Standard rotation. As of June 2026, marks A-G
# are rotated out; H, I, J are the current legal window.
ROTATED_OUT_REGULATION_MARKS = {'A', 'B', 'C', 'D', 'E', 'F', 'G'}

# Strip everything from the first "[" or the first " - " onward to get the
# true card name for cross-set Trainer reprint matching (set/number/variant
# disambiguation suffixes only, confirmed safe by Michael 2026-06-20 —
# e.g. "Boss's Orders [Corbeau] - 183/217" -> "Boss's Orders").
# Strip everything from the first "[", "(", or " - " onward to get the true
# card name for cross-set Trainer reprint matching (set/number/variant
# disambiguation suffixes only -- confirmed safe by Michael 2026-06-20,
# including parenthetical variants like "(Poke Ball Pattern)", "(Secret)",
# "(Cosmos Holo)" -- e.g. "Boss's Orders [Corbeau] - 183/217" ->
# "Boss's Orders", "Professor's Research (Poke Ball Pattern)" ->
# "Professor's Research").
_NAME_SUFFIX_RE = re.compile(r'\s*(\[|\(|-\s)')


def clean_base_name(name):
    match = _NAME_SUFFIX_RE.search(name)
    if match:
        return name[:match.start()].strip()
    return name.strip()


def mark_is_legal(mark):
    if not mark:
        return False
    return mark.strip().upper() not in ROTATED_OUT_REGULATION_MARKS


def effective_mark(p):
    """Per-card regulation_mark takes priority over the set-level value --
    confirmed 2026-06-20 that marks are NOT always uniform within a set
    (SV/MEG eras especially), so the per-card field is the source of truth
    whenever it's populated."""
    if p.regulation_mark:
        return p.regulation_mark
    return p.card_set.regulation_mark if p.card_set else ''


def _lower(s):
    return (s or '').lower()


TRAINER_TOKENS = ('trainer', 'supporter', 'stadium', 'item', 'tool')


def is_basic_energy(p):
    # card_subtypes correctly tags most of these as 'Basic Energy', but
    # ~444 genuine Basic Energy rows have BOTH supertype and card_subtypes
    # completely blank, identifiable only by name (e.g.
    # "Basic Fire Energy - 002"). The one known exception, "Magnetic M
    # Energy", does NOT start with "Basic " and is a Special Energy card --
    # correctly excluded by this check, falling through to the strict
    # per-print rule instead.
    if 'basic energy' in _lower(p.card_subtypes):
        return True
    name = p.name or ''
    return name.strip().startswith('Basic ') and 'energy' in name.lower()


def is_trainer(p):
    # supertype is NOT a reliable Pokemon/Trainer/Energy enum in this DB --
    # for Pokemon cards it actually stores evolution STAGE ("Basic",
    # "Stage 1", "Stage 2", "VMAX", etc.), confirmed 2026-06-20. So check
    # both supertype and card_subtypes for known Trainer-category tokens.
    # rarity == 'ace_spec' is an extra reliable signal since ACE SPEC cards
    # are always Trainer (Item or Supporter) cards in the real TCG rules.
    haystack = _lower(p.supertype) + ' ' + _lower(p.card_subtypes)
    if any(tok in haystack for tok in TRAINER_TOKENS):
        return True
    return (p.rarity or '').lower() == 'ace_spec'


class Command(BaseCommand):
    help = "Recompute legal_standard for every product per current rotation rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts of what would change without saving anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        products = list(
            PokemonProduct.objects.select_related('card_set')
            .only('id', 'name', 'supertype', 'card_subtypes', 'rarity', 'regulation_mark', 'legal_standard', 'card_set__regulation_mark')
        )
        self.stdout.write(f"Loaded {len(products)} product(s).")

        new_legal = {}  # product id -> bool

        # Pass 0: sibling variant rows of the EXACT same printing (e.g.
        # Ultra Ball BRS-150-N vs BRS-150-RH -- same card, same set,
        # different variant_override) sometimes have card_subtypes/
        # supertype populated on only one of them (confirmed 2026-06-20).
        # Since they're the same underlying card, they must get identical
        # legality. So classify Trainer-ness per (name, card_set) cluster:
        # if ANY sibling in the cluster looks like a Trainer card, treat
        # every row in that cluster as Trainer.
        cluster_is_trainer = defaultdict(bool)
        for p in products:
            key = (p.name, p.card_set_id)
            if is_trainer(p):
                cluster_is_trainer[key] = True

        # Pass 1: Pokemon + Special (non-Basic) Energy, strictly per-print.
        trainer_products = []
        for p in products:
            key = (p.name, p.card_set_id)
            if cluster_is_trainer[key]:
                trainer_products.append(p)
                continue
            if is_basic_energy(p):
                new_legal[p.id] = True
                continue
            new_legal[p.id] = mark_is_legal(effective_mark(p))

        # Pass 2: Trainer cards, grouped by cleaned base name.
        groups = defaultdict(list)
        for p in trainer_products:
            groups[clean_base_name(p.name)].append(p)

        for base_name, group in groups.items():
            any_legal = any(mark_is_legal(effective_mark(p)) for p in group)
            for p in group:
                new_legal[p.id] = any_legal

        # Compare against current state, build the update list.
        to_update = []
        changed_ids = set()
        becoming_legal = 0
        becoming_illegal = 0
        unchanged = 0

        for p in products:
            target = new_legal[p.id]
            if target != p.legal_standard:
                if target:
                    becoming_legal += 1
                else:
                    becoming_illegal += 1
                changed_ids.add(p.id)
                p.legal_standard = target
                to_update.append(p)
            else:
                unchanged += 1

        self.stdout.write("")
        self.stdout.write(f"Would change: {len(to_update)} product(s)")
        self.stdout.write(f"  -> becoming legal_standard=True:  {becoming_legal}")
        self.stdout.write(f"  -> becoming legal_standard=False: {becoming_illegal}")
        self.stdout.write(f"Unchanged: {unchanged} product(s)")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Dry run — no changes saved."))
            self.stdout.write(f"Trainer groups found: {len(groups)} (covering {len(trainer_products)} Trainer-classified products)")
            # Show a sample of Trainer groups that flipped, for sanity-checking.
            sample_shown = 0
            for base_name, group in groups.items():
                group_changed = [p for p in group if p.id in changed_ids]
                if group_changed and sample_shown < 15:
                    marks = sorted({
                        (p.card_set.code if p.card_set else '?', effective_mark(p), p.regulation_mark)
                        for p in group
                    })
                    self.stdout.write(f"  Trainer group '{base_name}': now legal={new_legal[group[0].id]} | printings: {marks}")
                    sample_shown += 1
            if sample_shown == 0 and groups:
                self.stdout.write("  (no Trainer groups had any changes -- every Trainer card's computed legality already matched its stored value)")
            return

        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ['legal_standard'], batch_size=500)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Saved. Updated {len(to_update)} product(s)."))
