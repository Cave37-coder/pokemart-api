import pandas as pd

df = pd.read_csv('pokebulk_bible_v6.csv', low_memory=False)

# Lost Origin rows - matching by set name or tcgcsv group id, adjust column name if needed
lor = df[df['final_set_name'].astype(str).str.contains('Lost Origin', case=False, na=False)] if 'final_set_name' in df.columns else df[df.astype(str).apply(lambda r: r.str.contains('Lost Origin', case=False, na=False).any(), axis=1)]

print(f"Total Bible rows matching 'Lost Origin': {len(lor)}")
print(f"Columns available: {list(df.columns)}\n")

if 'card_number' in lor.columns and 'variant_code' in lor.columns:
    by_num = lor.groupby('card_number')['variant_code'].apply(lambda x: sorted(set(x.dropna()))).reset_index()
    print("Variant codes per card_number (first 15):")
    for _, row in by_num.head(15).iterrows():
        print(f"  #{row['card_number']}: {row['variant_code']}")

    # Count how many commons/uncommons have BOTH N and RH per Bible data
    if 'final_rarity' in lor.columns:
        commons_uncommons = lor[lor['final_rarity'].astype(str).str.lower().isin(['common', 'uncommon'])]
        cu_by_num = commons_uncommons.groupby('card_number')['variant_code'].apply(lambda x: set(x.dropna()))
        both = sum(1 for v in cu_by_num if 'N' in v and 'RH' in v)
        only_one = sum(1 for v in cu_by_num if len(v) == 1)
        print(f"\nCommons/Uncommons with BOTH N+RH in Bible: {both}")
        print(f"Commons/Uncommons with only ONE variant in Bible: {only_one}")
        print(f"Total distinct common/uncommon card numbers: {len(cu_by_num)}")
else:
    print("Expected columns 'card_number'/'variant_code' not found - print first row to inspect:")
    print(lor.iloc[0].to_dict() if len(lor) > 0 else "no rows matched")
