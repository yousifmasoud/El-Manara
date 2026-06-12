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
from django.db.models import Q

from .forms import (
    LoginForm,
    ParentRegistrationForm,
    StudentRegistrationForm,
    TeacherRegistrationForm,
)
from .models import ParentProfile, Referral, StudentProfile, TeacherProfile, UserProfile, GoogleCredential, ParentChildRequest



def _template(lang, name):
    """Return 'ar/<name>' for Arabic, 'en/<name>' for English."""
    prefix = "ar" if (lang or "").startswith("ar") else "en"
    return f"{prefix}/{name}"


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
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
    
    # Determine if this is a Google registration
    google_data = request.session.get('google_register_data')
    is_google = google_data is not None
    
    # Determine if this is profile completion for a logged-in user
    is_profile_completion = False
    if request.user.is_authenticated:
        try:
            if request.user.profile.student_profile:
                return redirect('dashboard')
        except Exception:
            pass
        is_profile_completion = True
        
    initial_data = {"referral_code": referral_code}
    if is_google:
        initial_data.update({
            'email': google_data['email'],
            'first_name': google_data['first_name'],
            'last_name': google_data['last_name'],
            'username': google_data['email'].split('@')[0],
        })
        
    if request.method == "POST":
        form = StudentRegistrationForm(
            request.POST,
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
        if form.is_valid():
            if is_profile_completion:
                user = request.user
                form.save()
                profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.ROLE_STUDENT})
                if not created and profile.role != UserProfile.ROLE_STUDENT:
                    profile.role = UserProfile.ROLE_STUDENT
                    profile.save(update_fields=['role'])
            else:
                user = form.save()
                profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_STUDENT)
                
            student, created = StudentProfile.objects.get_or_create(
                profile=profile,
                defaults={'grade_level': form.cleaned_data.get("grade_level", "")}
            )
            
            if is_google:
                from django.utils.dateparse import parse_datetime
                GoogleCredential.objects.update_or_create(
                    user=user,
                    defaults={
                        'access_token': google_data['access_token'],
                        'refresh_token': google_data['refresh_token'],
                        'scopes': google_data['scopes'],
                        'expires_at': parse_datetime(google_data['expires_at']) or timezone.now() + timezone.timedelta(hours=1)
                    }
                )
                request.session.pop('google_register_data', None)
                
            if not request.user.is_authenticated:
                login(request, user)
                
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
            messages.success(request, _("Welcome to Khotaa Academy!"))
            return redirect("dashboard")
    else:
        form = StudentRegistrationForm(
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
    return render(
        request, _template(lang, "accounts/register_student.html"), {"form": form}
    )


def register_teacher(request):
    lang = translation.get_language() or "en"
    
    # Determine if this is a Google registration
    google_data = request.session.get('google_register_data')
    is_google = google_data is not None
    
    # Determine if this is profile completion for a logged-in user
    is_profile_completion = False
    if request.user.is_authenticated:
        try:
            if request.user.profile.teacher_profile:
                return redirect('dashboard')
        except Exception:
            pass
        is_profile_completion = True
        
    initial_data = {}
    if is_google:
        initial_data.update({
            'email': google_data['email'],
            'first_name': google_data['first_name'],
            'last_name': google_data['last_name'],
            'username': google_data['email'].split('@')[0],
        })
        
    if request.method == "POST":
        form = TeacherRegistrationForm(
            request.POST,
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
        if form.is_valid():
            if is_profile_completion:
                user = request.user
                form.save()
                profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.ROLE_TEACHER})
                if not created and profile.role != UserProfile.ROLE_TEACHER:
                    profile.role = UserProfile.ROLE_TEACHER
                    profile.save(update_fields=['role'])
            else:
                user = form.save()
                profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_TEACHER)
                
            teacher, created = TeacherProfile.objects.get_or_create(
                profile=profile,
                defaults={
                    'bio': form.cleaned_data.get("bio", ""),
                    'hourly_rate': form.cleaned_data.get("hourly_rate") or 0,
                }
            )
            
            if is_google:
                from django.utils.dateparse import parse_datetime
                GoogleCredential.objects.update_or_create(
                    user=user,
                    defaults={
                        'access_token': google_data['access_token'],
                        'refresh_token': google_data['refresh_token'],
                        'scopes': google_data['scopes'],
                        'expires_at': parse_datetime(google_data['expires_at']) or timezone.now() + timezone.timedelta(hours=1)
                    }
                )
                request.session.pop('google_register_data', None)
                
            if not request.user.is_authenticated:
                login(request, user)
            messages.success(
                request, _("Welcome, Teacher! Your profile is pending verification.")
            )
            return redirect("dashboard")
    else:
        form = TeacherRegistrationForm(
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
    return render(
        request, _template(lang, "accounts/register_teacher.html"), {"form": form}
    )


def register_parent(request):
    lang = translation.get_language() or "en"
    
    # Determine if this is a Google registration
    google_data = request.session.get('google_register_data')
    is_google = google_data is not None
    
    # Determine if this is profile completion for a logged-in user
    is_profile_completion = False
    if request.user.is_authenticated:
        try:
            if request.user.profile.parent_profile:
                return redirect('dashboard')
        except Exception:
            pass
        is_profile_completion = True
        
    initial_data = {}
    if is_google:
        initial_data.update({
            'email': google_data['email'],
            'first_name': google_data['first_name'],
            'last_name': google_data['last_name'],
            'username': google_data['email'].split('@')[0],
        })
        
    if request.method == "POST":
        form = ParentRegistrationForm(
            request.POST,
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
        if form.is_valid():
            if is_profile_completion:
                user = request.user
                form.save()
                profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.ROLE_PARENT})
                if not created and profile.role != UserProfile.ROLE_PARENT:
                    profile.role = UserProfile.ROLE_PARENT
                    profile.save(update_fields=['role'])
            else:
                user = form.save()
                profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_PARENT)
                
            parent, created = ParentProfile.objects.get_or_create(profile=profile)
            
            if is_google:
                from django.utils.dateparse import parse_datetime
                GoogleCredential.objects.update_or_create(
                    user=user,
                    defaults={
                        'access_token': google_data['access_token'],
                        'refresh_token': google_data['refresh_token'],
                        'scopes': google_data['scopes'],
                        'expires_at': parse_datetime(google_data['expires_at']) or timezone.now() + timezone.timedelta(hours=1)
                    }
                )
                request.session.pop('google_register_data', None)
                
            if not request.user.is_authenticated:
                login(request, user)
            messages.success(
                request, _("Welcome! You can now manage your children's accounts.")
            )
            return redirect("dashboard")
    else:
        form = ParentRegistrationForm(
            instance=request.user if is_profile_completion else None,
            initial=initial_data,
            is_google=is_google,
            is_profile_completion=is_profile_completion
        )
    return render(
        request, _template(lang, "accounts/register_parent.html"), {"form": form}
    )


