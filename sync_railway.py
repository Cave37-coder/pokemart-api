import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DB_NAME"] = "railway"
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm"
os.environ["DB_HOST"] = "nozomi.proxy.rlwy.net"
os.environ["DB_PORT"] = "59678"
sys.path.insert(0, os.getcwd())
django.setup()
from django.core.management import call_command
call_command("sync_prices", xlsx="all_tcg_products_20260518_1456.xlsx")
