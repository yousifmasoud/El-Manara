from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Subject, HourlyPackage, Purchase, Session, StudentEnrollment, TeacherSubjectRequest


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'name_ar', 'slug', 'is_test_prep', 'is_active', 'order')
    list_filter = ('is_test_prep', 'is_active')
    search_fields = ('name_en', 'name_ar')
    prepopulated_fields = {'slug': ('name_en',)}
    list_editable = ('order', 'is_active', 'is_test_prep')


@admin.register(HourlyPackage)
class HourlyPackageAdmin(admin.ModelAdmin):
    list_display = ('hours', 'price_usd', 'price_per_hour', 'savings_percent', 'is_featured', 'is_active')
    list_filter = ('is_featured', 'is_active')
    list_editable = ('is_featured', 'is_active')

    @admin.display(description=_('$/hr'))
    def price_per_hour(self, obj):
        return f"${obj.price_per_hour}"

    @admin.display(description=_('Savings %'))
    def savings_percent(self, obj):
        return f"{obj.savings_percent}%"


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('student', 'hours_at_purchase', 'price_at_purchase', 'purchased_at', 'referral_processed')
    list_filter = ('referral_processed',)
    search_fields = ('student__profile__user__username', 'transaction_id')
    readonly_fields = ('purchased_at', 'hours_at_purchase', 'price_at_purchase')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'student', 'teacher', 'scheduled_at', 'duration_minutes', 'status')
    list_filter = ('status', 'scheduled_at')
    search_fields = ('student__profile__user__username', 'teacher__profile__user__username', 'subject__name_en')


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'enrolled_at')
    list_filter = ('subject', 'enrolled_at')
    search_fields = ('student__profile__user__username', 'subject__name_en')


@admin.register(TeacherSubjectRequest)
class TeacherSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'proposed_rate', 'status', 'created_at')
    list_filter = ('status', 'subject', 'created_at')
    search_fields = ('teacher__profile__user__username', 'subject__name_en')
    actions = ['approve_requests', 'reject_requests']

    @admin.action(description=_("Approve selected teacher requests"))
    def approve_requests(self, request, queryset):
        for req in queryset:
            req.status = req.STATUS_APPROVED
            req.save()
        self.message_user(request, _("Selected requests approved and subjects linked."))

    @admin.action(description=_("Reject selected teacher requests"))
    def reject_requests(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, _("Selected requests rejected."))


