from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from accounts import views as accounts_views

# The i18n language-switch endpoint (must be outside i18n_patterns)
# Google OAuth endpoints are also outside i18n_patterns so the redirect URI
# is always a fixed path (/accounts/google/callback/) without any language prefix.
# This prevents the "redirect_uri_mismatch" error from Google.
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/google/login/', accounts_views.google_login, name='google_login'),
    path('accounts/google/callback/', accounts_views.google_callback, name='google_callback'),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('courses/', include('courses.urls')),
    path('', include('accounts.urls')),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
