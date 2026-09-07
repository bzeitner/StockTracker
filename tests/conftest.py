import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stocktracker_web.settings")
django.setup()
