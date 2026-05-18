from django.urls import path
from . import views

urlpatterns = [
    path('packages/', views.packages_view, name='packages'),
    path('packages/purchase/', views.purchase_package, name='purchase_package'),
]
