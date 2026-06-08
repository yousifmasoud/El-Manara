from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils.crypto import get_random_string
import requests
from courses.models import HourlyPackage, Subject, Session

from .forms import (
    LoginForm,
    ParentRegistrationForm,
    StudentRegistrationForm,
    TeacherRegistrationForm,
)
from .models import ParentProfile, Referral, StudentProfile, TeacherProfile, UserProfile, GoogleCredential


def _template(lang, name):
    """Return 'ar/<name>' for Arabic, 'en/<name>' for English."""
    prefix = "ar" if (lang or "").startswith("ar") else "en"
    return f"{prefix}/{name}"


def home(request):
    subjects = Subject.objects.filter(is_active=True, is_test_prep=False).order_by(
        "order"
    )
    test_prep = Subject.objects.filter(is_active=True, is_test_prep=True).order_by(
        "order"
    )
    featured_packages = HourlyPackage.objects.filter(is_active=True, is_featured=True)
    lang = translation.get_language() or "en"
    return render(
        request,
        _template(lang, "home.html"),
        {
            "subjects": subjects,
            "test_prep": test_prep,
            "featured_packages": featured_packages,
            "lang": lang,
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    lang = translation.get_language() or "en"
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user:
            login(request, user)
            next_url = request.GET.get("next", "home")
            return redirect(next_url)
        messages.error(request, _("Invalid username or password."))
    return render(request, _template(lang, "accounts/login.html"), {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


def register_student(request):
    lang = translation.get_language() or "en"
    referral_code = request.GET.get("ref", "")
    form = StudentRegistrationForm(
        request.POST or None, initial={"referral_code": referral_code}
    )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_STUDENT)
        student = StudentProfile.objects.create(
            profile=profile,
            grade_level=form.cleaned_data.get("grade_level", ""),
        )
        # Handle referral linkage
        ref = form.cleaned_data.get("referral_code", "").strip().upper()
        if ref:
            try:
                referrer = StudentProfile.objects.get(referral_code=ref)
                if referrer != student:
                    Referral.objects.get_or_create(
                        referrer=referrer, referred_user=student
                    )
            except StudentProfile.DoesNotExist:
                pass
        login(request, user)
        messages.success(request, _("Welcome to Khotaa Academy!"))
        return redirect("home")
    return render(
        request, _template(lang, "accounts/register_student.html"), {"form": form}
    )


def register_teacher(request):
    lang = translation.get_language() or "en"
    form = TeacherRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_TEACHER)
        TeacherProfile.objects.create(
            profile=profile,
            bio=form.cleaned_data.get("bio", ""),
            hourly_rate=form.cleaned_data.get("hourly_rate") or 0,
        )
        login(request, user)
        messages.success(
            request, _("Welcome, Teacher! Your profile is pending verification.")
        )
        return redirect("home")
    return render(
        request, _template(lang, "accounts/register_teacher.html"), {"form": form}
    )


def register_parent(request):
    lang = translation.get_language() or "en"
    form = ParentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_PARENT)
        ParentProfile.objects.create(profile=profile)
        login(request, user)
        messages.success(
            request, _("Welcome! You can now manage your children's accounts.")
        )
        return redirect("dashboard")
    return render(
        request, _template(lang, "accounts/register_parent.html"), {"form": form}
    )


@login_required
def dashboard(request):
    lang = translation.get_language() or "en"
    profile = request.user.profile
    context = {"profile": profile}
    if profile.is_student:
        student = profile.student_profile
        referrals = Referral.objects.filter(referrer=student).select_related(
            "referred_user__profile__user"
        )
        sessions = student.sessions.all().select_related("teacher__profile__user", "subject")
        context.update(
            {
                "student": student,
                "referrals": referrals,
                "purchases": student.purchases.all()[:5],
                "sessions": sessions,
            }
        )
    elif profile.is_teacher:
        teacher = profile.teacher_profile
        sessions = teacher.sessions.all().select_related("student__profile__user", "subject")
        context.update({
            "teacher": teacher,
            "sessions": sessions,
        })
    elif profile.is_parent:
        parent = profile.parent_profile
        context["parent"] = parent
        context["children"] = parent.children.select_related("profile__user").all()
    return render(request, _template(lang, "accounts/dashboard.html"), context)


def about_view(request):
    lang = translation.get_language() or "en"
    return render(request, _template(lang, "about.html"), {"lang": lang})


def contact_view(request):
    lang = translation.get_language() or "en"
    return render(request, _template(lang, "contact.html"), {"lang": lang})


def google_login(request):
    role = request.GET.get('role', 'student')
    request.session['google_oauth_role'] = role
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    is_mock = not client_id or 'placeholder' in client_id.lower() or 'your-' in client_id.lower()
    if is_mock:
        return redirect(reverse('google_callback') + '?code=mock_oauth_code_xyz')
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    from urllib.parse import urlencode
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile https://www.googleapis.com/auth/calendar',
        'access_type': 'offline',
        'prompt': 'consent',
    })
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    return redirect(google_auth_url)


