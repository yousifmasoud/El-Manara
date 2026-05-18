from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

PACKAGE_HOURS = list(range(8, 65, 8))  # [8, 16, 24, 32, 40, 48, 56, 64]


class Subject(models.Model):
    name_en = models.CharField(max_length=100, verbose_name=_('English Name'))
    name_ar = models.CharField(max_length=100, verbose_name=_('Arabic Name'))
    slug = models.SlugField(unique=True)
    icon_svg = models.TextField(verbose_name=_('SVG Icon'), blank=True)
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    is_test_prep = models.BooleanField(default=False, verbose_name=_('Test Prep Subject'))
    test_prep_badge = models.CharField(max_length=20, blank=True, help_text='e.g. SAT, IELTS, TOEFL')
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    color_accent = models.CharField(max_length=7, default='#00c9c9', help_text='Hex color for card accent')

    class Meta:
        ordering = ['order', 'name_en']
        verbose_name = _('Subject')
        verbose_name_plural = _('Subjects')

    def __str__(self):
        return self.name_en

    def get_name(self, lang='en'):
        return self.name_ar if lang == 'ar' else self.name_en


class HourlyPackage(models.Model):
    HOURS_CHOICES = [(h, f"{h} {_('hours')}") for h in PACKAGE_HOURS]

    hours = models.PositiveSmallIntegerField(
        choices=HOURS_CHOICES,
        unique=True,
        verbose_name=_('Hours'),
    )
    price_usd = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_('Price (USD)'))
    price_aed = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name=_('Price (AED)'))
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False, verbose_name=_('Featured Package'))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['hours']
        verbose_name = _('Hourly Package')
        verbose_name_plural = _('Hourly Packages')

    def __str__(self):
        return f"{self.hours}h — {self.price_aed} AED"

    @property
    def price_per_hour(self):
        if self.hours:
            return round(float(self.price_usd) / self.hours, 2)
        return 0

    @property
    def price_per_hour_aed(self):
        if self.hours:
            return round(float(self.price_aed) / self.hours, 1)
        return 0

    @property
    def savings_percent(self):
        """Savings vs. the 8-hour (base) package, per hour (AED)."""
        try:
            base = HourlyPackage.objects.get(hours=8)
            base_pph = float(base.price_aed) / 8
            current_pph = float(self.price_aed) / self.hours if self.hours else 0
            if base_pph and current_pph < base_pph:
                return round((1 - current_pph / base_pph) * 100)
        except HourlyPackage.DoesNotExist:
            pass
        return 0


class Purchase(models.Model):
    student = models.ForeignKey(
        'accounts.StudentProfile', on_delete=models.CASCADE, related_name='purchases'
    )
    package = models.ForeignKey(
        HourlyPackage, on_delete=models.SET_NULL, null=True, related_name='purchases'
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    hours_at_purchase = models.PositiveSmallIntegerField()
    price_at_purchase = models.DecimalField(max_digits=8, decimal_places=2)
    referral_processed = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-purchased_at']
        verbose_name = _('Purchase')
        verbose_name_plural = _('Purchases')

    def __str__(self):
        return f"{self.student} — {self.hours_at_purchase}h on {self.purchased_at.date()}"

    def save(self, *args, **kwargs):
        # Snapshot package details at purchase time
        if self.package and not self.pk:
            self.hours_at_purchase = self.package.hours
            self.price_at_purchase = self.package.price_usd
        super().save(*args, **kwargs)
        if not self.referral_processed:
            self._process_referral()

    def _process_referral(self):
        from accounts.models import Referral
        from datetime import timedelta

        reward_hours = getattr(settings, 'REFERRAL_REWARD_HOURS', 2)
        window_days = getattr(settings, 'REFERRAL_WINDOW_DAYS', 30)
        monthly_cap = getattr(settings, 'REFERRAL_MONTHLY_CAP', 4)

        try:
            referral = Referral.objects.get(
                referred_user=self.student,
                status=Referral.STATUS_PENDING,
            )
        except Referral.DoesNotExist:
            Purchase.objects.filter(pk=self.pk).update(referral_processed=True)
            return

        now = timezone.now()

        # Check 30-day window
        if now > referral.date_created + timedelta(days=window_days):
            referral.status = Referral.STATUS_EXPIRED
            referral.save()
            Purchase.objects.filter(pk=self.pk).update(referral_processed=True)
            return

        # Check monthly cap on the referrer
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_count = Referral.objects.filter(
            referrer=referral.referrer,
            status=Referral.STATUS_COMPLETED,
            date_completed__gte=month_start,
        ).count()

        if monthly_count >= monthly_cap:
            referral.status = Referral.STATUS_EXPIRED
            referral.save()
            Purchase.objects.filter(pk=self.pk).update(referral_processed=True)
            return

        # All checks passed — grant reward
        referral.status = Referral.STATUS_COMPLETED
        referral.date_completed = now
        referral.reward_granted = True
        referral.reward_hours = reward_hours
        referral.save()

        referrer = referral.referrer
        referrer.hourly_balance += reward_hours
        referrer.save(update_fields=['hourly_balance'])

        Purchase.objects.filter(pk=self.pk).update(referral_processed=True)
