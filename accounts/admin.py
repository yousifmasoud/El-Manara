from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import UserProfile, StudentProfile, TeacherProfile, ParentProfile, Referral


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'language_preference', 'phone')
    list_filter = ('role', 'language_preference')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'referral_code', 'hourly_balance', 'grade_level')
    search_fields = ('profile__user__username', 'referral_code')
    readonly_fields = ('referral_code',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'hourly_rate', 'is_verified', 'rating', 'total_sessions')
    list_filter = ('is_verified',)
    filter_horizontal = ('subjects',)


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__',)
    filter_horizontal = ('children',)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred_user', 'status', 'date_created', 'reward_granted', 'reward_hours')
    list_filter = ('status', 'reward_granted')
    search_fields = ('referrer__profile__user__username', 'referred_user__profile__user__username')
    readonly_fields = ('date_created', 'date_completed')