def google_callback(request):
    code = request.GET.get('code')
    if not code:
        messages.error(request, _("Google authentication failed: no code returned."))
        return redirect('login')
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    is_mock = not client_id or 'placeholder' in client_id.lower() or 'your-' in client_id.lower() or code == 'mock_oauth_code_xyz'
    role = request.session.pop('google_oauth_role', 'student')
    if role not in [UserProfile.ROLE_STUDENT, UserProfile.ROLE_TEACHER, UserProfile.ROLE_PARENT]:
        role = UserProfile.ROLE_STUDENT
    if is_mock:
        if request.user.is_authenticated:
            GoogleCredential.objects.update_or_create(
                user=request.user,
                defaults={
                    'access_token': 'mock_access_token',
                    'refresh_token': 'mock_refresh_token',
                    'scopes': 'openid email profile https://www.googleapis.com/auth/calendar',
                    'expires_at': timezone.now() + timezone.timedelta(hours=1)
                }
            )
            messages.success(request, _("Successfully linked Google account (Mock Mode)."))
            return redirect('dashboard')
        username = f'google_{role}'
        email = f'{role}@google.com'
        try:
            user = User.objects.get(email=email)
            created = False
        except User.DoesNotExist:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': f'Google {role.capitalize()}',
                    'last_name': '(Mock)',
                }
            )
        if created:
            user.set_password(get_random_string(32))
            user.save()
            profile = UserProfile.objects.create(user=user, role=role)
            if role == UserProfile.ROLE_STUDENT:
                StudentProfile.objects.create(profile=profile)
            elif role == UserProfile.ROLE_TEACHER:
                TeacherProfile.objects.create(profile=profile)
            elif role == UserProfile.ROLE_PARENT:
                ParentProfile.objects.create(profile=profile)
        GoogleCredential.objects.update_or_create(
            user=user,
            defaults={
                'access_token': 'mock_access_token',
                'refresh_token': 'mock_refresh_token',
                'scopes': 'openid email profile https://www.googleapis.com/auth/calendar',
                'expires_at': timezone.now() + timezone.timedelta(hours=1)
            }
        )
        login(request, user)
        messages.success(request, _("Successfully logged in with Google (Mock Mode)."))
        return redirect('dashboard')
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        messages.error(request, _(f"Google token exchange failed: {response.text}"))
        return redirect('login')
    token_data = response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 3600)
    expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {'Authorization': f"Bearer {access_token}"}
    userinfo_response = requests.get(userinfo_url, headers=headers)
    if userinfo_response.status_code != 200:
        messages.error(request, _("Google userinfo retrieval failed."))
        return redirect('login')
    userinfo = userinfo_response.json()
    email = userinfo.get('email')
    first_name = userinfo.get('given_name', '')
    last_name = userinfo.get('family_name', '')
    if request.user.is_authenticated:
        GoogleCredential.objects.update_or_create(
            user=request.user,
            defaults={
                'access_token': access_token,
                'refresh_token': refresh_token or GoogleCredential.objects.filter(user=request.user).values_list('refresh_token', flat=True).first(),
                'scopes': token_data.get('scope', ''),
                'expires_at': expires_at
            }
        )
        messages.success(request, _("Successfully linked Google account."))
        return redirect('dashboard')
    try:
        user = User.objects.get(email=email)
        created = False
    except User.DoesNotExist:
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        created = True

    if created:
        user.set_password(get_random_string(32))
        user.save()
        profile = UserProfile.objects.create(user=user, role=role)
        if role == UserProfile.ROLE_STUDENT:
            StudentProfile.objects.create(profile=profile)
        elif role == UserProfile.ROLE_TEACHER:
            TeacherProfile.objects.create(profile=profile)
        elif role == UserProfile.ROLE_PARENT:
            ParentProfile.objects.create(profile=profile)
    GoogleCredential.objects.update_or_create(
        user=user,
        defaults={
            'access_token': access_token,
            'refresh_token': refresh_token or GoogleCredential.objects.filter(user=user).values_list('refresh_token', flat=True).first(),
            'scopes': token_data.get('scope', ''),
            'expires_at': expires_at
        }
    )
    login(request, user)
    messages.success(request, _("Successfully logged in with Google."))
    return redirect('dashboard')


