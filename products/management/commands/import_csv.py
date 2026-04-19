import csv
import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from products.models import PokemonProduct

TYPE_TO_SUFFIX = {
    "normal": "N", "Normal": "N",
    "reverseHolofoil": "RH", "Reverse Holofoil": "RH",
    "Reverseholofoil": "RH", "Reverse Holo": "RH",
    "holofoil": "H", "Holofoil": "H", "Rare Holo Foil": "H",
    "Double Rare EX (Holo Foil)": "DR",
    "Ace Spec": "AS", "ACE SPEC": "AS",
    "Mirror Holo": "MH",
    "Energy Holo": "ERH",
    "Poke Ball Holo": "RH-PB", "Poke Ball Reverse Holo": "RH-PB",
    "Master Ball Holo": "RH-MB", "Master Ball Reverse Holo": "RH-MB",
    "Friend Ball Holo": "BRH-FB",
    "Love Ball Holo": "BRH-LB",
    "Quick Ball Holo": "BRH-QB",
    "Dusk Ball Holo": "BRH-DB",
    "Team Rocket Holo": "BRH-R",
    "Pokemon Card": "N",
    "Notavailable": "N",
}

SET_ID_MAP = {
    "hgss1": "hgss1", "hgss2": "hgss2", "hgss3": "hgss3", "hgss4": "hgss4",
    "hsp": "hsp", "col1": "col1",
    "bw1": "bw1", "bw2": "bw2", "bw3": "bw3", "bw4": "bw4",
    "bw5": "bw5", "bw6": "bw6", "bw7": "bw7", "bw8": "bw8",
    "bw9": "bw9", "bw10": "bw10", "bw11": "bw11",
    "bwp": "bwp", "dc1": "dc1", "dv1": "dv1",
    "tk1a": "tk1a", "tk1b": "tk1b", "tk2a": "tk2a", "tk2b": "tk2b",
    "xy1": "xy1", "xy2": "xy2", "xy3": "xy3", "xy4": "xy4",
    "xy5": "xy5", "xy6": "xy6", "xy7": "xy7", "xy8": "xy8",
    "xy9": "xy9", "xy10": "xy10", "xy11": "xy11", "xy12": "xy12",
    "xyp": "xyp", "g1": "g1",
    "sm1": "sm1", "sm2": "sm2", "sm3": "sm3", "sm35": "sm35",
    "sm4": "sm4", "sm5": "sm5", "sm6": "sm6", "sm7": "sm7",
    "sm75": "sm75", "sm8": "sm8", "sm9": "sm9", "sm10": "sm10",
    "sm11": "sm11", "sm115": "sm115", "sm12": "sm12",
    "sma": "sma", "smp": "smp",
    "swsh1": "swsh1", "swsh2": "swsh2", "swsh3": "swsh3",
    "swsh35": "swsh35", "swsh4": "swsh4", "swsh45": "swsh45",
    "swsh45sv": "swsh45sv", "swsh5": "swsh5", "swsh6": "swsh6",
    "swsh7": "swsh7", "swsh8": "swsh8", "swsh9": "swsh9",
    "swsh10": "swsh10", "swsh11": "swsh11", "swsh12": "swsh12",
    "swsh12pt5": "swsh12pt5", "swshp": "swshp",
    "swsh9tg": "swsh9", "swsh10tg": "swsh10",
    "swsh11tg": "swsh11", "swsh12tg": "swsh12",
    "swsh12pt5gg": "swsh12pt5",
    "cel25": "cel25", "cel25c": "cel25c", "pgo": "pgo",
    "sv1": "sv1", "sv2": "sv2", "sv3": "sv3", "sv3pt5": "sv3pt5",
    "sv4": "sv4", "sv4pt5": "sv4pt5", "sv5": "sv5", "sv6": "sv6",
    "sv6pt5": "sv6pt5", "sv7": "sv7", "sv8": "sv8", "sv8pt5": "sv8pt5",
    "sv9": "sv9", "sv9pt5": "sv9pt5",
    "me1": "me1", "me2": "me2", "me2pt5": "me2pt5",
    "me3": "me3", "me03": "me3",
    "me4": "me4", "me04": "me4",
    "me5": "me5", "me05": "me5",
}

