from django.db import models
from django.conf import settings


class Branch(models.Model):
    clinic = models.ForeignKey(
        'accounts.Clinic',
        on_delete=models.CASCADE,
        related_name='branches',
    )
    name = models.CharField(max_length=60)
    city = models.CharField(max_length=100, default='')
    area = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'branches'
        unique_together = ('clinic', 'name')

    def __str__(self):
        return f'{self.name} — {self.clinic.name}'


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
