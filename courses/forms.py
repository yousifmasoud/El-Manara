from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from .models import Session, Subject
from accounts.models import StudentProfile, TeacherProfile

class TeacherModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.profile.user.get_full_name() or obj.profile.user.username
        verified_str = f" ({_('Verified')})" if obj.is_verified else f" ({_('Pending')})"
        rating_str = f" ⭐ {obj.rating}" if obj.rating else ""
        return f"{name}{verified_str}{rating_str} — ${obj.hourly_rate}/hr"


class SessionForm(forms.ModelForm):
    teacher = TeacherModelChoiceField(
        queryset=TeacherProfile.objects.all().select_related('profile__user'),
        required=True,
        label=_('Teacher')
    )

    class Meta:
        model = Session
        fields = ('student', 'teacher', 'subject', 'scheduled_at', 'duration_minutes', 'notes')
        widgets = {
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'placeholder': '60'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Enter any special notes for the session…')}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        
        # Style form fields to match the platform's input design style
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.HiddenInput):
                existing_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{existing_class} form-control".strip()

        # Set default scheduled_at to tomorrow
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        self.fields['scheduled_at'].initial = tomorrow.strftime('%Y-%m-%dT10:00')

        if user:
            profile = getattr(user, 'profile', None)
            if profile:
                if profile.is_teacher:
                    # Current user is the teacher, they schedule with a student
                    self.fields['teacher'].required = False
                    self.fields['teacher'].widget = forms.HiddenInput()
                    teacher_subs = profile.teacher_profile.subjects.filter(is_active=True)
                    self.fields['subject'].queryset = teacher_subs
                    self.fields['student'].queryset = StudentProfile.objects.filter(
                        enrollments__subject__in=teacher_subs
                    ).distinct().select_related('profile__user')
                elif profile.is_student:
                    # Current user is the student, they schedule with a teacher
                    self.fields['student'].required = False
                    self.fields['student'].widget = forms.HiddenInput()
                    # Only show verified teachers if possible
                    verified_teachers = TeacherProfile.objects.filter(is_verified=True).select_related('profile__user')
                    if verified_teachers.exists():
                        self.fields['teacher'].queryset = verified_teachers
                    else:
                        self.fields['teacher'].queryset = TeacherProfile.objects.all().select_related('profile__user')
                    
                    # Filter subjects by student's enrollments
                    student_subs = profile.student_profile.enrollments.values_list('subject_id', flat=True)
                    if student_subs.exists():
                        self.fields['subject'].queryset = Subject.objects.filter(id__in=student_subs, is_active=True)
                    else:
                        self.fields['subject'].queryset = Subject.objects.filter(is_active=True)


    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data.get('scheduled_at')
        if scheduled_at and scheduled_at < timezone.now():
            raise forms.ValidationError(_('Session must be scheduled in the future.'))
        return scheduled_at

    def clean(self):
        cleaned_data = super().clean()
        duration_minutes = cleaned_data.get('duration_minutes')
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        
        # If student is not selected but the logged-in user is a student, assign the student profile
        if not student and self.user and hasattr(self.user, 'profile') and self.user.profile.is_student:
            student = self.user.profile.student_profile
            cleaned_data['student'] = student
        
        # Validate that if the scheduling user is a teacher, the student is enrolled in the subject
        # and the teacher is approved to teach the subject
        if self.user and hasattr(self.user, 'profile') and self.user.profile.is_teacher:
            teacher = self.user.profile.teacher_profile
            if subject and not teacher.subjects.filter(pk=subject.pk).exists():
                self.add_error('subject', _("You are not approved to teach this subject."))
            if student and subject:
                from .models import StudentEnrollment
                if not StudentEnrollment.objects.filter(student=student, subject=subject).exists():
                    self.add_error('subject', _("The selected student is not enrolled in this subject."))

        if duration_minutes is not None:
            if duration_minutes <= 0:
                self.add_error('duration_minutes', _('Duration must be greater than zero.'))
            else:
                duration_hours = Decimal(duration_minutes) / Decimal(60.0)
                if student and self.user and hasattr(self.user, 'profile') and self.user.profile.is_student:
                    if student.hourly_balance < duration_hours:
                        raise forms.ValidationError(
                            _("The student does not have enough hours in their balance. Required: %(req)s hours, Available: %(avail)s hours.") % {
                                'req': duration_hours,
                                'avail': student.hourly_balance
                            }
                        )
        return cleaned_data
