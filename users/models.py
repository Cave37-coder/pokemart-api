from django.db import models
from django.contrib.auth.models import AbstractUser
from products.models import PokemonProduct


class User(AbstractUser):
    TRAINER_LEVELS = [
        ('rookie',        'Rookie Trainer'),
        ('intermediate',  'Intermediate Trainer'),
        ('expert',        'Expert Trainer'),
        ('master',        'Pokémon Master'),
    ]

    DELIVERY_PREFERENCE = [
        ('pudo',       'Pudo Locker'),
        ('address',    'Home / Office Address'),
        ('collection', 'Collection'),
    ]

    avatar         = models.ImageField(upload_to='avatars/', blank=True, null=True)
    trainer_level  = models.CharField(max_length=20, choices=TRAINER_LEVELS, default='rookie')
    wishlist       = models.ManyToManyField(PokemonProduct, blank=True, related_name='wishlisted_by')
    created_at     = models.DateTimeField(auto_now_add=True)

    # ── Delivery preference ───────────────────────────────────────────────
    delivery_preference = models.CharField(
        max_length=20, choices=DELIVERY_PREFERENCE, default='pudo', blank=True
    )

    # ── Home / office address ─────────────────────────────────────────────
    address_line1  = models.CharField(max_length=255, blank=True)
    address_line2  = models.CharField(max_length=255, blank=True)
    address_city   = models.CharField(max_length=100, blank=True)
    address_province = models.CharField(max_length=100, blank=True)
    address_postal_code = models.CharField(max_length=20, blank=True)

    # ── Pudo locker ───────────────────────────────────────────────────────
    pudo_locker_name    = models.CharField(max_length=255, blank=True)
    pudo_locker_address = models.CharField(max_length=255, blank=True)
    pudo_locker_code    = models.CharField(max_length=50, blank=True)

    # ── Contact ───────────────────────────────────────────────────────────
    phone_number   = models.CharField(max_length=20, blank=True)

    # ── Checklist community features (Compare & Compete, 2026-07-30) ───────
    # Both default to "off" on purpose -- a customer's checklist progress is
    # private (name, blank display name) until they explicitly opt in and
    # pick a display name. Leaderboard/Wall of Honour queries filter on
    # checklist_public=True AND a non-blank public_display_name, so leaving
    # either one unset keeps a customer completely out of both.
    public_display_name = models.CharField(
        max_length=40, blank=True,
        help_text="Shown on leaderboards / Wall of Honour instead of the real username. Blank = not shown."
    )
    checklist_public = models.BooleanField(
        default=False,
        help_text="Opt-in: show this customer's checklist completion on leaderboards and the Wall of Honour."
    )

    # ── Community: public collection profile + DMs (2026-08-07) ────────────
    # Deliberately separate from checklist_public, same reasoning Michael
    # gave for keeping the Pokedex feature itself independent from
    # Checklists: "I want to track my Poke Dex separate to rest of my
    # collection." A customer might want checklist progress public but their
    # Pokedex/wishlist private, or vice versa -- one flag can't express that.
    # Both still reuse public_display_name/avatar as the one shared public
    # identity across every opt-in feature rather than adding a second name.
    community_profile_public = models.BooleanField(
        default=False,
        help_text="Opt-in: show this customer's Pokedex collection and wishlist on a public community profile page."
    )
    community_bio = models.CharField(
        max_length=200, blank=True,
        help_text="Short public note shown on the community profile, e.g. \"Looking for shiny Charizards!\""
    )
    # A second, separate opt-in on top of community_profile_public -- seeing
    # someone's collection is low-risk, but receiving unsolicited messages
    # from strangers is a different kind of exposure, so it gets its own
    # explicit switch rather than being bundled in.
    messaging_enabled = models.BooleanField(
        default=False,
        help_text="Opt-in: allow other customers to send this customer direct messages / trade requests."
    )

    def __str__(self):
        return self.username
