from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/student/', views.register_student, name='register_student'),
    path('register/teacher/', views.register_teacher, name='register_teacher'),
    path('register/parent/', views.register_parent, name='register_parent'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    # NOTE: google/login/ and google/callback/ are defined in khotaa/urls.py
    # outside of i18n_patterns to ensure a stable redirect URI for Google OAuth.
    path('sessions/<int:session_id>/create-meet/', views.create_instant_meeting, name='create_instant_meeting'),
    path('dashboard/send-link-request/', views.send_link_request, name='send_link_request'),
    path('dashboard/generate-invite-link/', views.generate_invite_link, name='generate_invite_link'),
    path('dashboard/accept-link-request/<int:request_id>/', views.accept_link_request, name='accept_link_request'),
    path('dashboard/reject-link-request/<int:request_id>/', views.reject_link_request, name='reject_link_request'),
    path('link/accept/', views.accept_invite_link, name='accept_invite_link'),
]