@login_required
@require_POST
def create_instant_meeting(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    profile = request.user.profile
    
    # Check authorization (only student or teacher of the session)
    is_authorized = False
    if profile.is_teacher and session.teacher == profile.teacher_profile:
        is_authorized = True
    elif profile.is_student and session.student == profile.student_profile:
        is_authorized = True
        
    if not is_authorized:
        messages.error(request, _("Access denied: You are not authorized to create a meeting for this session."))
        return redirect('dashboard')

    # Check for Google Credentials to add to calendar if possible
    has_credential = False
    try:
        credential = request.user.google_credential
        has_credential = True
    except GoogleCredential.DoesNotExist:
        credential = None

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    is_mock = not client_id or 'placeholder' in client_id.lower() or 'your-' in client_id.lower() or not has_credential or credential.refresh_token == 'mock_refresh_token'

    if is_mock:
        import random
        part1 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
        part2 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=4))
        part3 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
        session.meeting_link = f"https://meet.google.com/{part1}-{part2}-{part3}"
        session.save(update_fields=['meeting_link'])
        messages.warning(request, _("Google account is not linked. A placeholder mock Google Meet link was generated for display, but it will not be active on Google's servers. To generate real, working Google Meet links, please click 'Link Google Account' in your dashboard sidebar first."))
        return redirect('dashboard')

    # If not mock, attempt Google Calendar integration to invite both users and generate Google Meet
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    
    creds = Credentials(
        token=credential.access_token,
        refresh_token=credential.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=credential.scopes.split(' ')
    )
    
    # Refresh the access token if it has expired
    if credential.expires_at and credential.expires_at <= timezone.now():
        try:
            creds.refresh(Request())
            credential.access_token = creds.token
            credential.expires_at = timezone.now() + timezone.timedelta(seconds=3600)
            if creds.refresh_token:
                credential.refresh_token = creds.refresh_token
            credential.save(update_fields=['access_token', 'refresh_token', 'expires_at'])
        except Exception as e:
            # Fallback to saving Google Meet link directly if token refresh fails
            import random
            part1 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            part2 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=4))
            part3 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            session.meeting_link = f"https://meet.google.com/{part1}-{part2}-{part3}"
            session.save(update_fields=['meeting_link'])
            messages.warning(request, _(f"Google token refresh failed: {str(e)}. A placeholder mock Google Meet link was created. Please re-link your Google account."))
            return redirect('dashboard')
            
    try:
        service = build('calendar', 'v3', credentials=creds)
        start_time = session.scheduled_at
        end_time = start_time + timezone.timedelta(minutes=session.duration_minutes)
        event_body = {
            'summary': f"Khotaa Academy Lesson: {session.subject.name_en if session.subject else 'Tutoring'}",
            'description': f"Tutoring lesson between Student {session.student} and Teacher {session.teacher}.\nNotes: {session.notes}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"khotaa-session-{session.id}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            },
            'attendees': [
                {'email': session.student.profile.user.email},
                {'email': session.teacher.profile.user.email},
            ],
        }
        event = service.events().insert(
            calendarId='primary',
            body=event_body,
            conferenceDataVersion=1
        ).execute()
        
        # Persist refreshed token if changed
        if creds.token != credential.access_token:
            credential.access_token = creds.token
            credential.expires_at = timezone.now() + timezone.timedelta(seconds=3600)
            if creds.refresh_token:
                credential.refresh_token = creds.refresh_token
            credential.save(update_fields=['access_token', 'refresh_token', 'expires_at'])
            
        meet_link = event.get('hangoutLink')
        if meet_link:
            session.meeting_link = meet_link
            session.save(update_fields=['meeting_link'])
            messages.success(request, _("Successfully created Google Meet link and added to Google Calendar!"))
        else:
            # Fallback to direct mock link if hangoutLink is missing
            import random
            part1 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            part2 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=4))
            part3 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            session.meeting_link = f"https://meet.google.com/{part1}-{part2}-{part3}"
            session.save(update_fields=['meeting_link'])
            messages.warning(request, _("Google Meet link not returned; generated fallback mock Google Meet link."))
    except Exception as e:
        # Fallback to direct mock link on API error
        import random
        part1 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
        part2 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=4))
        part3 = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
        session.meeting_link = f"https://meet.google.com/{part1}-{part2}-{part3}"
        session.save(update_fields=['meeting_link'])
        messages.warning(request, _(f"Google Calendar API failed: {str(e)}. Generated a placeholder mock Google Meet link. Please verify your Google API project setup, OAuth scopes, and permissions."))
        
    return redirect('dashboard')
