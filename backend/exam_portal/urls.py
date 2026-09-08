import re

from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.http import JsonResponse
from django.views.static import serve as serve_static


def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('healthz/', health_check, name='health-check'),
    path('admin/', admin.site.urls),
    path('api/', include('portal.urls')),
]

# Serve uploaded note attachments / recordings. This deployment has no CDN or
# object storage in front of MEDIA_ROOT, so the files must be served by
# Django itself even with DEBUG off (Gunicorn on Render). Django's own
# `static()` helper is a no-op whenever DEBUG=False, which is exactly why
# every note download/upload link was 404ing with "resource not found" in
# production — so this wires django.views.static.serve directly instead of
# going through that helper.
urlpatterns += [
    re_path(r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')),
            serve_static, {'document_root': settings.MEDIA_ROOT}),
]


