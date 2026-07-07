import pandas as pd

df = pd.read_csv('pokebulk_bible_v7.csv', low_memory=False)

print('Total rows:', len(df))
print()
print('is_card dtype:', df['is_card'].dtype)
print('is_card value counts (including NaN):')
print(df['is_card'].value_counts(dropna=False).head(10))
print()
print('variant_code dtype:', df['variant_code'].dtype)
print('variant_code value counts (including NaN), top 15:')
print(df['variant_code'].value_counts(dropna=False).head(15))
print()

# Isolate just PBL to compare
pbl = df[df['set_code'] == 'PBL']
print('PBL rows found by set_code:', len(pbl))
if len(pbl):
    print('PBL is_card values:', pbl['is_card'].unique())
    print('PBL variant_code values:', pbl['variant_code'].unique())
