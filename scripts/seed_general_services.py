import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=True)

django.setup()

from django.conf import settings
print('DB:', settings.DATABASES['default'].get('NAME') or settings.DATABASES['default'].get('HOST'))

import openpyxl
from accounts.models import User, Doctor, GeneralService

EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jolie Derm Center.xlsx')

# Clinic-In doctors
CLINIC_IN_EMAILS = [
    'mohamedmagdy@joliderm.info',
    'amrsweidan@joliderm.info',
    'mahy@joliderm.info',
    'rehab@joliderm.info',
]

# Clinic-Out doctors
CLINIC_OUT_EMAILS = [
    'aliaatef@gmail.com',
    'lailaibrahim@gmail.com',
]

# Read services from Excel
wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
ws = wb['Services']

services = []
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0:
        continue  # skip header
    name, clinic_in, clinic_out = row[0], row[1], row[2]
    if not name:
        continue
    services.append({
        'name':       str(name).strip(),
        'clinic_in':  clinic_in or 0,
        'clinic_out': clinic_out or 0,
    })

wb.close()
print(f'Found {len(services)} services')

created = 0
skipped = 0

for email in CLINIC_IN_EMAILS + CLINIC_OUT_EMAILS:
    try:
        user   = User.objects.get(email=email)
        doctor = Doctor.objects.get(user=user)
    except (User.DoesNotExist, Doctor.DoesNotExist):
        print(f'Doctor not found: {email}')
        continue

    is_clinic_in = email in CLINIC_IN_EMAILS
    fee_key      = 'clinic_in' if is_clinic_in else 'clinic_out'

    for svc in services:
        _, was_created = GeneralService.objects.get_or_create(
            doctor=doctor,
            name=svc['name'],
            defaults={
                'clinic_fees': svc[fee_key],
            }
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    print(f'Done: {user.name} ({"Clinic-In" if is_clinic_in else "Clinic-Out"}) — {len(services)} services')

print(f'\nTotal created: {created} | Skipped (already exists): {skipped}')
