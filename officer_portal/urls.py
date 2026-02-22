from django.urls import path
from . import views

urlpatterns = [
    path('', views.officer_login, name='portal_login'),
    path('admin-security/2fa/', views.Admin2FAView.as_view(), name='admin_2fa'),
    path('admin-security/logout/', views.custom_admin_logout, name='clean_logout'),
    path('dashboard/', views.officer_dashboard, name='officer_dashboard'),
    path('api/chat/', views.ai_chat_endpoint, name='ai_chat_endpoint'),
    path('api/generate-legal/', views.generate_legal, name='generate_legal'),
    path('api/download-case-pdf/', views.download_case_pdf, name='download_case_pdf'),
    path('authorize/', views.authorize_ai, name='authorize_ai'),
    path('ai-lab/', views.ai_lab, name='ai_lab'),
    path('api/create-case/', views.create_case_endpoint, name='create_case'),
    path('sys/factory_reset/', views.factory_reset, name='factory_reset'),
]
