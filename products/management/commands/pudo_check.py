"""
pudo_check.py -- safe, read-only test of the Pudo API setup. Books NOTHING.

    python manage.py pudo_check --skip-checks
    python manage.py pudo_check --skip-checks --to CG54     # also asks Pudo for the rate sender -> CG54

Checks: settings present, the API key is accepted (downloads the locker list), your drop-off locker is on the
list, and (with --to) that Pudo returns an Extra Small locker-to-locker rate for the route.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Read-only check of the Pudo API settings (books nothing)."

    def add_arguments(self, parser):
        parser.add_argument("--to", default="", help="A locker code to price a route to, e.g. CG54.")
        parser.add_argument("--probe", action="store_true",
                            help="Try the likely Pudo servers/paths and print only the HTTP status of each (no data, no booking).")

    def handle(self, *args, **opts):
        from orders import pudo
        env = pudo._env
        self.stdout.write(f"Booking switched on : {pudo.enabled()} (PUDO_BOOKING_ENABLED)")
        self.stdout.write(f"API base            : {pudo._base()}")
        self.stdout.write(f"API key set         : {bool(str(env('PUDO_API_KEY', '')).strip())}")
        sender = str(env('PUDO_SENDER_TERMINAL', '')).strip().upper()
        self.stdout.write(f"Sender locker       : {sender or '-- NOT SET --'}")
        self.stdout.write(f"Sender mobile       : {pudo._mobile(str(env('PUDO_SENDER_MOBILE', ''))) or '-- NOT SET --'}")
        if opts["probe"]:
            self._probe(pudo, sender, (opts["to"] or "CG10").strip().upper())
            return
        me = None
        try:
            lockers = pudo.get_lockers()
            self.stdout.write(self.style.SUCCESS(f"Locker list OK     : {len(lockers)} lockers/kiosks"))
            me = pudo.locker_by_code(sender) if sender else None
            if sender:
                self.stdout.write((self.style.SUCCESS if me else self.style.WARNING)(
                    f"Your drop-off locker: {me['name'] + ' - ' + me['address'] if me else sender + ' not found in the list'}"))
        except pudo.PudoError as e:
            self.stdout.write(self.style.WARNING(f"Locker list unavailable: {e}"))
            self.stdout.write("(If it says 5xx that's Pudo's side; the picker falls back to typing the locker code. "
                              "401/403 = key/header; 404 = PUDO_API_BASE should end in /api/v1.) Carrying on with the rate check...")
        if opts["to"] and sender:
            per = pudo.cards_per_size()
            for tier, short in enumerate(pudo.SIZE_SHORT):
                label = f"{short} ({tier * per + 1}-{(tier + 1) * per} cards)"
                try:
                    code, rate = pudo._service_for(tier, sender, opts["to"].strip().upper())
                    self.stdout.write(self.style.SUCCESS(f"Rate {label:24}: {code}  R{rate}"))
                except pudo.PudoError as e:
                    self.stdout.write(self.style.WARNING(f"Rate {label:24}: {e}"))

    def _probe(self, pudo, sender, to):
        import requests
        bases = []
        for b in (pudo._base(), "https://api-pudo.co.za", "https://api-sandbox.pudo.co.za",
                  "https://dev.api-pudo.co.za", "https://api-tcg.co.za"):
            if b not in bases:
                bases.append(b)
        try:
            hdr = pudo._headers()
        except pudo.PudoError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return
        def show(label, resp):
            try:
                body = resp.json()
                msg = (body.get("message") or body.get("error") or "") if isinstance(body, dict) else f"list of {len(body)}"
            except ValueError:
                msg = "(not JSON)"
            self.stdout.write(f"  {label:34} -> {resp.status_code}  {str(msg)[:90]}")
        for b in bases:
            self.stdout.write(b)
            for path in ("/lockers-data", "/lockers", "/terminals"):
                try:
                    show(f"GET {path}", requests.get(b + path, headers=hdr, timeout=20))
                except requests.RequestException as e:
                    self.stdout.write(f"  GET {path:29} -> failed ({e.__class__.__name__})")
            if sender:
                try:
                    show(f"POST /rates {sender}->{to}", requests.post(
                        b + "/rates", headers=hdr, timeout=20,
                        json={"collection_address": {"terminal_id": sender}, "delivery_address": {"terminal_id": to}}))
                except requests.RequestException as e:
                    self.stdout.write(f"  POST /rates -> failed ({e.__class__.__name__})")
