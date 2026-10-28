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

    def handle(self, *args, **opts):
        from orders import pudo
        env = pudo._env
        self.stdout.write(f"Booking switched on : {pudo.enabled()} (PUDO_BOOKING_ENABLED)")
        self.stdout.write(f"API base            : {pudo._base()}")
        self.stdout.write(f"API key set         : {bool(str(env('PUDO_API_KEY', '')).strip())}")
        sender = str(env('PUDO_SENDER_TERMINAL', '')).strip().upper()
        self.stdout.write(f"Sender locker       : {sender or '-- NOT SET --'}")
        self.stdout.write(f"Sender mobile       : {pudo._mobile(str(env('PUDO_SENDER_MOBILE', ''))) or '-- NOT SET --'}")
        try:
            lockers = pudo.get_lockers()
        except pudo.PudoError as e:
            self.stdout.write(self.style.ERROR(f"Locker list FAILED: {e}"))
            self.stdout.write("If it says 401/403 the key or header is wrong: set PUDO_AUTH_HEADER / PUDO_AUTH_PREFIX; "
                              "if it can't connect or 404s, check PUDO_API_BASE.")
            return
        self.stdout.write(self.style.SUCCESS(f"Locker list OK     : {len(lockers)} lockers/kiosks"))
        me = pudo.locker_by_code(sender) if sender else None
        if sender:
            self.stdout.write((self.style.SUCCESS if me else self.style.WARNING)(
                f"Your drop-off locker: {me['name'] + ' - ' + me['address'] if me else sender + ' not found in the list'}"))
        if opts["to"] and sender:
            per = pudo.cards_per_size()
            for tier, short in enumerate(pudo.SIZE_SHORT):
                label = f"{short} ({tier * per + 1}-{(tier + 1) * per} cards)"
                try:
                    code, rate = pudo._service_for(tier, sender, opts["to"].strip().upper())
                    self.stdout.write(self.style.SUCCESS(f"Rate {label:24}: {code}  R{rate}"))
                except pudo.PudoError as e:
                    self.stdout.write(self.style.WARNING(f"Rate {label:24}: {e}"))
