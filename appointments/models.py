from django.db import models
from django.conf import settings


class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
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
    date_of_visit    = models.DateField()
    slot             = models.TimeField(null=True, blank=True)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_examination   = models.BooleanField(default=False)
    discount         = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    general_services      = models.ManyToManyField(
        'accounts.GeneralService', blank=True, related_name='reservations'
    )
    general_service_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_of_visit', 'slot']

    def __str__(self):
        return f'{self.patient.full_name} — {self.date_of_visit}'


class ReservationGeneralServicePrice(models.Model):
    reservation      = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='general_service_prices')
    general_service  = models.ForeignKey('accounts.GeneralService', on_delete=models.CASCADE)
    price            = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('reservation', 'general_service')

    def __str__(self):
        return f'{self.reservation_id} — {self.general_service.name}: {self.price}'


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending',        'Pending'
        PARTIAL = 'partial',        'Partial'
        PAID    = 'paid',           'Paid'
        FREE    = 'free',  'Free'

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    patient     = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    subtotal    = models.DecimalField(max_digits=10, decimal_places=2)
    discount    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total       = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at  = models.DateTimeField(auto_now_add=True)

    @property
    def remaining(self):
        from decimal import Decimal
        return max(Decimal('0'), self.total - self.paid_amount)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Invoice {self.pk} — {self.reservation or self.patient}'


class InvoicePayment(models.Model):
    class PaymentType(models.IntegerChoices):
        INSTAPAY = 1, 'Instapay'
        CASH     = 2, 'Cash'
        VISA     = 3, 'Visa'

    invoice      = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.IntegerField(choices=PaymentType.choices)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Payment {self.pk} — {self.get_payment_type_display()} {self.amount}'


class PatientPulsePackage(models.Model):
    patient          = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pulse_package_records')
    package          = models.ForeignKey('accounts.PulsePackage', on_delete=models.CASCADE, related_name='patient_records')
    total_pulses     = models.PositiveIntegerField()
    remaining_pulses = models.PositiveIntegerField()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient} — {self.package} ({self.remaining_pulses}/{self.total_pulses})'


class PatientAreaPackage(models.Model):
    patient    = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='area_package_records')
    package    = models.ForeignKey('accounts.AreaPackage', on_delete=models.CASCADE, related_name='patient_records')
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient} — {self.package} ({"used" if self.is_used else "active"})'


class ReservationAttachment(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='reservation_attachments/', blank=True)
    url  = models.URLField(blank=True)
    name = models.CharField(max_length=255, blank=True)
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


class ZoneDefinition(models.Model):
    zone_id    = models.IntegerField(unique=True)
    zone_label = models.CharField(max_length=100)

    class Meta:
        ordering = ['zone_id']

    def __str__(self):
        return f'{self.zone_id} — {self.zone_label}'


class DermaFaceMapping(models.Model):
    reservation  = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='derma_mappings')
    patient      = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='derma_mappings')
    mapping_type = models.CharField(max_length=20, default='face')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'DermaMapping {self.pk} — {self.reservation}'


class DermaFaceMappingZone(models.Model):
    mapping    = models.ForeignKey(DermaFaceMapping, on_delete=models.CASCADE, related_name='zones')
    zone_id    = models.IntegerField()
    zone_label = models.CharField(max_length=100)

    class Meta:
        ordering = ['zone_id']

    def __str__(self):
        return f'Zone {self.zone_label}'


class DermaFaceMappingZoneService(models.Model):
    zone    = models.ForeignKey(DermaFaceMappingZone, on_delete=models.CASCADE, related_name='zone_services')
    service = models.ForeignKey('accounts.Service', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'ZoneService {self.zone} — {self.service}'


class DermaFaceMappingLine(models.Model):
    zone_service = models.ForeignKey(DermaFaceMappingZoneService, on_delete=models.CASCADE, related_name='lines')
    line_type    = models.CharField(max_length=20)           # product | machine
    product      = models.ForeignKey('accounts.Product', on_delete=models.SET_NULL, null=True, blank=True)
    product_type = models.CharField(max_length=50, blank=True)  # syringe | veil
    quantity     = models.IntegerField(null=True, blank=True)
    volume_ml    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    machine      = models.ForeignKey('accounts.Machine', on_delete=models.SET_NULL, null=True, blank=True)
    machine_type = models.CharField(max_length=50, blank=True)  # duration | pulses | sessions | injectables
    minutes      = models.IntegerField(null=True, blank=True)
    pulses       = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'Line {self.line_type}'


class BodyZoneDefinition(models.Model):
    zone_id    = models.IntegerField(unique=True)
    zone_label = models.CharField(max_length=100)

    class Meta:
        ordering = ['zone_id']

    def __str__(self):
        return f'{self.zone_id} — {self.zone_label}'


class DermaBodyMapping(models.Model):
    reservation  = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='body_mappings')
    patient      = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='body_mappings')
    mapping_type = models.CharField(max_length=20, default='body')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'BodyMapping {self.pk} — {self.reservation}'


class DermaBodyMappingZone(models.Model):
    mapping    = models.ForeignKey(DermaBodyMapping, on_delete=models.CASCADE, related_name='zones')
    zone_id    = models.IntegerField()
    zone_label = models.CharField(max_length=100)

    class Meta:
        ordering = ['zone_id']

    def __str__(self):
        return f'Zone {self.zone_label}'


class DermaBodyMappingZoneService(models.Model):
    zone    = models.ForeignKey(DermaBodyMappingZone, on_delete=models.CASCADE, related_name='zone_services')
    service = models.ForeignKey('accounts.Service', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'ZoneService {self.zone} — {self.service}'


class DermaBodyMappingLine(models.Model):
    zone_service = models.ForeignKey(DermaBodyMappingZoneService, on_delete=models.CASCADE, related_name='lines')
    line_type    = models.CharField(max_length=20)
    product      = models.ForeignKey('accounts.Product', on_delete=models.SET_NULL, null=True, blank=True)
    product_type = models.CharField(max_length=50, blank=True)
    quantity     = models.IntegerField(null=True, blank=True)
    volume_ml    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    machine      = models.ForeignKey('accounts.Machine', on_delete=models.SET_NULL, null=True, blank=True)
    machine_type = models.CharField(max_length=50, blank=True)
    minutes      = models.IntegerField(null=True, blank=True)
    pulses       = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'Line {self.line_type}'


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
