from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Subject, HourlyPackage, Purchase


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