@login_required
def dashboard(request):
    lang = translation.get_language() or "en"
    
    # 1. Check if user has UserProfile
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.warning(request, _("Please select a role to complete setting up your profile."))
        return redirect('register_student')
        
    # 2. Check if the subprofile exists. If not, redirect to complete it.
    if profile.is_student:
        try:
            student = profile.student_profile
        except StudentProfile.DoesNotExist:
            messages.warning(request, _("Your Student profile is incomplete. Please complete it to continue."))
            return redirect('register_student')
    elif profile.is_teacher:
        try:
            teacher = profile.teacher_profile
        except TeacherProfile.DoesNotExist:
            messages.warning(request, _("Your Teacher profile is incomplete. Please complete it to continue."))
            return redirect('register_teacher')
    elif profile.is_parent:
        try:
            parent = profile.parent_profile
        except ParentProfile.DoesNotExist:
            messages.warning(request, _("Your Parent profile is incomplete. Please complete it to continue."))
            return redirect('register_parent')

    context = {"profile": profile}
    if profile.is_student:
        student = profile.student_profile
        referrals = Referral.objects.filter(referrer=student).select_related(
            "referred_user__profile__user"
        )
        sessions = student.sessions.all().select_related("teacher__profile__user", "subject")
        enrolled_subjects = Subject.objects.filter(enrollments__student=student, is_active=True)
        pending_session_requests = student.sessions.filter(status=Session.STATUS_REQUESTED).select_related('teacher__profile__user', 'subject')
        context.update(
            {
                "student": student,
                "referrals": referrals,
                "purchases": student.purchases.all()[:5],
                "sessions": sessions,
                "enrolled_subjects": enrolled_subjects,
                "pending_session_requests": pending_session_requests,
            }
        )
    elif profile.is_teacher:
        teacher = profile.teacher_profile
        sessions = teacher.sessions.all().select_related("student__profile__user", "subject")
        teaching_subjects = teacher.subjects.filter(is_active=True)
        context.update({
            "teacher": teacher,
            "sessions": sessions,
            "teaching_subjects": teaching_subjects,
        })
    elif profile.is_parent:
        parent = profile.parent_profile
        children = parent.children.select_related("profile__user").all()
        pending_session_requests = Session.objects.filter(student__in=children, status=Session.STATUS_REQUESTED).select_related('student__profile__user', 'teacher__profile__user', 'subject')
        context.update({
            "parent": parent,
            "children": children,
            "pending_session_requests": pending_session_requests,
        })

    # Get incoming/outgoing link requests
    incoming_requests = ParentChildRequest.objects.filter(
        Q(receiver=request.user) | Q(receiver_email=request.user.email),
        status=ParentChildRequest.STATUS_PENDING
    ).select_related('sender__profile__user')

    outgoing_requests = ParentChildRequest.objects.filter(
        sender=request.user,
        status=ParentChildRequest.STATUS_PENDING
    ).select_related('receiver__profile__user')

    context.update({
        "incoming_requests": incoming_requests,
        "outgoing_requests": outgoing_requests,
    })

    return render(request, _template(lang, "accounts/dashboard.html"), context)


