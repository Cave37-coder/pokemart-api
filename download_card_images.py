"""
Management command: download_card_images
========================================
Downloads hi-res card images from pokemontcg.io for every PokemonProduct
in the database. Saves one clean image per unique (set_code, card_number).

Usage:
    python manage.py download_card_images
    python manage.py download_card_images --set sv3pt5
    python manage.py download_card_images --force          # re-download existing
    python manage.py download_card_images --dry-run

Output structure:
    media/card_images/originals/{set_code}/{number}.png

Progress is saved to card_image_progress.json so interrupted runs resume.
"""

import os
import json
import time
import random
import requests
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct, CardSet

PROGRESS_FILE = "card_image_progress.json"
POKEMONTCG_API = "https://api.pokemontcg.io/v2/cards"
IMAGES_CDN     = "https://images.pokemontcg.io"

# Polite delays — randomised to avoid pattern detection
DELAY_MIN = 1.2   # seconds between requests
DELAY_MAX = 2.8
DELAY_BURST = 8.0  # extra pause every N requests
BURST_EVERY = 25   # requests

HEADERS = {
    "User-Agent": "PokeBulkSA/1.0 (pokebulksa.co.za; card image archiver)",
}
if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
    HEADERS["X-Api-Key"] = settings.POKEMONTCG_API_KEY


class Command(BaseCommand):
    help = "Download hi-res card images from pokemontcg.io"

    def add_arguments(self, parser):
        parser.add_argument("--set",     dest="set_code", help="Only download images for this set code (e.g. sv3pt5)")
        parser.add_argument("--force",   action="store_true", help="Re-download images that already exist on disk")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without saving anything")
        parser.add_argument("--delay-min", type=float, default=DELAY_MIN, help=f"Min seconds between requests (default {DELAY_MIN})")
        parser.add_argument("--delay-max", type=float, default=DELAY_MAX, help=f"Max seconds between requests (default {DELAY_MAX})")

    def handle(self, *args, **options):
        set_filter   = options["set_code"]
        force        = options["force"]
        dry_run      = options["dry_run"]
        delay_min    = options["delay_min"]
        delay_max    = options["delay_max"]

        base_dir = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        base_dir.mkdir(parents=True, exist_ok=True)

        progress = self._load_progress()

        # ── Build the work list ──────────────────────────────────────────────
        qs = PokemonProduct.objects.select_related("card_set").values(
            "card_set__code", "card_number"
        ).distinct()

        if set_filter:
            qs = qs.filter(card_set__code=set_filter)

        # Deduplicate: one image per (set_code, card_number)
        work = {}
        for row in qs:
            set_code   = row["card_set__code"]
            card_number = row["card_number"]
            if set_code and card_number:
                key = f"{set_code}:{card_number}"
                work[key] = (set_code, card_number)

        total  = len(work)
        done   = 0
        skipped = 0
        failed  = []

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'[DRY RUN] ' if dry_run else ''}Queued {total} unique card images to download\n"
        ))

        # ── Download loop ────────────────────────────────────────────────────
        for i, (key, (set_code, card_number)) in enumerate(work.items(), 1):
            # Skip already completed
            if key in progress.get("completed", set()) and not force:
                skipped += 1
                continue

            dest_dir = base_dir / set_code
            dest_file = dest_dir / f"{card_number}.png"

            if dest_file.exists() and not force:
                progress.setdefault("completed", set()).add(key)
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY] Would download {set_code}/{card_number}.png")
                done += 1
                continue

            # Fetch image URL from the API (needed to get exact filename)
            image_url = self._get_image_url(set_code, card_number)
            if not image_url:
                self.stdout.write(self.style.WARNING(
                    f"  ✗ No image found: {set_code}/{card_number}"
                ))
                failed.append(key)
                time.sleep(random.uniform(delay_min, delay_max))
                continue

            # Download the actual image bytes
            success = self._download_image(image_url, dest_dir, dest_file)
            if success:
                done += 1
                progress.setdefault("completed", set()).add(key)
                self.stdout.write(f"  ✓ [{i}/{total}] {set_code}/{card_number}.png")
            else:
                failed.append(key)
                self.stdout.write(self.style.WARNING(
                    f"  ✗ [{i}/{total}] Failed: {set_code}/{card_number}"
                ))

            # Polite delay
            delay = random.uniform(delay_min, delay_max)
            if i % BURST_EVERY == 0:
                self.stdout.write(self.style.HTTP_INFO(
                    f"  ⏸  Burst pause {DELAY_BURST}s after {BURST_EVERY} requests…"
                ))
                time.sleep(DELAY_BURST)
            else:
                time.sleep(delay)

            # Save progress every 10 downloads
            if i % 10 == 0:
                self._save_progress(progress)

        self._save_progress(progress)

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Downloaded : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped    : {skipped}  (already on disk)"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed     : {len(failed)}"))
            for f in failed[:20]:
                self.stdout.write(f"    - {f}")
            if len(failed) > 20:
                self.stdout.write(f"    … and {len(failed) - 20} more (see {PROGRESS_FILE})")
        self.stdout.write("─" * 50 + "\n")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_image_url(self, set_code, card_number):
        """
        Try the CDN URL directly first (fast, no API quota).
        Format: https://images.pokemontcg.io/{set_code}/{number}_hires.png
        Fall back to the REST API if the CDN 404s.
        """
        # pokemontcg.io uses lowercase set codes in image paths
        sc = set_code.lower()

        # Some sets use numeric-only card numbers; strip leading zeros for API id
        cdn_url = f"{IMAGES_CDN}/{sc}/{card_number}_hires.png"
        try:
            r = requests.head(cdn_url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return cdn_url
        except requests.RequestException:
            pass

        # API fallback: construct card id as {set_code}-{number}
        card_id = f"{sc}-{card_number}"
        try:
            r = requests.get(
                f"{POKEMONTCG_API}/{card_id}",
                headers=HEADERS,
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                return data.get("images", {}).get("large") or data.get("images", {}).get("small")
        except requests.RequestException:
            pass

        return None

    def _download_image(self, url, dest_dir, dest_file):
        """Download image bytes to dest_file. Returns True on success."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
            if r.status_code == 200:
                with open(dest_file, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        fh.write(chunk)
                return True
            else:
                return False
        except requests.RequestException:
            return False

    def _load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE) as fh:
                    data = json.load(fh)
                    data["completed"] = set(data.get("completed", []))
                    return data
            except Exception:
                pass
        return {"completed": set()}

    def _save_progress(self, progress):
        data = dict(progress)
        data["completed"] = list(progress.get("completed", set()))
        with open(PROGRESS_FILE, "w") as fh:
            json.dump(data, fh, indent=2)
