import os, sys, django

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DB_NAME"]     = "railway"
os.environ["DB_USER"]     = "postgres"
os.environ["DB_PASSWORD"] = "dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm"
os.environ["DB_HOST"]     = "nozomi.proxy.rlwy.net"
os.environ["DB_PORT"]     = "59678"

sys.path.insert(0, r"C:\Users\texca\pokemart-api")
django.setup()

from django.core.management import call_command
call_command("sync_prices", delay=1)
