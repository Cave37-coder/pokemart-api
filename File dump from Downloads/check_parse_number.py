"""
Check what _parse_number does with TG numbers in the actual installed command
Run: python manage.py shell --command="exec(open('check_parse_number.py').read())"
"""
from products.management.commands.sync_tcgcsv import _parse_number

test_numbers = ['TG01/TG30', 'TG01', 'SV1/SV94', 'GG19/GG70', 'RC1/RC32', '001/217', '1']
for n in test_numbers:
    result = _parse_number(n)
    print(f"  _parse_number('{n}') = {result}")
