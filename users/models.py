from django.db import models
from django.contrib.auth.models import AbstractUser
from products.models import PokemonProduct


class User(AbstractUser):
    TRAINER_LEVELS = [
        ('rookie', 'Rookie Trainer'),
        ('intermediate', 'Intermediate Trainer'),
        ('expert', 'Expert Trainer'),
        ('master', 'Pokémon Master'),
    ]

    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    trainer_level = models.CharField(max_length=20, choices=TRAINER_LEVELS, default='rookie')
    wishlist = models.ManyToManyField(PokemonProduct, blank=True, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username
