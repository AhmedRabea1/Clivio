import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=True)

django.setup()

from appointments.models import Patient

patients = Patient.objects.exclude(mobile_number__startswith='+')
total    = patients.count()
print(f'Found {total} patients without + prefix')

updated = 0
for patient in patients.iterator():
    patient.mobile_number = '+2' + patient.mobile_number
    patient.save(update_fields=['mobile_number'])
    updated += 1
    if updated % 500 == 0:
        print(f'  Updated {updated}/{total}...')

print(f'\nDone. Updated {updated} patients.')