def about_view(request):
    lang = translation.get_language() or "en"
    return render(request, _template(lang, "about.html"), {"lang": lang})


def contact_view(request):
    lang = translation.get_language() or "en"
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        subject = request.POST.get("subject")
        message = request.POST.get("message")
        
        # Simulate storing/emailing the message
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Contact submission from {name} <{email}>: [{subject}] {message}")
        
        messages.success(request, _("Thank you for contacting us! Your message has been sent successfully. We will get back to you soon."))
        return redirect("contact")
        
    return render(request, _template(lang, "contact.html"), {"lang": lang})


def google_login(request):
    if request.user.is_authenticated:
        try:
            if request.user.profile.is_student:
                messages.error(request, _("Students are not allowed to link Google accounts."))
                return redirect('dashboard')
        except Exception:
            pass
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
        except User.DoesNotExist:
            request.session['google_register_data'] = {
                'email': email,
                'first_name': f"Google_{role}",
                'last_name': "User",
                'access_token': 'mock_access_token',
                'refresh_token': 'mock_refresh_token',
                'scopes': 'openid email profile https://www.googleapis.com/auth/calendar',
                'expires_at': (timezone.now() + timezone.timedelta(hours=1)).isoformat(),
            }
            messages.info(request, _("Google login successful! Please complete your profile to finish creating your account."))
            if role == UserProfile.ROLE_PARENT:
                return redirect('register_parent')
            elif role == UserProfile.ROLE_TEACHER:
                return redirect('register_teacher')
            else:
                return redirect('register_student')
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
    except User.DoesNotExist:
        request.session['google_register_data'] = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'access_token': access_token,
            'refresh_token': refresh_token or '',
            'scopes': token_data.get('scope', ''),
            'expires_at': expires_at.isoformat() if hasattr(expires_at, 'isoformat') else str(expires_at),
        }
        messages.info(request, _("Google login successful! Please complete your profile to finish creating your account."))
        if role == UserProfile.ROLE_PARENT:
            return redirect('register_parent')
        elif role == UserProfile.ROLE_TEACHER:
            return redirect('register_teacher')
        else:
            return redirect('register_student')

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
    
    # Check authorization (only teacher of the session)
    is_authorized = False
    if profile.is_teacher and session.teacher == profile.teacher_profile:
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


