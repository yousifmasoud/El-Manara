import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.conf import settings


def generate_referral_code():
    """Generate a unique 8-character alphanumeric code."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):
        code = ''.join(random.choices(chars, k=8))
        if not StudentProfile.objects.filter(referral_code=code).exists():
            return code
    raise ValueError("Could not generate a unique referral code.")


class UserProfile(models.Model):
    ROLE_STUDENT = 'student'
    ROLE_TEACHER = 'teacher'
    ROLE_PARENT = 'parent'
    ROLE_CHOICES = [
        (ROLE_STUDENT, _('Student')),
        (ROLE_TEACHER, _('Teacher')),
        (ROLE_PARENT, _('Parent')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    language_preference = models.CharField(
        max_length=2,
        choices=[('ar', 'العربية'), ('en', 'English')],
        default='ar',
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Phone'))
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == self.ROLE_STUDENT

    @property
    def is_teacher(self):
        return self.role == self.ROLE_TEACHER

    @property
    def is_parent(self):
        return self.role == self.ROLE_PARENT


class StudentProfile(models.Model):
    profile = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name='student_profile'
    )
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    hourly_balance = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    grade_level = models.CharField(max_length=50, blank=True, verbose_name=_('Grade Level'))
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_('Date of Birth'))

    class Meta:
        verbose_name = _('Student Profile')
        verbose_name_plural = _('Student Profiles')

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = generate_referral_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Student: {self.profile.user.get_full_name() or self.profile.user.username}"


class TeacherProfile(models.Model):
    profile = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name='teacher_profile'
    )
    bio = models.TextField(blank=True, verbose_name=_('Biography'))
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name=_('Hourly Rate (USD)'))
    is_verified = models.BooleanField(default=False, verbose_name=_('Verified'))
    subjects = models.ManyToManyField('courses.Subject', blank=True, related_name='teachers')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, verbose_name=_('Rating'))
    total_sessions = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Teacher Profile')
        verbose_name_plural = _('Teacher Profiles')

    def __str__(self):
        return f"Teacher: {self.profile.user.get_full_name() or self.profile.user.username}"


class ParentProfile(models.Model):
    profile = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name='parent_profile'
    )
    children = models.ManyToManyField(
        StudentProfile, blank=True, related_name='parents', verbose_name=_('Children')
    )

    class Meta:
        verbose_name = _('Parent Profile')
        verbose_name_plural = _('Parent Profiles')

    def __str__(self):
        return f"Parent: {self.profile.user.get_full_name() or self.profile.user.username}"


class Referral(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_COMPLETED, _('Completed')),
        (STATUS_EXPIRED, _('Expired')),
    ]

    referrer = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name='referrals_made'
    )
    referred_user = models.OneToOneField(
        StudentProfile, on_delete=models.CASCADE, related_name='referral_received'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    date_created = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True, blank=True)
    reward_granted = models.BooleanField(default=False)
    reward_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    class Meta:
        verbose_name = _('Referral')
        verbose_name_plural = _('Referrals')

    def __str__(self):
        return f"{self.referrer} → {self.referred_user} [{self.get_status_display()}]"
