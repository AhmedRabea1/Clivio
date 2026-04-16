from django.contrib import admin
from .models import Patient, AuditLog


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'clinic', 'mobile_number', 'clinic_location', 'doctor', 'status', 'visit_date')
    list_filter = ('clinic', 'status', 'visit_date')
    search_fields = ('first_name', 'last_name', 'mobile_number')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id')
    list_filter = ('action', 'model_name')
    search_fields = ('user__name', 'model_name', 'object_id')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'changes', 'ip_address', 'timestamp')
