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


class Doctor(models.Model):
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='doctor_profile',
    )
    specialty = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-user__date_joined']

    def __str__(self):
        return f'Dr. {self.user.name}'


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
