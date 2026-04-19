content = '''from django.db import models


class Era(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name}"


class CardSet(models.Model):
    era = models.ForeignKey(Era, on_delete=models.SET_NULL, null=True, related_name="sets")
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    symbol_url = models.URLField(max_length=500, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    total_cards = models.PositiveIntegerField(default=0)
    release_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class PokemonType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class PokemonProduct(models.Model):
    RARITY_CHOICES = [
        ("common", "Common"),
        ("uncommon", "Uncommon"),
        ("rare", "Rare"),
        ("holo_rare", "Holo Rare"),
        ("ultra_rare", "Ultra Rare"),
        ("illustration_rare", "Illustration Rare"),
        ("special_illustration_rare", "Special Illustration Rare"),
        ("hyper_rare", "Hyper Rare"),
        ("mega_hyper_rare", "Mega Hyper Rare"),
        ("mega_attack_rare", "Mega Attack Rare"),
        ("secret_rare", "Secret Rare"),
        ("legendary", "Legendary"),
        ("ace_spec", "ACE SPEC"),
        ("gold_star", "Gold Star"),
        ("shining", "Shining"),
    ]

    VARIANT_CODES = {
        "common": "N",
        "uncommon": "N",
        "rare": "N",
        "holo_rare": "H",
        "ultra_rare": "UR",
        "secret_rare": "SR",
        "legendary": "RA",
    }

    # Identifiers
    pb_id = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    sku = models.CharField(max_length=20, unique=True, blank=True)
    csv_sku = models.CharField(max_length=100, blank=True, db_index=True)
    tcgplayer_id = models.CharField(max_length=50, blank=True)
    gengar_id = models.CharField(max_length=50, blank=True)

    # Product details
    name = models.CharField(max_length=200)
    name_japanese = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    flavour_text = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    card_set = models.ForeignKey(CardSet, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    pokemon_types = models.ManyToManyField(PokemonType, blank=True, related_name="products")
    rarity = models.CharField(max_length=30, choices=RARITY_CHOICES, default="common")
    pokedex_number = models.PositiveIntegerField(null=True, blank=True)
    card_number = models.PositiveIntegerField(null=True, blank=True)
    variant_override = models.CharField(max_length=20, blank=True)

    # Card stats
    hp = models.PositiveIntegerField(null=True, blank=True)
    artist = models.CharField(max_length=200, blank=True)
    supertype = models.CharField(max_length=50, blank=True)
    card_subtypes = models.CharField(max_length=200, blank=True)
    weakness_type = models.CharField(max_length=50, blank=True)
    weakness_value = models.CharField(max_length=10, blank=True)
    resistance_type = models.CharField(max_length=50, blank=True)
    resistance_value = models.CharField(max_length=10, blank=True)
    retreat_cost = models.PositiveIntegerField(null=True, blank=True)

    # Ability
    ability_name = models.CharField(max_length=200, blank=True)
    ability_type = models.CharField(max_length=50, blank=True)
    ability_text = models.TextField(blank=True)

    # Attacks
    attack_1_name = models.CharField(max_length=200, blank=True)
    attack_1_damage = models.CharField(max_length=20, blank=True)
    attack_1_text = models.TextField(blank=True)
    attack_2_name = models.CharField(max_length=200, blank=True)
    attack_2_damage = models.CharField(max_length=20, blank=True)
    attack_2_text = models.TextField(blank=True)

    # Media
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True)
    image_small_url = models.URLField(max_length=500, blank=True)

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_normal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_holo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_reverse_holo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_first_edition = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pb_id} - {self.name}" if self.pb_id else self.name

    @property
    def in_stock(self):
        return self.stock > 0

    def generate_pb_id(self):
        if not self.card_set or not self.pokedex_number or not self.card_number:
            return ""
        era_code = self.card_set.era.code if self.card_set.era else "XX"
        set_code = self.card_set.code
        pokedex = str(self.pokedex_number).zfill(3)
        variant = self.variant_override or self.VARIANT_CODES.get(self.rarity, "N")
        card_num = str(self.card_number).zfill(3)
        return f"PB-{era_code}-{set_code}-{pokedex}-{variant}-{card_num}"

    def generate_sku(self):
        last = PokemonProduct.objects.order_by("id").last()
        next_num = (last.id + 1) if last else 1
        return f"PKB-{str(next_num).zfill(3)}"

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self.generate_sku()
        if not self.pb_id:
            self.pb_id = self.generate_pb_id()
        super().save(*args, **kwargs)
'''

with open("products/models.py", "w", encoding="utf-8") as f:
    f.write(content)
print("models.py written!")