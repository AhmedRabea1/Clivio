from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('configuration/', views.configuration_view, name='configuration'),
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/add/', views.doctor_create, name='doctor_create'),
    path('doctors/<int:pk>/edit/', views.doctor_edit, name='doctor_edit'),
    path('doctors/<int:pk>/delete/', views.doctor_delete, name='doctor_delete'),
    path('assistants/', views.assistant_list, name='assistant_list'),
    path('assistants/add/', views.assistant_create, name='assistant_create'),
    path('assistants/<int:pk>/edit/', views.assistant_edit, name='assistant_edit'),
    path('assistants/<int:pk>/delete/', views.assistant_delete, name='assistant_delete'),
]
