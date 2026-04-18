from django.db import models


class Era(models.Model):
    code = models.CharField(max_length=10, unique=True)  # B7
    name = models.CharField(max_length=100)              # Sword & Shield

    def __str__(self):
        return f"{self.code} — {self.name}"


class CardSet(models.Model):
    era = models.ForeignKey(Era, on_delete=models.SET_NULL, null=True, related_name='sets')
    code = models.CharField(max_length=10, unique=True)  # SSH
    name = models.CharField(max_length=100)              # Sword & Shield Base

    def __str__(self):
        return f"{self.code} — {self.name}"


class PokemonType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
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

    VARIANT_CODES = {
        'common': 'S',
        'uncommon': 'S',
        'rare': 'S',
        'holo_rare': 'H',
        'ultra_rare': 'FA',
        'secret_rare': 'SR',
        'legendary': 'RA',
    }

    # Core identifiers
    pb_id       = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    sku         = models.CharField(max_length=20, unique=True, blank=True)
    tcgplayer_id = models.CharField(max_length=50, blank=True)
    gengar_id   = models.CharField(max_length=50, blank=True)

    # Product details
    name          = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    category      = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    card_set      = models.ForeignKey(CardSet, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    pokemon_types = models.ManyToManyField(PokemonType, blank=True, related_name='products')
    rarity        = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    pokedex_number = models.PositiveIntegerField(null=True, blank=True)  # 006
    card_number   = models.PositiveIntegerField(null=True, blank=True)   # 196 (set card number)
    variant_override = models.CharField(max_length=10, blank=True)       # override auto variant code

    # Pricing & stock
    price  = models.DecimalField(max_digits=10, decimal_places=2)
    stock  = models.PositiveIntegerField(default=0)
    image  = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pb_id} — {self.name}" if self.pb_id else self.name

    @property
    def in_stock(self):
        return self.stock > 0

    def generate_pb_id(self):
        if not self.card_set or not self.pokedex_number or not self.card_number:
            return ''
        era_code = self.card_set.era.code if self.card_set.era else 'XX'
        set_code = self.card_set.code
        pokedex = str(self.pokedex_number).zfill(3)
        variant = self.variant_override or self.VARIANT_CODES.get(self.rarity, 'S')
        card_num = str(self.card_number).zfill(3)
        return f"PB-{era_code}-{set_code}-{pokedex}-{variant}-{card_num}"

    def generate_sku(self):
        last = PokemonProduct.objects.order_by('id').last()
        next_num = (last.id + 1) if last else 1
        return f"PKB-{str(next_num).zfill(3)}"

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self.generate_sku()
        if not self.pb_id:
            self.pb_id = self.generate_pb_id()
        super().save(*args, **kwargs)