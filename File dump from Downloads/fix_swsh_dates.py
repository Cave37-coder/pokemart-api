import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import CardSet
dates = {
    'SWSH01': '2020-02-07',
    'SWSH02': '2020-05-01',
    'SWSH03': '2020-08-14',
    'SWSH04': '2020-11-13',
    'SWSH06': '2021-06-18',
    'SWSH07': '2021-08-27',
    'SWSH08': '2021-11-12',
    'SWSH09': '2022-02-25',
    'SWSH10': '2022-05-27',
    'SWSH11': '2022-09-09',
    'SWSH12': '2022-11-11',
    'CLB':    '2021-10-08',
    'CCC':    '2021-10-08',
    'PR-SWSH':'2020-02-07',
}
for code, date in dates.items():
    updated = CardSet.objects.filter(code=code).update(release_date=date)
    print(code + ' -> ' + date + ' (' + str(updated) + ' updated)')
