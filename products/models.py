from django.conf import settings
from django.db import models


class Era(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    # Michael, 2026-08-08: "replace the simple Era labels with the actual
    # Era Logo" on the Checklist page's Overview grid -- distinct from
    # CardSet.logo_url (one specific set's box art), this is a single
    # wordmark/logo representing the whole era (e.g. "Scarlet & Violet",
    # "Sword & Shield"). Blank by default -- Michael is sourcing/pasting
    # these himself via admin; the frontend falls back to the existing
    # coloured text pill for any era left blank.
    logo_url = models.URLField(max_length=500, blank=True)

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
    regulation_mark = models.CharField(max_length=5, blank=True, default='')
    checklist_pdf = models.FileField(upload_to='checklists/', blank=True, null=True)
    checklist_xlsx = models.FileField(upload_to='checklists/', blank=True, null=True)
    tcgio_code = models.CharField(max_length=20, blank=True, default='', help_text='pokemontcg.io API set code e.g. swsh1. Used for API lookups only, never in filenames or paths.')
    bulba_code = models.CharField(max_length=20, blank=True, default='', help_text='Official Bulbapedia set abbreviation e.g. SSH')

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

    CONDITION_CHOICES = [
        ('NM', 'Near Mint'),
        ('LP', 'Lightly Played'),
        ('MP', 'Moderately Played'),
        ('HP', 'Heavily Played'),
        ('DMG', 'Damaged'),
    ]

    CONDITION_MULTIPLIERS = {
        'NM': 1.00,
        'LP': 0.80,
        'MP': 0.60,
        'HP': 0.35,
        'DMG': 0.20,
    }

    # Identifiers
    pb_id = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    sku = models.CharField(max_length=20, unique=True, blank=True)
    csv_sku = models.CharField(max_length=100, blank=True, db_index=True)
    tcgplayer_id = models.CharField(max_length=50, blank=True)
    tcgcsv_product_id = models.IntegerField(null=True, blank=True, db_index=True)
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
    # Michael, 2026-08-02: "the TAG Team cards with 2 Pokemon, must have
    # Pokedex numbers added" -- cards like "Pikachu & Zekrom-GX" depict two
    # separate Pokemon. Deliberately a SECOND nullable field rather than
    # restructuring pokedex_number into a list: every existing filter, the
    # Pokedex pages, and the ?pokedex= query param all assume a single int
    # and keep working unchanged for the ~99% of cards with one Pokemon.
    # Only tag-team/multi-Pokemon cards ever get this set.
    pokedex_number_2 = models.PositiveIntegerField(null=True, blank=True)
    card_number = models.PositiveIntegerField(null=True, blank=True)
    number = models.CharField(max_length=20, blank=True)
    variant_override = models.CharField(max_length=20, blank=True)
    variant_sort = models.IntegerField(default=9)
    condition = models.CharField(max_length=3, choices=CONDITION_CHOICES, default='NM')
    legal_standard = models.BooleanField(null=True, blank=True)
    legal_expanded = models.BooleanField(null=True, blank=True)
    legal_unlimited = models.BooleanField(default=True)
    # Per-card regulation mark (e.g. "H", "I", "J"). Takes priority over
    # card_set.regulation_mark when computing Standard legality -- confirmed
    # 2026-06-20 that regulation mark is NOT always uniform across an entire
    # set (pokemontcg.io exposes it per individual card, not per set), so
    # the set-level field alone is an unsafe approximation for SV/MEG-era
    # cards in particular. Blank means "no per-card override known yet,
    # fall back to card_set.regulation_mark".
    regulation_mark = models.CharField(max_length=5, blank=True, default='')

    # Comma-separated Prize Pack series numbers this exact card+variant has
    # appeared in, e.g. "7,8,9" — a card can legitimately appear in multiple
    # series since the official Pokemon.com checklists overlap. Blank means
    # "not a Prize Pack reprint, or not yet matched against the official lists".
    prize_pack_series = models.CharField(max_length=50, blank=True, default='')

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
    price_pokeball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_masterball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_friendball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_loveball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_quickball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_duskball = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    # Separate from `stock` above on purpose: `stock` drives what's live and
    # purchasable on the website (via Cart/Order/ManualInvoice). pos_stock is
    # a completely independent counter, incremented only by Buy Orders in
    # the standalone POS (pokebulk-pos) -- physical cards bought at the
    # counter that haven't been sorted/verified/listed yet. Nothing here
    # ever flows into the real `stock` field automatically; moving pos_stock
    # into live `stock` is a deliberate, separate manual step.
    pos_stock = models.PositiveIntegerField(
        default=0,
        help_text="Physical stock acquired via the POS Buy screen. Separate from live website stock -- does not affect what's purchasable on the site."
    )
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


class ChecklistEntry(models.Model):
    """
    One row = one customer has ticked one card as owned, on the Checklists
    page. Existence of the row is the "checked" state -- unchecking a box
    just deletes the row, checking one creates it. This replaces the old
    localStorage['pb_cl_'+code] behaviour, which lived only in one browser
    and vanished the moment a customer's session/device changed. Tying it
    to the user account instead is also what makes any future
    sharing/community features (comparing collections between customers)
    possible -- can't share what's trapped in one browser.

    card_set/card_key intentionally mirror the frontend's existing
    identifiers (CardSet.code, and the "001/217_N" style key already used
    in the Checklists page) rather than a FK straight to PokemonProduct --
    a checklist entry should survive even if the underlying product row
    gets resynced/replaced by a catalog sync script.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checklist_entries")
    card_set = models.CharField(max_length=20, help_text="CardSet.code, e.g. 'ASC', 'TK22'")
    card_key = models.CharField(max_length=64, help_text="Checklist item key, e.g. '001/217_N'")
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "card_set", "card_key"], name="unique_checklist_entry"),
        ]
        indexes = [
            models.Index(fields=["user", "card_set"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.card_set}/{self.card_key}"


class SetCompletionEvent(models.Model):
    """
    One row = one customer hit 100% on one tier of one set, for the first
    time. Powers the Wall of Honour (see products/completion.py for the
    tier definitions and the actual percentage math). Created automatically
    by checklist_toggle the moment a check pushes a tier to complete --
    never created directly, never updated after creation, so the
    completed_at timestamp always reflects the FIRST time they got there
    even if they later uncheck something and re-complete it.

    card_set mirrors ChecklistEntry's pattern (CardSet.code as a plain
    string, not an FK) for the same reason: a completion record should
    survive a catalog resync.
    """
    TIER_CHOICES = [
        ("broke_base", "Broke Base"),
        ("base_set", "Base Set"),
        ("special_set_base", "Special Set Base"),
        ("master_set", "Master Set"),
        ("complete_set", "Complete Set"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="set_completions")
    card_set = models.CharField(max_length=20, help_text="CardSet.code, e.g. 'ASC', 'TK22'")
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "card_set", "tier"], name="unique_set_completion_event"),
        ]
        indexes = [
            models.Index(fields=["card_set", "tier"]),
            models.Index(fields=["-completed_at"]),
        ]
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.user.username}: {self.card_set} -- {self.get_tier_display()}"


class PokedexCollectionEntry(models.Model):
    """
    One row = one customer has marked one exact card/variant (a single
    PokemonProduct row) as owned in their personal Pokedex collection.

    Michael, 2026-08-02: deliberately a SEPARATE feature from ChecklistEntry
    / set completion -- "I want to be able to select the card or Variant of
    Card, add to a separate PokeDex collection, not tie in into Checklist,
    that was the one issue I had with pkmn.gg version. I want to track my
    Poke Dex separate to rest of my collection." So a Pokemon "counts" as
    caught on the Pokedex the moment ANY one of its cards has a row here,
    independent of whatever's checked on that card's set Checklist -- the
    two features share no data.

    Uses a direct FK to PokemonProduct (unlike ChecklistEntry's string-based
    card_set/card_key) since a Pokedex entry is inherently about one exact
    physical print a customer says they own, not an abstract per-set card
    slot that needs to survive a catalog resync the same way a checklist
    tick does.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pokedex_entries")
    product = models.ForeignKey(PokemonProduct, on_delete=models.CASCADE, related_name="pokedex_entries")
    added_at = models.DateTimeField(auto_now_add=True)
    # Michael, 2026-08-04: tag-team cards ("Pheromosa & Buzzwole GX") depict
    # TWO Pokemon on one physical card/product row. Final decision after
    # testing the "both species always get credit" behaviour live: "if you
    # select a card on a page for a pokemon, that selection must be for that
    # pokemon only, not bleed into the other pokemon on the tag team card" --
    # i.e. catching this card from Pheromosa's page credits ONLY Pheromosa;
    # catching the SAME physical card again from Buzzwole's page is a
    # separate, independent action that credits Buzzwole. This field records
    # which of the (up to two) species this particular catch was for, so the
    # same product can have zero, one, or two rows for the same user -- one
    # per species it's been caught for. Null only for rows written before
    # this field existed; those were backfilled to the product's primary
    # pokedex_number in the migration that added this field.
    caught_for_pokedex_number = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product", "caught_for_pokedex_number"], name="unique_pokedex_entry_per_species"),
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.product.name} (product #{self.product_id})"
