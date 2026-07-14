import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User, Doctor
from branches.models import Branch, DoctorSchedule

BRANCH_ID = 1
PASSWORD  = 'admin123'

DOCTORS = [
    {'name': 'Mohamed Magdy',    'email': 'mohamedmagdy@joliderm.info'},
    {'name': 'Amr Sweidan',      'email': 'amrsweidan@joliderm.info'},
    {'name': 'Mahy El Bassyouni','email': 'mahy@joliderm.info'},
    {'name': 'Naglaa Salem',     'email': 'nagla@joliderm.info'},
    {'name': 'Aliaa Atef',       'email': 'aliaatef@gmail.com'},
    {'name': 'Lamia Ibrahim',    'email': 'lailaibrahim@gmail.com'},
]

# All days: 0=Saturday to 6=Friday
ALL_DAYS   = [0, 1, 2, 3, 4, 5, 6]
FROM_TIME  = '12:00'
TO_TIME    = '23:59'

branch = Branch.objects.get(pk=BRANCH_ID)

for doc in DOCTORS:
    user, created = User.objects.get_or_create(
        email=doc['email'],
        defaults={
            'name': doc['name'],
            'role': User.Role.DOCTOR,
            'is_active': True,
        }
    )
    if created:
        user.set_password(PASSWORD)
        user.save()
        print(f'Created user: {doc["name"]}')
    else:
        print(f'User already exists: {doc["name"]}')

    doctor, _ = Doctor.objects.get_or_create(user=user)

    for day in ALL_DAYS:
        DoctorSchedule.objects.get_or_create(
            user=user,
            branch=branch,
            day=day,
            defaults={
                'from_time': FROM_TIME,
                'to_time':   TO_TIME,
            }
        )

    print(f'  Schedule set for all days 12:00 PM - 11:59 PM — branch {branch.name}')

print('\nDone.')
