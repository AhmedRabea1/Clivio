from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class Configuration(models.Model):
    clinic = models.OneToOneField(
        'Clinic',
        on_delete=models.CASCADE,
        related_name='configuration',
    )
    clinic_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='attachments/', null=True, blank=True)
    hero_image = models.ImageField(upload_to='attachments/', null=True, blank=True)
    slogan = models.CharField(max_length=255, blank=True)
    sub_slogan = models.CharField(max_length=255, blank=True)
    footer_info = models.TextField(blank=True)
    linkedin_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    whatsapp_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7)    # hex e.g. #1ABC9C
    secondary_color = models.CharField(max_length=7, blank=True)
    slot_interval = models.PositiveIntegerField(default=30)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration'

    def __str__(self):
        return f'Config — {self.clinic.name}'


class Clinic(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='clinic_logos/', blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AssistantRole(models.Model):
    class RoleName(models.TextChoices):
        VIEW_INVENTORY    = 'view_inventory',    'View Inventory'
        EDIT_INVENTORY    = 'edit_inventory',    'Edit Inventory'
        ADD_INVENTORY     = 'add_inventory',     'Add Inventory'
        DELETE_INVENTORY  = 'delete_inventory',  'Delete Inventory'
        VIEW_CONFIG       = 'view_config',       'View Configurations'
        EDIT_CONFIG       = 'edit_config',       'Edit Configurations'
        VIEW_DOCTOR       = 'view_doctor',       'View Doctor'
        ADD_DOCTOR        = 'add_doctor',        'Add Doctor'
        EDIT_DOCTOR       = 'edit_doctor',       'Edit Doctor'
        DELETE_DOCTOR     = 'delete_doctor',     'Delete Doctor'
        VIEW_BRANCH       = 'view_branch',       'View Branch'
        ADD_BRANCH        = 'add_branch',        'Add Branch'
        EDIT_BRANCH       = 'edit_branch',       'Edit Branch'
        DELETE_BRANCH     = 'delete_branch',     'Delete Branch'
        VIEW_PATIENT      = 'view_patient',      'View Patient'
        ADD_PATIENT       = 'add_patient',       'Add Patient'
        EDIT_PATIENT      = 'edit_patient',      'Edit Patient'
        DELETE_PATIENT    = 'delete_patient',    'Delete Patient'
        VIEW_APPOINTMENT  = 'view_appointment',  'View Appointments'
        ADD_APPOINTMENT   = 'add_appointment',   'Add Appointments'
        EDIT_APPOINTMENT  = 'edit_appointment',  'Edit Appointments'
        DELETE_APPOINTMENT = 'delete_appointment', 'Delete Appointments'
        VIEW_ASSISTANT    = 'view_assistant',    'View Assistant'
        ADD_ASSISTANT     = 'add_assistant',     'Add Assistant'
        EDIT_ASSISTANT    = 'edit_assistant',    'Edit Assistant'
        DELETE_ASSISTANT  = 'delete_assistant',  'Delete Assistant'

    role_name = models.CharField(max_length=30, choices=RoleName.choices, unique=True)

    class Meta:
        ordering = ['role_name']

    def __str__(self):
        return self.get_role_name_display()


class Assistant(models.Model):
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='assistant_profile',
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assistants',
    )
    roles = models.ManyToManyField(
        AssistantRole,
        blank=True,
        related_name='assistants',
    )

    class Meta:
        ordering = ['-user__date_joined']

    def __str__(self):
        return self.user.name


class Doctor(models.Model):
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='doctor_profile',
    )
    specialty                = models.CharField(max_length=100, blank=True)
    price_per_examination    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_consultation   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-user__date_joined']

    def __str__(self):
        return f'Dr. {self.user.name}'


class DoctorMedicine(models.Model):
    doctor        = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='medicines')
    name          = models.CharField(max_length=255)
    concentration = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} {self.concentration}'


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        DOCTOR = 'doctor', 'Doctor'
        ASSISTANT = 'assistant', 'Assistant'

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DOCTOR)
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    phone = models.CharField(max_length=30, blank=True)
    specialty = models.CharField(max_length=100, blank=True, default='')
    role_title = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    token_version = models.PositiveIntegerField(default=0)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_role_display()})'

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_assistant(self):
        return self.role == self.Role.ASSISTANT


class Service(models.Model):
    class Category(models.TextChoices):
        INJECTABLE = 'injectable', 'Injectable'
        MACHINE    = 'machine',    'Machine'

    name        = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    category    = models.CharField(max_length=20, choices=Category.choices, default=Category.INJECTABLE)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Machine(models.Model):
    class Type(models.TextChoices):
        PULSES      = 'pulses',      'Pulses'
        DURATION    = 'duration',    'Duration'
        INJECTABLES = 'injectables', 'Injectables'
        SESSIONS    = 'sessions',    'Sessions'

    service                  = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='machines')
    name                     = models.CharField(max_length=255, unique=True)
    type                     = models.CharField(max_length=20, choices=Type.choices)
    price                    = models.DecimalField(max_digits=10, decimal_places=2)
    description              = models.TextField(blank=True, default='')
    latest_maintenance_date  = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PulsePackage(models.Model):
    pulses      = models.PositiveIntegerField()
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['pulses']

    def __str__(self):
        return f'{self.pulses} pulses'


class AreaPackage(models.Model):
    name        = models.CharField(max_length=255)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    class Type(models.TextChoices):
        VEIL     = 'veil',     'Veil'
        SYRINGE  = 'syringe',  'Syringe'

    service  = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='products')
    name     = models.CharField(max_length=255)
    type     = models.CharField(max_length=20, choices=Type.choices)
    quantity = models.PositiveIntegerField()
    volume   = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price    = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

