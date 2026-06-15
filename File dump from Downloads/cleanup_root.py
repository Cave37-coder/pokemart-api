import os, shutil

ROOT = r'C:\Users\texca\pokemart-api'
DUMP = r'C:\Users\texca\pokemart-api\File dump from Downloads'

KEEP = {
    'manage.py', 'requirements.txt', '.env', '.env.local', '.gitignore',
    'pokebulk_bible_v2.csv', 'pokebulk_bible_v3_balls.csv',
    'pokebulk_bible_v4.csv', 'pokebulk_bible_v5.csv',
    'set_mapping.py', 'sync_bible_to_db.py',
    'upload_images_to_cloudinary.py', 'find_wrong_n.py',
    'enrich_bulbapedia.py', 'enrich_only.py',
    'enrich_images_ptcgio.py', 'fetch_ball_variants.py',
    'populate_number.py', 'pokebulk_pricing.py',
    'build_tcgcsv_bible.py', 'wipe_cloudinary.py',
    'clear_cloudinary_urls.py', 'fix_total_cards.py',
    'railway.toml',
}

KEEP_FOLDERS = {
    'config', 'products', 'orders', 'payments', 'users',
    'media', 'inventory', '.vs', '196', '.git',
    'File dump from Downloads', '__pycache__',
}

moved = 0
skipped = 0

for item in os.listdir(ROOT):
    full = os.path.join(ROOT, item)
    
    # Skip folders we want to keep
    if os.path.isdir(full):
        if item not in KEEP_FOLDERS:
            dest = os.path.join(DUMP, item)
            shutil.move(full, dest)
            print(f'MOVED DIR: {item}')
            moved += 1
        continue
    
    # Skip files we want to keep
    if item in KEEP:
        skipped += 1
        continue
    
    # Move everything else
    dest = os.path.join(DUMP, item)
    if os.path.exists(dest):
        dest = os.path.join(DUMP, f'_dup_{item}')
    shutil.move(full, dest)
    print(f'MOVED: {item}')
    moved += 1

print(f'\nDone. Moved: {moved} | Kept: {skipped}')