def parse_sku(sku):
    parts = sku.strip().split("-")
    if len(parts) < 3:
        return None, None
    try:
        card_number = int(parts[-2])
        csv_set_id = "-".join(parts[:-2])
        tcg_set_id = SET_ID_MAP.get(csv_set_id, csv_set_id)
        return tcg_set_id, card_number
    except ValueError:
        return None, None


class Command(BaseCommand):
    help = "Import cards from a PokeBulk CSV with prices and csv_sku tracking"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")
        parser.add_argument("--overwrite", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--prices-only", action="store_true", default=False,
                            help="Only update prices and stock on existing cards")

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]
        prices_only = options["prices_only"]

        self.stdout.write(f"Reading: {csv_file}")

        rows = []
        with open(csv_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append(row)

        self.stdout.write(f"Found {len(rows)} rows")

        cards = {}
        skipped = 0

        for row in rows:
            sku = row.get("sku", "").strip()
            if not sku:
                continue
            sku_lower = sku.lower()
            if any(x in sku_lower for x in ["startrev", "starter", "bundle", "lot"]):
                continue

            tcg_set_id, card_number = parse_sku(sku)
            if not tcg_set_id or not card_number:
                skipped += 1
                continue

            try:
                price_val = float(row.get("price", 0) or 0)
                qty_val = int(float(row.get("quantity", 0) or 0))
            except (ValueError, TypeError):
                price_val = 0.0
                qty_val = 0

            csv_type = row.get("type", "").strip()
            suffix = TYPE_TO_SUFFIX.get(csv_type, "N")

            card_key = f"{tcg_set_id}-{card_number}"
            if card_key not in cards:
                cards[card_key] = {
                    "tcg_set_id": tcg_set_id,
                    "card_number": card_number,
                    "tcg_api_id": f"{tcg_set_id}-{card_number}",
                    "variants": [],
                }

            cards[card_key]["variants"].append({
                "csv_sku": sku,
                "suffix": suffix,
                "price": price_val,
                "quantity": qty_val,
                "csv_type": csv_type,
            })

        self.stdout.write(f"Parsed {len(cards)} unique cards ({skipped} rows skipped)")

        if dry_run:
            self.stdout.write("--- DRY RUN (first 10 cards) ---")
            for key, card in list(cards.items())[:10]:
                variants_str = ", ".join(
                    f"{v['suffix']}@R{v['price']}(qty:{v['quantity']})"
                    for v in card["variants"]
                )
                self.stdout.write(f"  {card['tcg_api_id']}: {variants_str}")
            return

        imported = 0
        updated = 0
        failed = 0
        total = len(cards)

        for i, (key, card) in enumerate(cards.items(), 1):
            tcg_id = card["tcg_api_id"]
            card_number = card["card_number"]
            variants = card["variants"]

            base_price = max(v["price"] for v in variants) if variants else 0
            base_qty = max(v["quantity"] for v in variants) if variants else 0

            self.stdout.write(f"[{i}/{total}] {tcg_id}...", ending=" ")

            if prices_only:
                count = self._update_prices(card_number, variants)
                if count:
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"updated {count} variants"))
                else:
                    self.stdout.write("not found")
                continue

            try:
                call_command(
                    "import_card",
                    tcg_id,
                    price=base_price,
                    stock=base_qty,
                    overwrite=overwrite,
                    verbosity=0,
                )
                count = self._update_prices(card_number, variants)
                imported += 1
                self.stdout.write(self.style.SUCCESS(f"OK ({count} variants priced)"))

            except SystemExit:
                count = self._update_prices(card_number, variants)
                updated += 1
                self.stdout.write(f"exists (updated {count} prices)")

            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"FAIL: {e}"))

            if i % 20 == 0:
                time.sleep(1)

        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"Done: {imported} imported, {updated} prices updated, {failed} failed"
        ))

    def _update_prices(self, card_number, variants):
        updated = 0
        for variant in variants:
            suffix = variant["suffix"]
            price = variant["price"]
            qty = variant["quantity"]
            csv_sku = variant["csv_sku"]

            products = PokemonProduct.objects.filter(
                card_number=card_number,
                variant_override__iexact=suffix,
            )

            if not products.exists():
                products = PokemonProduct.objects.filter(
                    card_number=card_number,
                    variant_override__icontains=suffix.split("-")[0],
                )

            for p in products:
                p.price = price
                p.stock = qty
                p.csv_sku = csv_sku
                p.save(update_fields=["price", "stock", "csv_sku", "updated_at"])
                updated += 1

        return updated
