from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.shortcuts import redirect

# API imports
from accounts.api_views import (
    api_login, api_refresh, api_logout,
    api_forgot_password, api_reset_password,
    api_users, api_user_detail, api_user_status, api_user_branches,
    api_configuration, api_public_configuration,
    api_doctors, api_doctor_detail, api_doctor_status,
)
from branches.api_views import (
    api_branches, api_branch_detail, api_branch_status, api_branch_users,
    api_public_branches,
)

api_urlpatterns = [
    # Auth
    path('auth/login',           api_login,           name='api_login'),
    path('auth/refresh',         api_refresh,         name='api_refresh'),
    path('auth/logout',          api_logout,          name='api_logout'),
    path('auth/forgot-password', api_forgot_password, name='api_forgot_password'),
    path('auth/reset-password',  api_reset_password,  name='api_reset_password'),

    # Users
    path('users',                    api_users,          name='api_users'),
    path('users/<int:pk>',           api_user_detail,    name='api_user_detail'),
    path('users/<int:pk>/status',    api_user_status,    name='api_user_status'),
    path('users/<int:pk>/branches',  api_user_branches,  name='api_user_branches'),

    # Doctors
    path('doctors',                  api_doctors,         name='api_doctors'),
    path('doctors/<int:pk>',         api_doctor_detail,   name='api_doctor_detail'),
    path('doctors/<int:pk>/status',  api_doctor_status,   name='api_doctor_status'),

    # Configuration
    path('configuration',        api_configuration,        name='api_configuration'),
    path('public/configuration', api_public_configuration, name='api_public_configuration'),
    path('public/branches',      api_public_branches,      name='api_public_branches'),

    # Branches
    path('branches',                      api_branches,       name='api_branches'),
    path('branches/<int:pk>',             api_branch_detail,  name='api_branch_detail'),
    path('branches/<int:pk>/status',      api_branch_status,  name='api_branch_status'),
    path('branches/<int:pk>/users',       api_branch_users,   name='api_branch_users'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_urlpatterns)),

    # Template-based admin panel
    path('', lambda request: redirect('branch_list'), name='home'),
    path('', include('accounts.urls')),
    path('', include('branches.urls')),
    path('', include('appointments.urls')),
] + [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
