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

    def __str__(self):
        return self.username
