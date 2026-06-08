from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from .models import Session, Subject
from accounts.models import StudentProfile, TeacherProfile

class SessionForm(forms.ModelForm):
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
                    self.fields['student'].queryset = StudentProfile.objects.all().select_related('profile__user')
                    # If teacher has specified subjects, show those, otherwise show all active
                    teacher_sub = profile.teacher_profile.subjects.all()
                    if teacher_sub.exists():
                        self.fields['subject'].queryset = teacher_sub.filter(is_active=True)
                    else:
                        self.fields['subject'].queryset = Subject.objects.filter(is_active=True)
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
        
        # If student is not selected but the logged-in user is a student, assign the student profile
        if not student and self.user and hasattr(self.user, 'profile') and self.user.profile.is_student:
            student = self.user.profile.student_profile
            cleaned_data['student'] = student
        
        if duration_minutes is not None:
            if duration_minutes <= 0:
                self.add_error('duration_minutes', _('Duration must be greater than zero.'))
            else:
                duration_hours = Decimal(duration_minutes) / Decimal(60.0)
                if student:
                    if student.hourly_balance < duration_hours:
                        raise forms.ValidationError(
                            _("The student does not have enough hours in their balance. Required: %(req)s hours, Available: %(avail)s hours.") % {
                                'req': duration_hours,
                                'avail': student.hourly_balance
                            }
                        )
        return cleaned_data
