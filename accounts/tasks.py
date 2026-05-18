"""
django-crontab background task.

Register with:  python manage.py crontab add
Remove with:    python manage.py crontab remove
Show with:      python manage.py crontab show
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def expire_pending_referrals():
    """
    Runs daily at midnight (configured in settings.CRONJOBS).
    Marks 'pending' Referrals as 'expired' when the 30-day purchase
    window has elapsed without the referred student buying a package.
    """
    from .models import Referral
    from django.conf import settings

    window_days = getattr(settings, 'REFERRAL_WINDOW_DAYS', 30)
    cutoff = timezone.now() - timedelta(days=window_days)

    expired_qs = Referral.objects.filter(
        status=Referral.STATUS_PENDING,
        date_created__lt=cutoff,
    )
    count = expired_qs.update(status=Referral.STATUS_EXPIRED)
    logger.info("[Referral Cron] Expired %d pending referrals (cutoff=%s).", count, cutoff.date())
    print(f"[Referral Cron] Expired {count} pending referrals.")