@login_required
@require_POST
def send_link_request(request):
    profile = request.user.profile
    identifier = request.POST.get("identifier", "").strip()
    if not identifier:
        messages.error(request, _("Please enter a valid username or email address."))
        return redirect("dashboard")

    # Determine role requirements
    if profile.is_student:
        sender_role = "student"
        expected_target_role = UserProfile.ROLE_PARENT
        target_role_display = _("Parent")
    elif profile.is_parent:
        sender_role = "parent"
        expected_target_role = UserProfile.ROLE_STUDENT
        target_role_display = _("Student")
    else:
        messages.error(request, _("Only students or parents can send link requests."))
        return redirect("dashboard")

    # Search for target user
    target_user = User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()
    
    if target_user:
        if target_user == request.user:
            messages.error(request, _("You cannot link your own account to itself."))
            return redirect("dashboard")
            
        if not hasattr(target_user, 'profile') or target_user.profile.role != expected_target_role:
            messages.error(request, _(f"The found user is not registered as a {target_role_display}."))
            return redirect("dashboard")
            
        # Check if already linked
        if profile.is_student:
            student_profile = profile.student_profile
            parent_profile = target_user.profile.parent_profile
        else:
            parent_profile = profile.parent_profile
            student_profile = target_user.profile.student_profile
            
        if parent_profile.children.filter(pk=student_profile.pk).exists():
            messages.warning(request, _("This account is already linked to yours."))
            return redirect("dashboard")

        # Check if request already exists
        existing = ParentChildRequest.objects.filter(
            sender=request.user, receiver=target_user, status=ParentChildRequest.STATUS_PENDING
        ).exists()
        if existing:
            messages.warning(request, _("A pending request has already been sent to this user."))
            return redirect("dashboard")

        ParentChildRequest.objects.create(
            sender=request.user,
            receiver=target_user,
            receiver_email=target_user.email,
            status=ParentChildRequest.STATUS_PENDING
        )
        messages.success(request, _(f"Linking request sent to {target_user.get_full_name() or target_user.username} successfully."))
    else:
        # User not registered yet, we create a pending invitation via email
        if "@" not in identifier:
            messages.error(request, _("User not found. To invite them, please provide a valid email address."))
            return redirect("dashboard")

        # Check if a pending invite already exists for this email
        existing = ParentChildRequest.objects.filter(
            sender=request.user, receiver_email=identifier, status=ParentChildRequest.STATUS_PENDING
        ).exists()
        if existing:
            messages.warning(request, _("A pending request has already been sent to this email."))
            return redirect("dashboard")

        req = ParentChildRequest.objects.create(
            sender=request.user,
            receiver_email=identifier,
            status=ParentChildRequest.STATUS_PENDING
        )
        
        # Build invitation link
        invite_link = request.build_absolute_uri(reverse('accept_invite_link') + f"?token={req.token}")
        messages.success(
            request,
            _(f"Invitation created for {identifier}! Since they are not registered yet, please share this invitation link with them to connect once they register: {invite_link}")
        )
        # Store in session for quick access
        request.session['last_invite_link'] = invite_link
        request.session['last_invite_email'] = identifier

    return redirect("dashboard")


@login_required
@require_POST
def accept_link_request(request, request_id):
    req = get_object_or_404(ParentChildRequest, pk=request_id)
    
    # Verify the logged in user is the receiver
    if req.receiver != request.user and req.receiver_email != request.user.email:
        messages.error(request, _("You are not authorized to accept this request."))
        return redirect("dashboard")
        
    if req.status != ParentChildRequest.STATUS_PENDING:
        messages.error(request, _("This request has already been processed."))
        return redirect("dashboard")
        
    # Process linking
    sender = req.sender
    receiver = request.user
    
    if sender.profile.is_parent and receiver.profile.is_student:
        parent_profile = sender.profile.parent_profile
        student_profile = receiver.profile.student_profile
    elif sender.profile.is_student and receiver.profile.is_parent:
        parent_profile = receiver.profile.parent_profile
        student_profile = sender.profile.student_profile
    else:
        messages.error(request, _("Account roles are incompatible for linking."))
        return redirect("dashboard")
        
    parent_profile.children.add(student_profile)
    req.status = ParentChildRequest.STATUS_ACCEPTED
    req.receiver = receiver
    req.receiver_email = receiver.email
    req.save()
    
    messages.success(request, _(f"Successfully linked accounts with {sender.get_full_name() or sender.username}!"))
    return redirect("dashboard")


