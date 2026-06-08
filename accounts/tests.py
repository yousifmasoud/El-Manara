from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from unittest.mock import patch, MagicMock, ANY
from decimal import Decimal

from accounts.models import UserProfile, StudentProfile, TeacherProfile, GoogleCredential
from courses.models import Subject, Session

class TestGoogleOAuth(TestCase):
    def setUp(self):
        translation.activate('en')
        # Setup subjects
        self.subject = Subject.objects.create(
            name_en="Test Subject",
            name_ar="مادة اختبارية",
            slug="test-subject",
            is_active=True
        )

        # Setup student user
        self.student_user = User.objects.create_user(
            username="student_user",
            email="student@test.com",
            password="password123",
            first_name="Alice"
        )
        self.student_profile = UserProfile.objects.create(
            user=self.student_user,
            role=UserProfile.ROLE_STUDENT
        )
        self.student_subprofile = StudentProfile.objects.create(
            profile=self.student_profile
        )

        # Setup teacher user
        self.teacher_user = User.objects.create_user(
            username="teacher_user",
            email="teacher@test.com",
            password="password123",
            first_name="Bob"
        )
        self.teacher_profile = UserProfile.objects.create(
            user=self.teacher_user,
            role=UserProfile.ROLE_TEACHER
        )
        self.teacher_subprofile = TeacherProfile.objects.create(
            profile=self.teacher_profile,
            hourly_rate=50
        )

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_google_login_mock_mode(self):
        """Test that google_login redirects to callback with a mock code when client ID is missing."""
        response = self.client.get(reverse('google_login'))
        expected_url = reverse('google_callback') + '?code=mock_oauth_code_xyz'
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @override_settings(GOOGLE_CLIENT_ID="real-client-id-123")
    def test_google_login_prod_mode(self):
        """Test that google_login redirects to Google OAuth url when GOOGLE_CLIENT_ID is set."""
        response = self.client.get(reverse('google_login'))
        self.assertEqual(response.status_code, 302)
        self.assertIn("https://accounts.google.com/o/oauth2/v2/auth", response.url)
        self.assertIn("client_id=real-client-id-123", response.url)

    def test_google_callback_mock_mode_anonymous(self):
        """Test mock callback view for an anonymous user logs in / registers the user."""
        # Clean user before test
        User.objects.filter(username='google_student').delete()

        response = self.client.get(reverse('google_callback') + '?code=mock_oauth_code_xyz')
        self.assertRedirects(response, reverse('dashboard'))

        # Check user is created and logged in
        new_user = User.objects.get(username='google_student')
        self.assertEqual(new_user.email, 'student@google.com')
        self.assertEqual(new_user.profile.role, UserProfile.ROLE_STUDENT)

        # Check credential is saved
        cred = GoogleCredential.objects.get(user=new_user)
        self.assertEqual(cred.access_token, 'mock_access_token')

    def test_google_callback_mock_mode_authenticated(self):
        """Test mock callback view links an existing logged in user."""
        self.client.login(username="teacher_user", password="password123")

        response = self.client.get(reverse('google_callback') + '?code=mock_oauth_code_xyz')
        self.assertRedirects(response, reverse('dashboard'))

        # Check credential is saved to teacher
        cred = GoogleCredential.objects.get(user=self.teacher_user)
        self.assertEqual(cred.access_token, 'mock_access_token')

    @override_settings(GOOGLE_CLIENT_ID="real-client-id", GOOGLE_CLIENT_SECRET="real-secret")
    @patch('requests.post')
    @patch('requests.get')
    def test_google_callback_prod_mode(self, mock_get, mock_post):
        """Test prod callback exchanges tokens, fetches userinfo, logs in, and links user."""
        # Mock token exchange
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            'access_token': 'prod_access_token_123',
            'refresh_token': 'prod_refresh_token_123',
            'expires_in': 3600,
            'scope': 'openid email profile'
        }
        mock_post.return_value = mock_token_resp

        # Mock userinfo fetch
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            'email': 'prod_google_user@test.com',
            'given_name': 'Charlie',
            'family_name': 'Brown'
        }
        mock_get.return_value = mock_userinfo_resp

        response = self.client.get(reverse('google_callback') + '?code=real_oauth_code_abc')
        self.assertRedirects(response, reverse('dashboard'))

        # Check user created
        new_user = User.objects.get(email='prod_google_user@test.com')
        self.assertEqual(new_user.first_name, 'Charlie')
        self.assertEqual(new_user.last_name, 'Brown')

        # Check Google credential exists
        cred = GoogleCredential.objects.get(user=new_user)
        self.assertEqual(cred.access_token, 'prod_access_token_123')
        self.assertEqual(cred.refresh_token, 'prod_refresh_token_123')

