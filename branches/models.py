from django.db import models
from django.conf import settings


class Branch(models.Model):
    clinic = models.ForeignKey(
        'accounts.Clinic',
        on_delete=models.CASCADE,
        related_name='branches',
    )
    DAYS = [
        (0, 'Saturday'),
        (1, 'Sunday'),
        (2, 'Monday'),
        (3, 'Tuesday'),
        (4, 'Wednesday'),
        (5, 'Thursday'),
        (6, 'Friday'),
    ]

    name = models.CharField(max_length=60)
    address = models.TextField()
    phone = models.CharField(max_length=30)
    from_time = models.TimeField(null=True, blank=True)
    to_time = models.TimeField(null=True, blank=True)
    vacation_days = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'branches'
        unique_together = ('clinic', 'name')

    def __str__(self):
        return f'{self.name} — {self.clinic.name}'


class DoctorSchedule(models.Model):
    DAYS = [
        (0, 'Saturday'), (1, 'Sunday'), (2, 'Monday'),
        (3, 'Tuesday'), (4, 'Wednesday'), (5, 'Thursday'), (6, 'Friday'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='doctor_schedules',
    )
    day = models.PositiveSmallIntegerField(choices=DAYS)
    from_time = models.TimeField()
    to_time = models.TimeField()

    class Meta:
        ordering = ['branch', 'day', 'from_time']

    def __str__(self):
        return f'{self.user.name} @ {self.branch.name} — {self.get_day_display()}'


class UserBranchAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='branch_assignments',
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='user_assignments',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_given',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'branch')
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.user.name} → {self.branch.name}'
