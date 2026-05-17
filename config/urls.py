from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.shortcuts import redirect

# API imports
from accounts.api_views import (
    api_login, api_refresh, api_logout,
    api_forgot_password, api_reset_password, api_change_password,
    api_users, api_user_detail, api_user_status, api_user_branches,
    api_configuration, api_public_configuration,
    api_public_doctors,
    api_doctors, api_doctor_detail, api_doctor_status,
    api_assistants, api_assistant_detail, api_assistant_status,
    api_assistant_roles,
    api_services, api_service_detail,
    api_products, api_product_detail,
    api_machines, api_machine_detail,
    api_pulse_packages, api_pulse_package_detail,
    api_area_packages, api_area_package_detail,
    api_doctor_medicines, api_doctor_medicine_detail,
)
from branches.api_views import (
    api_branches, api_branch_detail, api_branch_status, api_branch_users,
    api_public_branches,
)
from appointments.api_views import (
    api_public_book_reservation, api_public_slots, api_public_availability,
    api_patients, api_patient_detail, api_reservations, api_reservation_detail,
    api_reservation_attachments, api_reservation_attachment_detail,
    api_reservation_summary, api_reservation_prescription,
    api_patient_profile,
    api_derma_face_mappings, api_derma_face_mapping_detail,
    api_derma_face_mapping_line_detail,
)

api_urlpatterns = [
    # Auth
    path('auth/login',           api_login,           name='api_login'),
    path('auth/refresh',         api_refresh,         name='api_refresh'),
    path('auth/logout',          api_logout,          name='api_logout'),
    path('auth/forgot-password',  api_forgot_password,  name='api_forgot_password'),
    path('auth/reset-password',   api_reset_password,   name='api_reset_password'),
    path('auth/change-password',  api_change_password,  name='api_change_password'),

    # Users
    path('users',                    api_users,          name='api_users'),
    path('users/<int:pk>',           api_user_detail,    name='api_user_detail'),
    path('users/<int:pk>/status',    api_user_status,    name='api_user_status'),
    path('users/<int:pk>/branches',  api_user_branches,  name='api_user_branches'),

    # Doctors
    path('doctors',                  api_doctors,         name='api_doctors'),
    path('doctors/<int:pk>',         api_doctor_detail,   name='api_doctor_detail'),
    path('doctors/<int:pk>/status',  api_doctor_status,   name='api_doctor_status'),

    # Assistants
    path('assistants',                   api_assistants,        name='api_assistants'),
    path('assistants/<int:pk>',          api_assistant_detail,  name='api_assistant_detail'),
    path('assistants/<int:pk>/status',   api_assistant_status,  name='api_assistant_status'),

    # Assistant roles
    path('assistant-roles',              api_assistant_roles,   name='api_assistant_roles'),

    # Services
    path('services',             api_services,        name='api_services'),
    path('services/<int:pk>',    api_service_detail,  name='api_service_detail'),

    # Products
    path('products',             api_products,        name='api_products'),
    path('products/<int:pk>',    api_product_detail,  name='api_product_detail'),

    # Machines
    path('machines',             api_machines,        name='api_machines'),
    path('machines/<int:pk>',    api_machine_detail,  name='api_machine_detail'),

    # Pulse Packages
    path('pulse-packages',           api_pulse_packages,        name='api_pulse_packages'),
    path('pulse-packages/<int:pk>',  api_pulse_package_detail,  name='api_pulse_package_detail'),

    # Area Packages
    path('area-packages',            api_area_packages,         name='api_area_packages'),
    path('area-packages/<int:pk>',   api_area_package_detail,   name='api_area_package_detail'),

    # Doctor Medicines
    path('doctor-medicines',           api_doctor_medicines,         name='api_doctor_medicines'),
    path('doctor-medicines/<int:pk>',  api_doctor_medicine_detail,   name='api_doctor_medicine_detail'),

    # Configuration
    path('configuration',        api_configuration,        name='api_configuration'),
    path('public/configuration', api_public_configuration, name='api_public_configuration'),
    path('public/branches',      api_public_branches,      name='api_public_branches'),
    path('public/doctors',        api_public_doctors,           name='api_public_doctors'),
    path('public/reservations',   api_public_book_reservation,  name='api_public_book_reservation'),
    path('public/slots',          api_public_slots,             name='api_public_slots'),
    path('public/availability',   api_public_availability,      name='api_public_availability'),

    # Patients
    path('patients',              api_patients,                 name='api_patients'),
    path('patients/<int:pk>',     api_patient_detail,           name='api_patient_detail'),

    # Reservations
    path('reservations',                                api_reservations,                   name='api_reservations'),
    path('reservations/<int:pk>',                       api_reservation_detail,             name='api_reservation_detail'),
    path('reservations/<int:pk>/attachments',           api_reservation_attachments,        name='api_reservation_attachments'),
    path('attachments/<int:pk>',                        api_reservation_attachment_detail,  name='api_reservation_attachment_detail'),
    path('reservation-summary',                         api_reservation_summary,            name='api_reservation_summary'),
    path('reservations/<int:pk>/prescription',          api_reservation_prescription,       name='api_reservation_prescription'),
    path('patient-profile',                             api_patient_profile,                name='api_patient_profile'),

    # Derma Face Mappings
    path('derma-face-mappings',           api_derma_face_mappings,        name='api_derma_face_mappings'),
    path('derma-face-mappings/<int:pk>',       api_derma_face_mapping_detail,       name='api_derma_face_mapping_detail'),
    path('derma-face-mapping-lines/<int:pk>',  api_derma_face_mapping_line_detail,  name='api_derma_face_mapping_line_detail'),

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