@login_required
@require_POST
def reject_link_request(request, request_id):
    req = get_object_or_404(ParentChildRequest, pk=request_id)
    
    # Verify the logged in user is the receiver
    if req.receiver != request.user and req.receiver_email != request.user.email:
        messages.error(request, _("You are not authorized to reject this request."))
        return redirect("dashboard")
        
    if req.status != ParentChildRequest.STATUS_PENDING:
        messages.error(request, _("This request has already been processed."))
        return redirect("dashboard")
        
    req.status = ParentChildRequest.STATUS_REJECTED
    req.save()
    messages.info(request, _("Request declined."))
    return redirect("dashboard")


def accept_invite_link(request):
    token = request.GET.get("token") or request.session.get("pending_invite_token")
    if not token:
        messages.error(request, _("No invitation token provided."))
        return redirect("home")
        
    req = get_object_or_404(ParentChildRequest, token=token)
    
    if req.status != ParentChildRequest.STATUS_PENDING:
        messages.error(request, _("This invitation link has already been used or expired."))
        return redirect("home")
        
    if not request.user.is_authenticated:
        # Save token in session so we can resume after login/registration
        request.session["pending_invite_token"] = token
        messages.info(request, _("Please log in or register an account to accept this invitation."))
        return redirect(reverse('login') + f"?next={request.path}")
        
    # User is logged in
    sender = req.sender
    if sender == request.user:
        messages.error(request, _("You cannot accept your own invitation link."))
        if "pending_invite_token" in request.session:
            del request.session["pending_invite_token"]
        return redirect("dashboard")
        
    # Check role compatibility
    sender_profile = sender.profile
    receiver_profile = request.user.profile
    
    is_compatible = False
    if sender_profile.is_parent and receiver_profile.is_student:
        is_compatible = True
    elif sender_profile.is_student and receiver_profile.is_parent:
        is_compatible = True
        
    if not is_compatible:
        role_sender_display = sender_profile.get_role_display()
        role_receiver_display = receiver_profile.get_role_display()
        messages.error(
            request, 
            _(f"Role mismatch. The invitation was sent by a {role_sender_display}, but you are logged in as a {role_receiver_display}. You cannot link accounts of the same role.")
        )
        if "pending_invite_token" in request.session:
            del request.session["pending_invite_token"]
        return redirect("dashboard")
        
    # If request is POST, accept it
    if request.method == "POST":
        if sender_profile.is_parent:
            parent_profile = sender_profile.parent_profile
            student_profile = receiver_profile.student_profile
        else:
            parent_profile = receiver_profile.parent_profile
            student_profile = sender_profile.student_profile
            
        parent_profile.children.add(student_profile)
        req.status = ParentChildRequest.STATUS_ACCEPTED
        req.receiver = request.user
        req.receiver_email = request.user.email
        req.save()
        
        if "pending_invite_token" in request.session:
            del request.session["pending_invite_token"]
            
        messages.success(request, _(f"Successfully linked accounts with {sender.get_full_name() or sender.username}!"))
        return redirect("dashboard")
        
    # Render confirmation landing page
    lang = translation.get_language() or "en"
    return render(
        request, 
        _template(lang, "accounts/confirm_link.html"), 
        {"req": req, "sender": sender, "lang": lang}
    )


@login_required
@require_POST
def generate_invite_link(request):
    profile = request.user.profile
    if not (profile.is_student or profile.is_parent):
        messages.error(request, _("Only students or parents can generate invitation links."))
        return redirect("dashboard")
        
    req = ParentChildRequest.objects.create(
        sender=request.user,
        status=ParentChildRequest.STATUS_PENDING
    )
    
    invite_link = request.build_absolute_uri(reverse('accept_invite_link') + f"?token={req.token}")
    messages.success(request, _("Invitation link generated successfully! Share it to link accounts."))
    request.session['last_invite_link'] = invite_link
    return redirect("dashboard")