class TestCreateInstantMeeting(TestCase):
    def setUp(self):
        translation.activate('en')
        # Setup subjects
        self.subject = Subject.objects.create(
            name_en="Mathematics",
            slug="math",
            is_active=True
        )

        # Student user
        self.student_user = User.objects.create_user(
            username="student_user",
            email="student@test.com",
            password="password123"
        )
        student_prof = UserProfile.objects.create(user=self.student_user, role=UserProfile.ROLE_STUDENT)
        self.student = StudentProfile.objects.create(profile=student_prof)

        # Teacher user 1 (owns session)
        self.teacher_user1 = User.objects.create_user(
            username="teacher_user1",
            email="teacher1@test.com",
            password="password123"
        )
        teacher_prof1 = UserProfile.objects.create(user=self.teacher_user1, role=UserProfile.ROLE_TEACHER)
        self.teacher1 = TeacherProfile.objects.create(profile=teacher_prof1)

        # Teacher user 2 (does not own session)
        self.teacher_user2 = User.objects.create_user(
            username="teacher_user2",
            email="teacher2@test.com",
            password="password123"
        )
        teacher_prof2 = UserProfile.objects.create(user=self.teacher_user2, role=UserProfile.ROLE_TEACHER)
        self.teacher2 = TeacherProfile.objects.create(profile=teacher_prof2)

        # Setup Session
        self.session = Session.objects.create(
            student=self.student,
            teacher=self.teacher1,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
            duration_minutes=60,
            status=Session.STATUS_SCHEDULED
        )

    def test_anonymous_cannot_create_meet(self):
        """Test anonymous user is redirected to login."""
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_student_can_create_meet_successful(self):
        """Test student gets redirected and the Google Meet link is created successfully."""
        self.client.login(username="student_user", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        self.session.refresh_from_db()
        self.assertIn("https://meet.google.com/", self.session.meeting_link)

    def test_unauthorized_teacher_cannot_create_meet(self):
        """Test a teacher who does not own the session cannot create the meet link."""
        self.client.login(username="teacher_user2", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_teacher_without_google_linked_creates_meet_link_directly(self):
        """Test teacher can create the Google Meet link directly even if they haven't linked their Google account."""
        self.client.login(username="teacher_user1", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))

        # Check session meeting link is now populated with Google Meet URL
        self.session.refresh_from_db()
        self.assertIn("https://meet.google.com/", self.session.meeting_link)

    def test_successful_meet_creation_mock_mode(self):
        """Test successful Google Meet link generation in mock mode when credentials exist."""
        # Create GoogleCredential for teacher1
        GoogleCredential.objects.create(
            user=self.teacher_user1,
            access_token='mock_access_token',
            refresh_token='mock_refresh_token',
            scopes='https://www.googleapis.com/auth/calendar',
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )

        self.client.login(username="teacher_user1", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))

        # Check session meeting link is populated with Google Meet URL
        self.session.refresh_from_db()
        self.assertIn("https://meet.google.com/", self.session.meeting_link)

    @override_settings(GOOGLE_CLIENT_ID="real-client-id", GOOGLE_CLIENT_SECRET="real-secret")
    @patch('googleapiclient.discovery.build')
    def test_successful_meet_creation_prod_mode(self, mock_build):
        """Test Google Meet link creation with Google Calendar API calls mocked."""
        # Link google account with real refresh token
        GoogleCredential.objects.create(
            user=self.teacher_user1,
            access_token='prod_access_token',
            refresh_token='prod_refresh_token',
            scopes='https://www.googleapis.com/auth/calendar',
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )

        # Mock the build() service and events() call chain
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        
        mock_build.return_value = mock_service
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        
        # Return mock event with hangoutLink
        mock_insert.execute.return_value = {
            'id': 'google-calendar-event-id-123',
            'hangoutLink': 'https://meet.google.com/abc-defg-hij'
        }

        self.client.login(username="teacher_user1", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))

        # Check session was updated with Google Meet URL
        self.session.refresh_from_db()
        self.assertEqual(self.session.meeting_link, 'https://meet.google.com/abc-defg-hij')

        # Check mock build parameters
        mock_build.assert_called_once_with('calendar', 'v3', credentials=ANY)


