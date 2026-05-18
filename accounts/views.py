from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import translation

from .models import UserProfile, StudentProfile, TeacherProfile, ParentProfile, Referral
from .forms import StudentRegistrationForm, TeacherRegistrationForm, ParentRegistrationForm, LoginForm
from courses.models import Subject, HourlyPackage


def home(request):
    subjects = Subject.objects.filter(is_active=True, is_test_prep=False).order_by('order')
    test_prep = Subject.objects.filter(is_active=True, is_test_prep=True).order_by('order')
    featured_packages = HourlyPackage.objects.filter(is_active=True, is_featured=True)
    lang = translation.get_language() or 'en'
    return render(request, 'home.html', {
        'subjects': subjects,
        'test_prep': test_prep,
        'featured_packages': featured_packages,
        'lang': lang,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        messages.error(request, _('Invalid username or password.'))
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


def register_student(request):
    referral_code = request.GET.get('ref', '')
    form = StudentRegistrationForm(request.POST or None, initial={'referral_code': referral_code})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_STUDENT)
        student = StudentProfile.objects.create(
            profile=profile,
            grade_level=form.cleaned_data.get('grade_level', ''),
        )
        # Handle referral linkage
        ref = form.cleaned_data.get('referral_code', '').strip().upper()
        if ref:
            try:
                referrer = StudentProfile.objects.get(referral_code=ref)
                if referrer != student:
                    Referral.objects.get_or_create(referrer=referrer, referred_user=student)
            except StudentProfile.DoesNotExist:
                pass
        login(request, user)
        messages.success(request, _('Welcome to El-Manara Academy!'))
        return redirect('home')
    return render(request, 'accounts/register_student.html', {'form': form})


def register_teacher(request):
    form = TeacherRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_TEACHER)
        TeacherProfile.objects.create(
            profile=profile,
            bio=form.cleaned_data.get('bio', ''),
            hourly_rate=form.cleaned_data.get('hourly_rate') or 0,
        )
        login(request, user)
        messages.success(request, _('Welcome, Teacher! Your profile is pending verification.'))
        return redirect('home')
    return render(request, 'accounts/register_teacher.html', {'form': form})


def register_parent(request):
    form = ParentRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_PARENT)
        ParentProfile.objects.create(profile=profile)
        login(request, user)
        messages.success(request, _('Welcome! You can now manage your children\'s accounts.'))
        return redirect('dashboard')
    return render(request, 'accounts/register_parent.html', {'form': form})


@login_required
def dashboard(request):
    profile = request.user.profile
    context = {'profile': profile}
    if profile.is_student:
        student = profile.student_profile
        referrals = Referral.objects.filter(referrer=student).select_related('referred_user__profile__user')
        context.update({
            'student': student,
            'referrals': referrals,
            'purchases': student.purchases.all()[:5],
        })
    elif profile.is_teacher:
        context['teacher'] = profile.teacher_profile
    elif profile.is_parent:
        parent = profile.parent_profile
        context['parent'] = parent
        context['children'] = parent.children.select_related('profile__user').all()
    return render(request, 'accounts/dashboard.html', context)


def about_view(request):
    lang = translation.get_language() or 'en'
    return render(request, 'about.html', {'lang': lang})


def contact_view(request):
    lang = translation.get_language() or 'en'
    return render(request, 'contact.html', {'lang': lang})
