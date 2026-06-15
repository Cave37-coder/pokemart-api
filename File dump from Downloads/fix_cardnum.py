with open('products/management/commands/sync_tcgcsv.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'card_number = _get_number_from_extended(extended)',
    '''card_number = _get_number_from_extended(extended)
        if card_number and '/' in str(card_number):
            card_number = str(card_number).split('/')[0]'''
)

with open('products/management/commands/sync_tcgcsv.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
