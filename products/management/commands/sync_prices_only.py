import math, os, time, requests
from decimal import Decimal, ROUND_UP
from django.core.management.base import BaseCommand
from django.db import transaction

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")

# Reject an update that would move a price by more than this multiple in
# either direction (2026-08-12 -- Michael: "some prices are horribly
# wrong!!"). TCGCSV occasionally serves a garbage row for a productId (a
# single mis-listed/troll TCGPlayer listing can blow out low/mid/high for a
# whole card), and previously nothing stood between that garbage number and
# a live price on the site. Anything past this ratio gets skipped and
# reported instead of silently written -- a genuine 5x+ market move on a
# single card overnight is rare enough that it's worth a human glance
# either way.
#
# Configurable via PRICE_SYNC_MAX_JUMP_RATIO (2026-08-17) purely so a
# one-off catch-up run can temporarily raise/disable this without a code
# push+revert cycle: this same clamp, once live, will otherwise permanently
# protect any row that was ALREADY wrong by more than 5x from ever
# self-correcting again (confirmed live -- several Swablu reverse-holo rows
# sat untouched since 2026-06-19 despite the nightly cron running fine every
# day since). Set the env var sky-high in Railway, hit "Run now" once, then
# remove it again so future nightly runs use the safe default of 5.
MAX_JUMP_RATIO = Decimal(os.environ.get("PRICE_SYNC_MAX_JUMP_RATIO") or "5")

# Floor price (2026-08-17) -- Michael: "we need to impliment R1.80 minimum
# price on the site". A handful of bulk commons price out under R1 from raw
# TCGCSV market data, not economically worth listing/shipping at that price.
# Applied AFTER the suspicious-jump check above (it's a deliberate business
# rule, not organic market data, so it shouldn't get caught by/count against
# that clamp) and as a one-time sweep at the top of every run so it also
# catches existing rows this sync never touches (no tcgcsv_product_id, or a
# TCGCSV row that no longer exists) -- not just newly-synced ones.
MIN_PRICE = Decimal(os.environ.get("PRICE_SYNC_MIN_PRICE") or "1.80")

# TCGCSV variant name -> DB variant_override code. Must stay in sync with
# VARIANT_CHOICES in orders/admin.py (the codes staff can actually assign to
# a card) -- a TCGCSV label with no entry here silently falls back to 'N'
# below, which is exactly how the 1st Edition bug happened (see fix below).
VARIANT_MAP = {
    'Normal':                 'N',
    'Reverse Holofoil':       'RH',
    'Holofoil':               'H',
    'Unlimited Holofoil':     'H',
    'Unlimited':              'N',
    # BUG FIX 2026-08-12 (Michael: "some prices are horribly wrong!!"): these
    # two used to map to 'H'/'N' -- the same codes as the ordinary Unlimited
    # print -- even though the site has its own dedicated 'FE' (1st Edition)
    # variant code (see VARIANT_CHOICES, orders/admin.py). 1st Edition WotC-
    # era cards are routinely worth several times their Unlimited
    # counterpart, so a 1st Edition product row was either being skipped
    # entirely (no (pid, 'FE') key in the map) or, worse, silently
    # overwritten with the far cheaper Unlimited print's price via the
    # ambiguous-pid fallback below. Now maps to its own code so it only
    # ever matches an actual 'FE' product row.
    '1st Edition Holofoil':   'FE',
    '1st Edition':            'FE',
}

