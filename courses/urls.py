from django.urls import path
from . import views

urlpatterns = [
    path('', views.courses_list, name='courses_list'),
    path('enroll/', views.enroll_in_course, name='enroll_in_course'),
    path('teach-request/', views.request_to_teach, name='request_to_teach'),
    path('packages/', views.packages_view, name='packages'),
    path('packages/purchase/', views.purchase_package, name='purchase_package'),
    path('sessions/create/', views.create_session, name='create_session'),
    path('sessions/<int:session_id>/cancel/', views.cancel_session, name='cancel_session'),
    path('sessions/<int:session_id>/accept/', views.accept_session, name='accept_session'),
    path('sessions/<int:session_id>/reject/', views.reject_session, name='reject_session'),
]
