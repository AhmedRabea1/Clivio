from django.contrib import admin
from .models import Branch, UserBranchAssignment


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'clinic', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'clinic')
    search_fields = ('name', 'clinic__name')


@admin.register(UserBranchAssignment)
class UserBranchAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'branch', 'assigned_by', 'assigned_at')
    list_filter = ('branch__clinic',)
    search_fields = ('user__name', 'user__email', 'branch__name')