class Command(BaseCommand):
    help = "Nightly price-only sync from TCGCSV"

    def handle(self, *args, **options):
        from products.models import PokemonProduct

        # One-time sweep every run: catch anything already priced under the
        # floor regardless of whether TCGCSV touches it this run (no
        # tcgcsv_product_id, delisted pid, etc). price=0 is left alone --
        # that means "never priced yet", not "priced too low", and gets a
        # real first price the normal way once TCGCSV data comes in below.
        floored = PokemonProduct.objects.filter(price__gt=0, price__lt=MIN_PRICE).update(price=MIN_PRICE)
        if floored:
            self.stdout.write(f"Floored {floored:,} product(s) up to the R{MIN_PRICE} minimum")

        # Fetch live USD/ZAR rate
        rate = Decimal("18.50")
        for url in ["https://api.exchangerate-api.com/v4/latest/USD", "https://open.er-api.com/v6/latest/USD"]:
            try:
                r = requests.get(url, timeout=10)
                zar = r.json().get("rates", {}).get("ZAR")
                if zar:
                    rate = Decimal(str(zar))
                    break
            except Exception:
                continue
        self.stdout.write(f"1 USD = R{rate}")

        # Fetch all groups from TCGCSV
        self.stdout.write("Fetching groups from TCGCSV...")
        r = requests.get(f"{TCGCSV_BASE}/groups", headers=HEADERS, timeout=30)
        groups = r.json()
        if isinstance(groups, dict):
            groups = groups.get("results", groups.get("data", []))
        self.stdout.write(f"  {len(groups)} groups found")

        # Build map: (tcgcsv_product_id, variant_override) -> product
        self.stdout.write("Loading products from DB...")
        all_products = PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True)
        pid_variant_map = {}
        pid_counts = {}   # how many DB products share this pid (any variant)
        pid_map = {}      # fallback target: the one product, ONLY when pid_counts == 1
        for p in all_products:
            key = (p.tcgcsv_product_id, p.variant_override or 'N')
            pid_variant_map[key] = p
            pid_counts[p.tcgcsv_product_id] = pid_counts.get(p.tcgcsv_product_id, 0) + 1
            pid_map[p.tcgcsv_product_id] = p
        self.stdout.write(f"  {len(pid_variant_map):,} products loaded")

        def round_up_10c(zar):
            # Round UP to nearest R0.10
            return (Decimal(str(zar)) * 10).to_integral_value(rounding=ROUND_UP) / 10

        updated = skipped = no_match = ambiguous = suspicious = 0
        suspicious_examples = []
        to_update = []

        for i, g in enumerate(groups, 1):
            gid = g.get("groupId") or g.get("id")
            try:
                r = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
                prices = r.json()
                if isinstance(prices, dict):
                    prices = prices.get("results", prices.get("data", []))
                if not isinstance(prices, list):
                    continue
            except Exception:
                continue

            for row in prices:
                pid = row.get("productId")
                if not pid:
                    continue
                pid = int(pid)

                # Get variant from TCGCSV and map to DB code
                tcg_variant = row.get("subTypeName") or row.get("printing") or "Normal"
                db_variant = VARIANT_MAP.get(tcg_variant, 'N')

                # Try exact (productId, variant) match first. Only fall back
                # to "the product with this pid" when that pid is UNIQUE in
                # our DB (pid_counts == 1) -- BUG FIX 2026-08-12: previously
                # this fell back whenever there were multiple DB rows for
                # the same pid too (e.g. a card's N/H/RH prints sharing one
                # base TCGCSV productId, a documented TCGCSV pattern -- see
                # Gloom N/RH both carrying pid 662164), silently picking
                # whichever row the DB query happened to load last and
                # writing that ONE card's price onto a DIFFERENT print. Now
                # that ambiguous case is skipped and counted instead of
                # guessed.
                p = pid_variant_map.get((pid, db_variant))
                if p is None:
                    if pid_counts.get(pid) == 1:
                        p = pid_map.get(pid)
                    else:
                        ambiguous += 1
                        continue
                if p is None:
                    no_match += 1
                    continue

                # BUG FIX 2026-08-12: marketPrice is TCGPlayer's own smoothed
                # reference price; midPrice is just a low/high-derived stat
                # that a single outlier "reserve"/troll listing can drag
                # well above the real going rate (confirmed live: one card
                # showed midPrice 20%+ above marketPrice with nothing else
                # unusual about it). midPrice now only used when marketPrice
                # is missing, not preferred over it.
                usd = row.get("marketPrice") or row.get("midPrice") or row.get("lowPrice")
                if not usd or float(usd) <= 0:
                    continue

                new_price = round_up_10c(Decimal(str(usd)) * rate * MARKUP)

                # Sanity clamp -- see MAX_JUMP_RATIO above. Checked against
                # the raw TCGCSV-derived price (before the floor below) since
                # this is meant to catch genuine bad market data, not react
                # to the floor policy. p.price == 0 means this product has
                # never had a real price yet, so any first price is allowed
                # through uncapped.
                if p.price and p.price > 0:
                    ratio = new_price / p.price if p.price else None
                    if ratio and (ratio > MAX_JUMP_RATIO or ratio < (1 / MAX_JUMP_RATIO)):
                        suspicious += 1
                        if len(suspicious_examples) < 25:
                            suspicious_examples.append(
                                f"    {p.sku or p.id} ({p.name}, {p.variant_override or 'N'}): "
                                f"R{p.price} -> R{new_price} (TCGCSV pid {pid})"
                            )
                        continue

                # Floor applied last, after the clamp check -- a deliberate
                # business rule, not something that should ever get skipped
                # as a "suspicious jump".
                new_price = max(new_price, MIN_PRICE)
                if p.price == new_price:
                    skipped += 1
                    continue

                p.price = new_price
                to_update.append(p)
                updated += 1

            if len(to_update) >= 2000:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, ["price"])
                self.stdout.write(f"  ...wrote {updated:,}")
                to_update = []

            time.sleep(0.2)

        if to_update:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(to_update, ["price"])

        self.stdout.write(
            f"Done. Updated={updated:,} Skipped(no change)={skipped:,} "
            f"No match={no_match:,} Ambiguous pid (skipped)={ambiguous:,} "
            f"Suspicious jump (skipped)={suspicious:,}"
        )
        if suspicious_examples:
            self.stdout.write("Suspicious jumps skipped -- check these manually:")
            for line in suspicious_examples:
                self.stdout.write(line)
