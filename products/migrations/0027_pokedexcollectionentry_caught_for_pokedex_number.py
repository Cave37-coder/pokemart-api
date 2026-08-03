from django.db import migrations, models


def backfill_caught_for_pokedex_number(apps, schema_editor):
    """Every row that exists before this migration was written under the
    old "one product = one owned/unowned toggle, shared by every species it
    depicts" model. Michael's final call (2026-08-04): a catch only counts
    for the specific species it was caught for, so existing rows need an
    explicit value here rather than staying null. Defaulting to the
    product's PRIMARY pokedex_number preserves each existing row's original,
    single-count behaviour (this is exactly what every one of these rows
    counted as before pokedex_number_2 dual-crediting was ever added) --
    nobody silently loses credit for a Pokemon they already had marked
    caught, and nobody silently gains credit for the secondary species of a
    tag-team card they never explicitly caught from that species' own page.
    """
    PokedexCollectionEntry = apps.get_model('products', 'PokedexCollectionEntry')
    for entry in PokedexCollectionEntry.objects.select_related('product').filter(caught_for_pokedex_number__isnull=True):
        if entry.product.pokedex_number:
            entry.caught_for_pokedex_number = entry.product.pokedex_number
            entry.save(update_fields=['caught_for_pokedex_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0026_pokemonproduct_pokedex_number_2'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokedexcollectionentry',
            name='caught_for_pokedex_number',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_caught_for_pokedex_number, noop_reverse),
        migrations.RemoveConstraint(
            model_name='pokedexcollectionentry',
            name='unique_pokedex_entry',
        ),
        migrations.AddConstraint(
            model_name='pokedexcollectionentry',
            constraint=models.UniqueConstraint(fields=('user', 'product', 'caught_for_pokedex_number'), name='unique_pokedex_entry_per_species'),
        ),
    ]
