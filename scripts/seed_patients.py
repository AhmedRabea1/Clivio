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
from appointments.models import Patient

EXCEL_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jolie Derm Center.xlsx')
SHEET_NAME   = 'بيانات_المرضى'
DATE_OF_BIRTH = '1990-01-01'

wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
ws = wb[SHEET_NAME]

created_count  = 0
skipped_count  = 0
invalid_count  = 0

for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0:
        continue  # skip header

    full_name = str(row[0]).strip() if row[0] else ''
    mobile    = str(row[1]).strip() if row[1] else ''

    if not full_name or not mobile or full_name == 'None' or mobile == 'None':
        invalid_count += 1
        continue

    # Clean mobile — remove spaces/dashes
    mobile = mobile.replace(' ', '').replace('-', '')
    if not mobile.startswith('+'):
        mobile = '+2' + mobile

    # Split name: first word = first_name, rest = last_name
    parts      = full_name.split()
    first_name = parts[0]
    last_name  = ' '.join(parts[1:]) if len(parts) > 1 else parts[0]

    if Patient.objects.filter(mobile_number=mobile, is_primary=True).exists():
        skipped_count += 1
        continue

    Patient.objects.create(
        first_name=first_name,
        last_name=last_name,
        mobile_number=mobile,
        date_of_birth=DATE_OF_BIRTH,
        medical_notes='',
        is_primary=True,
    )
    created_count += 1

    if created_count % 500 == 0:
        print(f'  Created {created_count} patients so far...')

wb.close()
print(f'\nDone. Created: {created_count} | Skipped (duplicate): {skipped_count} | Invalid rows: {invalid_count}')
