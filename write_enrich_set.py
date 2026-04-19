content = '''import requests
import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from products.models import PokemonProduct, CardSet, Era

class Command(BaseCommand):
    help = "Enrich a full Pokemon set with all variants"

    def add_arguments(self, parser):
        parser.add_argument("set_id", type=str)
        parser.add_argument("--stock", type=int, default=1)
        parser.add_argument("--overwrite", action="store_true", default=True)

    def handle(self, *args, **options):
        set_id = options["set_id"]
        stock = options["stock"]
        overwrite = options["overwrite"]

        headers = {}
        if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
            headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        self.stdout.write(f"Fetching set info for {set_id}...")
        r = requests.get(f"https://api.pokemontcg.io/v2/sets/{set_id}", headers=headers)
        if r.status_code != 200:
            self.stderr.write(f"Set not found: {set_id}")
            return

        set_data = r.json().get("data", {})
        set_name = set_data.get("name", set_id)
        total = set_data.get("total", 0)
        self.stdout.write(f"Found: {set_name} ({total} cards)")

        # Fetch all cards in set
        self.stdout.write("Fetching card list...")
        cards_r = requests.get(
            f"https://api.pokemontcg.io/v2/cards?q=set.id:{set_id}&pageSize=500&orderBy=number",
            headers=headers
        )
        if cards_r.status_code != 200:
            self.stderr.write(f"Failed to fetch cards for {set_id}")
            return

        cards = cards_r.json().get("data", [])
        self.stdout.write(f"Processing {len(cards)} cards...")
        self.stdout.write("=" * 50)

        imported = 0
        failed = 0
        skipped = 0

        for i, card in enumerate(cards, 1):
            card_id = card.get("id", "")
            card_name = card.get("name", "")
            card_number = card.get("number", "?")

            self.stdout.write(f"[{i}/{len(cards)}] {card_name} ({card_id})...")

            try:
                call_command(
                    "import_card",
                    card_id,
                    stock=stock,
                    overwrite=overwrite,
                    verbosity=0,
                )
                imported += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Done"))
            except SystemExit:
                skipped += 1
                self.stdout.write(f"  - Skipped (exists)")
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ✗ Failed: {e}"))

            # Rate limit protection
            if i % 20 == 0:
                time.sleep(1)

        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"Enrichment complete for {set_name}"
        ))
        self.stdout.write(f"  Imported: {imported}")
        self.stdout.write(f"  Skipped:  {skipped}")
        self.stdout.write(f"  Failed:   {failed}")
        self.stdout.write(f"  Total:    {len(cards)}")
'''

with open("products/management/commands/enrich_set.py", "w", encoding="utf-8") as f:
    f.write(content)
print("enrich_set.py written!")