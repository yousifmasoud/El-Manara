from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class LoginForm(forms.Form):
    username = forms.CharField(
        label=_('Username'),
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'placeholder': _('Username')}),
    )
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'placeholder': _('Password')}),
    )


class BaseRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'placeholder': _('Password')}),
        required=True,
    )
    password2 = forms.CharField(
        label=_('Confirm Password'),
        widget=forms.PasswordInput(attrs={'placeholder': _('Confirm Password')}),
        required=True,
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': _('First Name')}),
            'last_name': forms.TextInput(attrs={'placeholder': _('Last Name')}),
            'username': forms.TextInput(attrs={'placeholder': _('Username')}),
            'email': forms.EmailInput(attrs={'placeholder': _('Email Address')}),
        }

    def __init__(self, *args, **kwargs):
        is_google = kwargs.pop('is_google', False)
        is_profile_completion = kwargs.pop('is_profile_completion', False)
        self.is_google = is_google
        self.is_profile_completion = is_profile_completion
        super().__init__(*args, **kwargs)
        if is_google or is_profile_completion:
            if 'password1' in self.fields:
                del self.fields['password1']
            if 'password2' in self.fields:
                del self.fields['password2']
            if is_google:
                self.fields['email'].disabled = True
            if is_profile_completion:
                self.fields['username'].disabled = True
                self.fields['email'].disabled = True

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if (self.is_google or self.is_profile_completion) and not p1 and not p2:
            return p2
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_('Passwords do not match.'))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get('password1')
        if p1:
            user.set_password(p1)
        elif not user.pk:
            import secrets
            user.set_password(secrets.token_hex(16))
        if commit:
            user.save()
        return user


class StudentRegistrationForm(BaseRegistrationForm):
    referral_code = forms.CharField(
        label=_('Referral Code (optional)'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Enter referral code')}),
    )
    grade_level = forms.CharField(
        label=_('Grade Level'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('e.g. Grade 10 / Year 12')}),
    )


class TeacherRegistrationForm(BaseRegistrationForm):
    bio = forms.CharField(
        label=_('Short Biography'),
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': _('Tell students about yourself…')}),
    )
    hourly_rate = forms.DecimalField(
        label=_('Hourly Rate (USD)'),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'placeholder': '25.00'}),
    )


class ParentRegistrationForm(BaseRegistrationForm):
    pass
