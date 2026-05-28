from products.models import CardSet

# Get all sets that have a ptcgio_id mapping
# Print all set codes so we can enrich them
sets = CardSet.objects.exclude(era__isnull=True).order_by('era__code', 'release_date')
for s in sets:
    print(s.code)
