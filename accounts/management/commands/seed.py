"""
Management command to seed the first Clinic and Super Admin user.

Usage:
    python manage.py seed
    python manage.py seed --clinic "My Clinic" --email admin@example.com --password secret123
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from accounts.models import Clinic, User


class Command(BaseCommand):
    help = 'Seed the database with the first Clinic and Super Admin user.'

    def add_arguments(self, parser):
        parser.add_argument('--clinic', type=str, default='Clivio Dermatology', help='Clinic name')
        parser.add_argument('--email', type=str, default='admin@clivio.com', help='Super admin email')
        parser.add_argument('--name', type=str, default='Super Admin', help='Super admin full name')
        parser.add_argument('--password', type=str, default='admin123', help='Super admin password')
        parser.add_argument('--force', action='store_true', help='Re-create even if data exists')

    def handle(self, *args, **options):
        clinic_name = options['clinic']
        email = options['email']
        name = options['name']
        password = options['password']
        force = options['force']

        # --- Clinic ---
        slug = slugify(clinic_name)
        clinic, clinic_created = Clinic.objects.get_or_create(
            slug=slug,
            defaults={
                'name': clinic_name,
                'is_active': True,
            }
        )

        if clinic_created:
            self.stdout.write(self.style.SUCCESS(f'  [+] Clinic created: "{clinic.name}" (slug: {slug})'))
        else:
            self.stdout.write(self.style.WARNING(f'  [~] Clinic already exists: "{clinic.name}"'))
            if not force:
                self.stdout.write('      Use --force to overwrite. Skipping clinic creation.')

        # --- Super Admin User ---
        if User.objects.filter(email=email).exists():
            if force:
                User.objects.filter(email=email).delete()
                self.stdout.write(self.style.WARNING(f'  [~] Existing user {email} deleted (--force).'))
            else:
                self.stdout.write(self.style.WARNING(f'  [~] User already exists: {email}'))
                self.stdout.write('      Use --force to recreate. Skipping user creation.')
                self._print_summary(clinic, email)
                return

        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=User.Role.SUPER_ADMIN,
            clinic=clinic,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

        self.stdout.write(self.style.SUCCESS(f'  [+] Super Admin created: {user.name} <{user.email}>'))
        self._print_summary(clinic, email, password)

    def _print_summary(self, clinic, email, password=None):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('  Seed complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'  Clinic : {clinic.name}')
        self.stdout.write(f'  Login  : {email}')
        if password:
            self.stdout.write(f'  Pass   : {password}')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
