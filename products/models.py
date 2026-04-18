from django.db import models


class PokemonType(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Fire, Water, Grass etc.

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Cards, Plush, Booster Pack etc.
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class PokemonProduct(models.Model):
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('holo_rare', 'Holo Rare'),
        ('ultra_rare', 'Ultra Rare'),
        ('secret_rare', 'Secret Rare'),
        ('legendary', 'Legendary'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    pokemon_types = models.ManyToManyField(PokemonType, blank=True, related_name='products')
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    set_name = models.CharField(max_length=200, blank=True)  # Base Set, Sword & Shield etc.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0