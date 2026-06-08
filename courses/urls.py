from django.urls import path
from . import views

urlpatterns = [
    path('packages/', views.packages_view, name='packages'),
    path('packages/purchase/', views.purchase_package, name='purchase_package'),
    path('sessions/create/', views.create_session, name='create_session'),
    path('sessions/<int:session_id>/cancel/', views.cancel_session, name='cancel_session'),
]
