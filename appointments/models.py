from django.db import models
from django.conf import settings


class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    mobile_number = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=True)
    primary_patient = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='family_members',
    )
    pulse_packages = models.ManyToManyField(
        'accounts.PulsePackage', blank=True, related_name='patients'
    )
    area_packages = models.ManyToManyField(
        'accounts.AreaPackage', blank=True, related_name='patients'
    )
    medical_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_patients',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        ARRIVED   = 'arrived',   'Arrived'
        CANCELED  = 'canceled',  'Canceled'
        FINISHED  = 'finished',  'Finished'

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    doctor = models.ForeignKey(
        'accounts.Doctor',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reservations',
    )
    date_of_visit  = models.DateField()
    slot           = models.TimeField(null=True, blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_examination = models.BooleanField(default=False)
    discount       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_of_visit', 'slot']

    def __str__(self):
        return f'{self.patient.full_name} — {self.date_of_visit}'


class ReservationAttachment(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='reservation_attachments/', blank=True)
    url  = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_attachments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Attachment for {self.reservation} — {self.pk}'


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action     = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id  = models.CharField(max_length=50, blank=True)
    changes    = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} — {self.action} {self.model_name}'
