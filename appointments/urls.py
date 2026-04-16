from django.urls import path
from . import views

urlpatterns = [
    path('patients/',           views.patient_list,   name='patient_list'),
    path('patients/add/',       views.patient_create, name='patient_create'),
    path('patients/<int:pk>/edit/',   views.patient_edit,   name='patient_edit'),
    path('patients/<int:pk>/delete/', views.patient_delete, name='patient_delete'),
]
