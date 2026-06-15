import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

emails = [
    {
        'to': 'shailenshay@icloud.com',
        'name': 'Shailen',
        'order': 13,
        'total': 'R80.58',
        'items': 21,
        'delivery': 'Cash on Collection',
        'extra': '\nRegarding your request to drop the order at Gengar Games — we will absolutely accommodate that. Please confirm when you re-place your order and we will make a note of it.\n',
    },
    {
        'to': 'kizyvita@gmail.com',
        'name': 'Wendy',
        'order': 14,
        'total': 'R255.29',
        'items': 61,
        'delivery': 'Courier to your Pudo locker',
        'extra': '\nWe also noted your request regarding the damaged cards from Kit — we have not forgotten and will sort that out for you.\n',
    },
]

for e in emails:
    subject = f"Important notice about your PokéBulk SA Order #{e['order']}"
    body = f"""Hi {e['name']},

We hope you're well. We're reaching out regarding your recent order #{e['order']} on PokéBulk SA (Total: {e['total']} | {e['items']} cards | {e['delivery']}).

Unfortunately, due to a technical issue during a system upgrade, the card details linked to your order were lost. We sincerely apologise for the inconvenience — this is entirely on our end.

Your payment status, account, and personal details are all completely safe and unaffected.
{e['extra']}
To help us fulfil your order as quickly as possible, could you please reply to this email with the cards you had selected? Even a rough list of the sets or Pokémon you were after would help us greatly.

Alternatively, you're welcome to re-browse our catalogue at www.pokebulk.co.za and place a new order — all our stock is available there.

Once again, we sincerely apologise for this inconvenience and appreciate your patience and understanding.

Kind regards,
Michael
PokéBulk SA
Tel: 074 488 6919 (WhatsApp)
enquiries@pokebulk.co.za
www.pokebulk.co.za
4 Heloise Street, Birchleigh North, Kempton Park
"""

    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [e['to']],
            fail_silently=False,
        )
        print(f"SENT → {e['name']} ({e['to']})")
    except Exception as ex:
        print(f"FAILED → {e['name']} ({e['to']}): {ex}")

print("\nDone.")
