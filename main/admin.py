from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count

class CustomAdminSite(admin.AdminSite):
    site_header = "StudyOptimizer Admin"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['total_users'] = User.objects.count()
        return super().index(request, extra_context=extra_context)

admin_site = CustomAdminSite(name='custom_admin')

