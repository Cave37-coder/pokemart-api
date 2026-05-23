with open('products/management/commands/sync_tcgcsv.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '''card_number = _get_number_from_extended(extended)
        if card_number and '/' in str(card_number):
            card_number = str(card_number).split('/')[0]''',
    '''card_number = _get_number_from_extended(extended)
        if card_number and '/' in str(card_number):
            card_number = str(card_number).split('/')[0]
        try:
            card_number = int(card_number) if card_number else None
        except (ValueError, TypeError):
            stats['non_card'] += 1
            continue'''
)

with open('products/management/commands/sync_tcgcsv.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
