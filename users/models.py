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

    def __str__(self):
        return self.username
