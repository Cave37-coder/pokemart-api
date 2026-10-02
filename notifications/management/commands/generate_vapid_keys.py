"""
One-off: generate the key pair Web Push needs.

    python manage.py generate_vapid_keys

Prints two lines to paste into Railway's Variables tab (and into the local
.env for testing). Does not touch the database or write any file.

Only ever run this ONCE for the live site. The public key is baked into
every customer's subscription at the moment they turn notifications on --
replace the pair later and every existing subscription stops working until
that customer switches notifications off and on again.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


class Command(BaseCommand):
    help = "Generate a VAPID key pair for Web Push notifications (prints env var lines; changes nothing)."

    def handle(self, *args, **options):
        key = ec.generate_private_key(ec.SECP256R1())
        private_raw = key.private_numbers().private_value.to_bytes(32, 'big')
        public_raw = key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        self.stdout.write("")
        self.stdout.write("Add these two variables on Railway (and to your local .env):")
        self.stdout.write("")
        self.stdout.write(f"VAPID_PUBLIC_KEY={_b64url(public_raw)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={_b64url(private_raw)}")
        self.stdout.write("")
        self.stdout.write("Keep VAPID_PRIVATE_KEY secret -- never commit it. Generate once only;")
        self.stdout.write("replacing the pair later breaks every customer's existing subscription.")
        self.stdout.write("")
