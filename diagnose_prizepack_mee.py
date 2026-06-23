from products.models import PokemonProduct, CardSet

# --- 1. Find the PRIZEPACK set ---
pp = CardSet.objects.filter(code__icontains='PRIZE').first()
if not pp:
    print("!! No CardSet with code containing 'PRIZE' found — check the exact code in admin.")
else:
    print(f"PRIZEPACK set found: code={pp.code!r} name={pp.name!r} id={pp.id}")

    # --- 2. Products in PRIZEPACK whose name looks like it belongs to MEE instead ---
    mee_like = PokemonProduct.objects.filter(card_set=pp, name__icontains=' - MEE').order_by('card_number')
    print(f"\nProducts in PRIZEPACK with ' - MEE' in the name: {mee_like.count()}")
    for p in mee_like[:60]:
        print(f"  id={p.id:<6} pb_id={p.pb_id!r:<20} card_number={p.card_number!r:<6} tcgplayer_id={p.tcgplayer_id!r:<10} name={p.name!r}")

    # --- 3. Does a separate MEE set already exist? ---
    mee_set = CardSet.objects.filter(code='MEE').first()
    print(f"\nSeparate 'MEE' CardSet exists already? {'YES — id=' + str(mee_set.id) + ', name=' + repr(mee_set.name) if mee_set else 'NO'}")

    # --- 4. Sanity check: how many genuine PRIZEPACK products (no MEE suffix) ---
    genuine = PokemonProduct.objects.filter(card_set=pp).exclude(name__icontains=' - MEE').count()
    total = PokemonProduct.objects.filter(card_set=pp).count()
    print(f"\nTotal products currently under PRIZEPACK: {total}")
    print(f"  Genuine PRIZEPACK (no MEE suffix): {genuine}")
    print(f"  Suspected misassigned MEE: {mee_like.count()}")

    # --- 5. Same check for WCD, while we're at it ---
    from django.db.models import Count
    wcd = CardSet.objects.filter(code__icontains='WCD').first()
    if wcd:
        wcd_total = PokemonProduct.objects.filter(card_set=wcd).count()
        dupe_numbers = (PokemonProduct.objects.filter(card_set=wcd)
                         .values('card_number')
                         .annotate(n=Count('id'))
                         .filter(n__gt=1))
        print(f"\nWCD set: total products={wcd_total}, card_numbers with duplicates={dupe_numbers.count()}")
        for d in dupe_numbers[:20]:
            print(f"  card_number={d['card_number']!r} appears {d['n']} times")
    else:
        print("\nNo WCD CardSet found yet (expected, since WCD sync is still deferred).")