class TestSessionSchedulingAndCancellation(TestCase):
    def setUp(self):
        translation.activate('en')
        # Setup subjects
        self.subject = Subject.objects.create(
            name_en="Physics",
            slug="physics",
            is_active=True
        )

        # Setup student 1
        self.student_user1 = User.objects.create_user(
            username="student_user1",
            email="student1@test.com",
            password="password123"
        )
        student_prof1 = UserProfile.objects.create(user=self.student_user1, role=UserProfile.ROLE_STUDENT)
        self.student1 = StudentProfile.objects.create(profile=student_prof1, hourly_balance=Decimal('5.0'))

        # Setup student 2 (has zero balance)
        self.student_user2 = User.objects.create_user(
            username="student_user2",
            email="student2@test.com",
            password="password123"
        )
        student_prof2 = UserProfile.objects.create(user=self.student_user2, role=UserProfile.ROLE_STUDENT)
        self.student2 = StudentProfile.objects.create(profile=student_prof2, hourly_balance=Decimal('0.0'))

        # Setup teacher
        self.teacher_user = User.objects.create_user(
            username="teacher_user",
            email="teacher@test.com",
            password="password123"
        )
        teacher_prof = UserProfile.objects.create(user=self.teacher_user, role=UserProfile.ROLE_TEACHER)
        self.teacher = TeacherProfile.objects.create(profile=teacher_prof)

    def test_student_schedules_session_successfully(self):
        """Test a student with enough balance can schedule a session, and hours are deducted."""
        self.client.login(username="student_user1", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=2)
        post_data = {
            'teacher': self.teacher.id,
            'subject': self.subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT14:30'),
            'duration_minutes': 60,
            'notes': "Help with gravity homework"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify session is created and assigned
        session = Session.objects.filter(student=self.student1, subject=self.subject).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.duration_minutes, 60)
        self.assertEqual(session.status, Session.STATUS_SCHEDULED)
        
        # Verify hours are deducted
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 4.0)

    def test_student_insufficient_balance_fails(self):
        """Test scheduling fails if the student has insufficient hourly balance."""
        self.client.login(username="student_user2", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=2)
        post_data = {
            'teacher': self.teacher.id,
            'subject': self.subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT14:30'),
            'duration_minutes': 60,
            'notes': "Physics review"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        # Should stay on page and show form validation error
        self.assertEqual(response.status_code, 200)
        self.assertIn("does not have enough hours", response.content.decode('utf-8'))
        
        # Verify no session created
        self.assertEqual(Session.objects.filter(student=self.student2).count(), 0)

    def test_teacher_schedules_session_successfully(self):
        """Test teacher can schedule a session with a student, deducting student's hours."""
        self.client.login(username="teacher_user", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=3)
        post_data = {
            'student': self.student1.id,
            'subject': self.subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT10:00'),
            'duration_minutes': 90, # 1.5 hours
            'notes': "Mechanics intensive"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify session is created
        session = Session.objects.filter(teacher=self.teacher, student=self.student1).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.duration_minutes, 90)
        
        # Verify student balance is deducted by 1.5 hours
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 3.5)

    def test_teacher_schedules_insufficient_student_balance_fails(self):
        """Test teacher scheduling fails if the chosen student has insufficient balance."""
        self.client.login(username="teacher_user", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=3)
        post_data = {
            'student': self.student2.id,
            'subject': self.subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT10:00'),
            'duration_minutes': 60,
            'notes': "Mechanics"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("does not have enough hours", response.content.decode('utf-8'))

    def test_cancel_session_refunds_hours(self):
        """Test session cancellation updates status and refunds hours to the student."""
        # Create a pre-existing session
        session = Session.objects.create(
            student=self.student1,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
            duration_minutes=120, # 2 hours
            status=Session.STATUS_SCHEDULED
        )
        # Deduct hours manually first since we didn't use the form to create this test session
        self.student1.hourly_balance -= Decimal('2.0')
        self.student1.save()
        
        # Log in as teacher to cancel it
        self.client.login(username="teacher_user", password="password123")
        url = reverse('cancel_session', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Check session is canceled
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_CANCELED)
        
        # Check student hours are refunded
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 5.0)

    def test_unauthorized_user_cannot_cancel_session(self):
        """Test that user cannot cancel a session they are not associated with."""
        session = Session.objects.create(
            student=self.student1,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
            duration_minutes=60,
            status=Session.STATUS_SCHEDULED
        )
        # Log in as student 2 (unrelated to the session)
        self.client.login(username="student_user2", password="password123")
        url = reverse('cancel_session', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify session is not canceled
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_SCHEDULED)

