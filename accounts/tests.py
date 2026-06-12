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
        """Test mock callback view for a non-existing user redirects them to register page."""
        # Clean user before test
        User.objects.filter(username='google_student').delete()

        response = self.client.get(reverse('google_callback') + '?code=mock_oauth_code_xyz')
        self.assertRedirects(response, reverse('register_student'))

        # Check user is NOT created
        self.assertFalse(User.objects.filter(email='student@google.com').exists())

    def test_google_callback_mock_mode_existing_user(self):
        """Test mock callback view logs in an existing user."""
        existing_user = User.objects.create_user(
            username="google_student",
            email="student@google.com",
            password="password123"
        )
        profile = UserProfile.objects.create(user=existing_user, role=UserProfile.ROLE_STUDENT)
        StudentProfile.objects.create(profile=profile)

        response = self.client.get(reverse('google_callback') + '?code=mock_oauth_code_xyz')
        self.assertRedirects(response, reverse('dashboard'))

        # Check credential is saved
        cred = GoogleCredential.objects.get(user=existing_user)
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
    def test_google_callback_prod_mode_anonymous(self, mock_get, mock_post):
        """Test prod callback redirects unregistered user to register page."""
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
        self.assertRedirects(response, reverse('register_student'))

        # Check user is NOT created
        self.assertFalse(User.objects.filter(email='prod_google_user@test.com').exists())

    @override_settings(GOOGLE_CLIENT_ID="real-client-id", GOOGLE_CLIENT_SECRET="real-secret")
    @patch('requests.post')
    @patch('requests.get')
    def test_google_callback_prod_mode_existing(self, mock_get, mock_post):
        """Test prod callback logs in an existing registered user."""
        existing_user = User.objects.create_user(
            username="charlie_brown",
            email="prod_google_user@test.com",
            password="password123"
        )
        profile = UserProfile.objects.create(user=existing_user, role=UserProfile.ROLE_STUDENT)
        StudentProfile.objects.create(profile=profile)

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

        # Check Google credential exists
        cred = GoogleCredential.objects.get(user=existing_user)
        self.assertEqual(cred.access_token, 'prod_access_token_123')

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

    def test_student_cannot_create_meet(self):
        """Test student gets redirected and the Google Meet link is NOT created."""
        self.client.login(username="student_user", password="password123")
        url = reverse('create_instant_meeting', args=[self.session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        self.session.refresh_from_db()
        self.assertEqual(self.session.meeting_link, "")

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
        self.teacher.subjects.add(self.subject)

        # Enroll students in the subject so they can be scheduled
        from courses.models import StudentEnrollment
        StudentEnrollment.objects.create(student=self.student1, subject=self.subject)
        StudentEnrollment.objects.create(student=self.student2, subject=self.subject)

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
        """Test teacher can request to schedule a session, creating a requested session with no immediate deduction."""
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
        
        # Verify session is created with requested status
        session = Session.objects.filter(teacher=self.teacher, student=self.student1).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.duration_minutes, 90)
        self.assertEqual(session.status, Session.STATUS_REQUESTED)
        
        # Verify student balance is NOT deducted
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 5.0)

    def test_teacher_schedules_student_insufficient_balance_succeeds(self):
        """Test teacher scheduling succeeds even if student has zero balance, since it's just a request."""
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
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify requested session created
        session = Session.objects.filter(teacher=self.teacher, student=self.student2).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, Session.STATUS_REQUESTED)

    def test_student_accepts_session_successfully(self):
        """Test student can accept a session request, which schedules it and deducts credit."""
        session = Session.objects.create(
            student=self.student1,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=90,
            status=Session.STATUS_REQUESTED
        )
        self.client.login(username="student_user1", password="password123")
        url = reverse('accept_session', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_SCHEDULED)
        
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 3.5)

    def test_student_accepts_session_insufficient_balance_fails(self):
        """Test student accepting a session request fails if they have insufficient balance."""
        session = Session.objects.create(
            student=self.student2,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=60,
            status=Session.STATUS_REQUESTED
        )
        self.client.login(username="student_user2", password="password123")
        url = reverse('accept_session', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_REQUESTED)  # remains requested
        
        self.student2.refresh_from_db()
        self.assertEqual(float(self.student2.hourly_balance), 0.0)

    def test_student_rejects_session(self):
        """Test student can reject a session request, changing its status to canceled without deducting credit."""
        session = Session.objects.create(
            student=self.student1,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=60,
            status=Session.STATUS_REQUESTED
        )
        self.client.login(username="student_user1", password="password123")
        url = reverse('reject_session', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_CANCELED)
        
        self.student1.refresh_from_db()
        self.assertEqual(float(self.student1.hourly_balance), 5.0)

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

    def test_teacher_cannot_schedule_unapproved_subject(self):
        """Test teacher scheduling a session for a subject they are not approved to teach fails validation."""
        unapproved_subject = Subject.objects.create(
            name_en="Chemistry",
            slug="chemistry",
            is_active=True
        )
        self.client.login(username="teacher_user", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=3)
        post_data = {
            'student': self.student1.id,
            'subject': unapproved_subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT10:00'),
            'duration_minutes': 60,
            'notes': "Review session"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'subject', "Select a valid choice. That choice is not one of the available choices.")

    def test_teacher_only_views_students_in_approved_subjects(self):
        """Test teacher can only view students enrolled in subjects the teacher is approved to teach."""
        # Setup a new student 3 who is NOT enrolled in self.subject (Physics)
        student_user3 = User.objects.create_user(
            username="student_user3",
            email="student3@test.com",
            password="password123"
        )
        student_prof3 = UserProfile.objects.create(user=student_user3, role=UserProfile.ROLE_STUDENT)
        student3 = StudentProfile.objects.create(profile=student_prof3, hourly_balance=Decimal('5.0'))

        self.client.login(username="teacher_user", password="password123")
        response = self.client.get(reverse('create_session'))
        self.assertEqual(response.status_code, 200)
        
        # Verify student1 and student2 (who are enrolled in Physics) are in the queryset/dropdown options
        # and student3 is NOT in the student queryset
        form = response.context['form']
        student_queryset = form.fields['student'].queryset
        self.assertIn(self.student1, student_queryset)
        self.assertIn(self.student2, student_queryset)
        self.assertNotIn(student3, student_queryset)


class TestParentChildLinkingAndEnrollment(TestCase):
    def setUp(self):
        translation.activate('en')
        from accounts.models import ParentProfile
        
        # Setup academic subjects
        self.subject = Subject.objects.create(
            name_en="Chemistry",
            name_ar="كيمياء",
            slug="chemistry",
            is_active=True
        )

        # Setup parent user
        self.parent_user = User.objects.create_user(
            username="parent_user",
            email="parent@test.com",
            password="password123",
            first_name="Dad"
        )
        self.parent_profile = UserProfile.objects.create(
            user=self.parent_user,
            role=UserProfile.ROLE_PARENT
        )
        self.parent_subprofile = ParentProfile.objects.create(
            profile=self.parent_profile
        )

        # Setup student user
        self.student_user = User.objects.create_user(
            username="student_user",
            email="student@test.com",
            password="password123",
            first_name="Kid"
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
            first_name="Prof"
        )
        self.teacher_profile = UserProfile.objects.create(
            user=self.teacher_user,
            role=UserProfile.ROLE_TEACHER
        )
        self.teacher_subprofile = TeacherProfile.objects.create(
            profile=self.teacher_profile,
            hourly_rate=60
        )

    def test_send_link_request_by_username(self):
        """Test sending a linking request using target username."""
        self.client.login(username="parent_user", password="password123")
        url = reverse('send_link_request')
        response = self.client.post(url, {'identifier': 'student_user'})
        self.assertRedirects(response, reverse('dashboard'))
        
        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.filter(sender=self.parent_user, receiver=self.student_user).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, ParentChildRequest.STATUS_PENDING)

    def test_send_link_request_email_invitation(self):
        """Test sending linking request to an unregistered email generates an invite token."""
        self.client.login(username="parent_user", password="password123")
        url = reverse('send_link_request')
        response = self.client.post(url, {'identifier': 'unregistered_kid@test.com'})
        self.assertRedirects(response, reverse('dashboard'))

        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.filter(sender=self.parent_user, receiver_email='unregistered_kid@test.com').first()
        self.assertIsNotNone(req)
        self.assertTrue(len(req.token) > 0)

    def test_accept_link_request(self):
        """Test student accepting parent's linking request."""
        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.create(
            sender=self.parent_user,
            receiver=self.student_user,
            receiver_email=self.student_user.email
        )
        
        self.client.login(username="student_user", password="password123")
        url = reverse('accept_link_request', args=[req.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        req.refresh_from_db()
        self.assertEqual(req.status, ParentChildRequest.STATUS_ACCEPTED)
        self.assertTrue(self.parent_subprofile.children.filter(pk=self.student_subprofile.pk).exists())

    def test_reject_link_request(self):
        """Test student rejecting parent's request."""
        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.create(
            sender=self.parent_user,
            receiver=self.student_user,
            receiver_email=self.student_user.email
        )
        
        self.client.login(username="student_user", password="password123")
        url = reverse('reject_link_request', args=[req.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        req.refresh_from_db()
        self.assertEqual(req.status, ParentChildRequest.STATUS_REJECTED)
        self.assertFalse(self.parent_subprofile.children.filter(pk=self.student_subprofile.pk).exists())

    def test_accept_invite_link_flow(self):
        """Test accepting a shared invite token confirms linking on landing page."""
        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.create(
            sender=self.parent_user,
            receiver_email=self.student_user.email
        )
        
        self.client.login(username="student_user", password="password123")
        # GET confirm landing page
        landing_url = reverse('accept_invite_link') + f"?token={req.token}"
        response = self.client.get(landing_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link Account Request")

        # POST confirm to accept
        response = self.client.post(landing_url)
        self.assertRedirects(response, reverse('dashboard'))
        
        req.refresh_from_db()
        self.assertEqual(req.status, ParentChildRequest.STATUS_ACCEPTED)
        self.assertTrue(self.parent_subprofile.children.filter(pk=self.student_subprofile.pk).exists())

    def test_student_enrollment(self):
        """Test student direct enrollment in a subject."""
        self.client.login(username="student_user", password="password123")
        response = self.client.post(reverse('enroll_in_course'), {'subject_id': self.subject.id})
        self.assertRedirects(response, reverse('courses_list'))

        from courses.models import StudentEnrollment
        enrollment = StudentEnrollment.objects.filter(student=self.student_subprofile, subject=self.subject).exists()
        self.assertTrue(enrollment)

    def test_parent_enroll_child(self):
        """Test parent enrolling their linked child in a subject."""
        # Link child first
        self.parent_subprofile.children.add(self.student_subprofile)

        self.client.login(username="parent_user", password="password123")
        response = self.client.post(reverse('enroll_in_course'), {
            'subject_id': self.subject.id,
            'child_id': self.student_subprofile.id
        })
        self.assertRedirects(response, reverse('courses_list'))

        from courses.models import StudentEnrollment
        enrollment = StudentEnrollment.objects.filter(student=self.student_subprofile, subject=self.subject).exists()
        self.assertTrue(enrollment)

    def test_teacher_request_to_teach(self):
        """Test teacher proposing to teach a subject, then admin action approval."""
        self.client.login(username="teacher_user", password="password123")
        response = self.client.post(reverse('request_to_teach'), {
            'subject_id': self.subject.id,
            'proposed_rate': '75.00'
        })
        self.assertRedirects(response, reverse('courses_list'))

        from courses.models import TeacherSubjectRequest
        req = TeacherSubjectRequest.objects.filter(teacher=self.teacher_subprofile, subject=self.subject).first()
        self.assertIsNotNone(req)
        self.assertEqual(float(req.proposed_rate), 75.0)
        self.assertEqual(req.status, TeacherSubjectRequest.STATUS_PENDING)

        # Simulate Admin Approval
        req.status = TeacherSubjectRequest.STATUS_APPROVED
        req.save()

        self.assertTrue(self.teacher_subprofile.subjects.filter(pk=self.subject.pk).exists())

    def test_generate_invite_link_by_student(self):
        """Test student generating a generic invitation link."""
        self.client.login(username="student_user", password="password123")
        response = self.client.post(reverse('generate_invite_link'))
        self.assertRedirects(response, reverse('dashboard'))

        from accounts.models import ParentChildRequest
        req = ParentChildRequest.objects.filter(sender=self.student_user, receiver__isnull=True, receiver_email__isnull=True).first()
        self.assertIsNotNone(req)
        self.assertTrue(len(req.token) > 0)
        self.assertIn(req.token, self.client.session['last_invite_link'])

    def test_teacher_schedule_student_not_enrolled_fails(self):
        """Test teacher scheduling a student who is not enrolled in the subject fails validation."""
        # Approve teacher for Chemistry (self.subject)
        self.teacher_subprofile.subjects.add(self.subject)
        # Create a second subject (Physics) and approve teacher for it
        subject2 = Subject.objects.create(
            name_en="Physics",
            slug="physics",
            is_active=True
        )
        self.teacher_subprofile.subjects.add(subject2)
        # Enroll the student in Physics, so they are in the teacher's student list
        from courses.models import StudentEnrollment
        StudentEnrollment.objects.create(student=self.student_subprofile, subject=subject2)

        self.client.login(username="teacher_user", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=2)
        post_data = {
            'student': self.student_subprofile.id,
            'subject': self.subject.id,  # scheduling Chemistry (self.subject)
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT14:30'),
            'duration_minutes': 60,
            'notes': "Organic Chemistry Lesson"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        # Verify it fails validation and displays form error
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'subject', "The selected student is not enrolled in this subject.")

    def test_teacher_schedule_student_enrolled_success(self):
        """Test teacher scheduling an enrolled student succeeds and creates a pending 'requested' session without deducting balance."""
        # Approve teacher for subject
        self.teacher_subprofile.subjects.add(self.subject)
        # Enroll student first
        from courses.models import StudentEnrollment, Session
        StudentEnrollment.objects.create(student=self.student_subprofile, subject=self.subject)
        self.student_subprofile.hourly_balance = Decimal('10.0')
        self.student_subprofile.save()

        self.client.login(username="teacher_user", password="password123")
        scheduled_time = timezone.now() + timezone.timedelta(days=2)
        post_data = {
            'student': self.student_subprofile.id,
            'subject': self.subject.id,
            'scheduled_at': scheduled_time.strftime('%Y-%m-%dT14:30'),
            'duration_minutes': 60,
            'notes': "Organic Chemistry Lesson"
        }
        response = self.client.post(reverse('create_session'), data=post_data)
        self.assertRedirects(response, reverse('dashboard'))

        # Verify session is created with requested status
        session = Session.objects.filter(student=self.student_subprofile, subject=self.subject).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, Session.STATUS_REQUESTED)

        # Verify student balance is NOT deducted
        self.student_subprofile.refresh_from_db()
        self.assertEqual(float(self.student_subprofile.hourly_balance), 10.0)

    def test_student_accept_session_request(self):
        """Test student accepting teacher's session request deducts balance and updates status to scheduled."""
        from courses.models import Session
        # Create a requested session
        session = Session.objects.create(
            student=self.student_subprofile,
            teacher=self.teacher_subprofile,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=90,
            status=Session.STATUS_REQUESTED
        )
        self.student_subprofile.hourly_balance = Decimal('5.0')
        self.student_subprofile.save()

        self.client.login(username="student_user", password="password123")
        response = self.client.post(reverse('accept_session', args=[session.id]))
        self.assertRedirects(response, reverse('dashboard'))

        # Verify status is scheduled
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_SCHEDULED)

        # Verify balance is deducted (90 mins = 1.5 hours)
        self.student_subprofile.refresh_from_db()
        self.assertEqual(float(self.student_subprofile.hourly_balance), 3.5)

    def test_student_reject_session_request(self):
        """Test student declining teacher's session request cancels session and does not deduct balance."""
        from courses.models import Session
        session = Session.objects.create(
            student=self.student_subprofile,
            teacher=self.teacher_subprofile,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=60,
            status=Session.STATUS_REQUESTED
        )
        self.student_subprofile.hourly_balance = Decimal('5.0')
        self.student_subprofile.save()

        self.client.login(username="student_user", password="password123")
        response = self.client.post(reverse('reject_session', args=[session.id]))
        self.assertRedirects(response, reverse('dashboard'))

        # Verify status is canceled
        session.refresh_from_db()
        self.assertEqual(session.status, Session.STATUS_CANCELED)

        # Verify balance is NOT deducted
        self.student_subprofile.refresh_from_db()
        self.assertEqual(float(self.student_subprofile.hourly_balance), 5.0)

class TestProfileCompletionAndGoogleOAuthFlow(TestCase):
    def setUp(self):
        translation.activate('en')
        self.user = User.objects.create_user(
            username="test_user",
            email="test@user.com",
            password="password123"
        )

    def test_dashboard_redirects_if_missing_student_profile(self):
        """If user has UserProfile role student but no StudentProfile, redirect to register_student."""
        UserProfile.objects.create(user=self.user, role=UserProfile.ROLE_STUDENT)
        self.client.login(username="test_user", password="password123")
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('register_student'))

    def test_google_oauth_signup_flow(self):
        """Test the end-to-end google signup flow: callback saves session data -> form registration completes it."""
        # Clean up username/email if they exist
        User.objects.filter(email='student@google.com').delete()
        
        # 1. Trigger Google callback for non-existing user
        response = self.client.get(reverse('google_callback') + '?code=mock_oauth_code_xyz')
        self.assertRedirects(response, reverse('register_student'))
        
        # Verify session has register data
        google_data = self.client.session.get('google_register_data')
        self.assertIsNotNone(google_data)
        self.assertEqual(google_data['email'], 'student@google.com')
        
        # 2. Submit student registration form using the Google session data (no passwords required)
        post_data = {
            'first_name': 'Google',
            'last_name': 'Student',
            'username': 'googlestudent',
            'email': 'student@google.com',
            'grade_level': 'Grade 11'
        }
        response = self.client.post(reverse('register_student'), data=post_data)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify user, profile, student profile, and google credential were created
        new_user = User.objects.get(email='student@google.com')
        self.assertEqual(new_user.username, 'googlestudent')
        self.assertEqual(new_user.profile.role, UserProfile.ROLE_STUDENT)
        self.assertEqual(new_user.profile.student_profile.grade_level, 'Grade 11')
        
        from accounts.models import GoogleCredential
        cred = GoogleCredential.objects.get(user=new_user)
        self.assertEqual(cred.access_token, 'mock_access_token')
        
        # Verify session is cleaned up
        self.assertNotIn('google_register_data', self.client.session)


class TestStudentGoogleLinkAndTeacherPackagesRestriction(TestCase):
    def setUp(self):
        translation.activate('en')
        from courses.models import Session, Subject
        # Setup student user
        self.student_user = User.objects.create_user(
            username="student_user_rest",
            email="student_rest@test.com",
            password="password123"
        )
        student_prof = UserProfile.objects.create(user=self.student_user, role=UserProfile.ROLE_STUDENT)
        self.student = StudentProfile.objects.create(profile=student_prof)

        # Setup teacher user
        self.teacher_user = User.objects.create_user(
            username="teacher_user_rest",
            email="teacher_rest@test.com",
            password="password123"
        )
        teacher_prof = UserProfile.objects.create(user=self.teacher_user, role=UserProfile.ROLE_TEACHER)
        self.teacher = TeacherProfile.objects.create(profile=teacher_prof)

        # Setup subject
        self.subject = Subject.objects.create(
            name_en="Physics",
            slug="physics",
            is_active=True
        )

    def test_student_cannot_link_google_account(self):
        """Test that logged-in students are prevented from initiating Google linking."""
        self.client.login(username="student_user_rest", password="password123")
        response = self.client.get(reverse('google_login'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_student_cannot_create_instant_meeting(self):
        """Test that a student cannot create an instant meeting link for a session."""
        from courses.models import Session
        session = Session.objects.create(
            student=self.student,
            teacher=self.teacher,
            subject=self.subject,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            duration_minutes=60,
            status=Session.STATUS_SCHEDULED
        )
        self.client.login(username="student_user_rest", password="password123")
        url = reverse('create_instant_meeting', args=[session.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        
        # Verify no meeting link is generated
        session.refresh_from_db()
        self.assertEqual(session.meeting_link, '')

    def test_teacher_cannot_view_packages_page(self):
        """Test that a logged-in teacher is prevented from visiting the packages view."""
        self.client.login(username="teacher_user_rest", password="password123")
        response = self.client.get(reverse('packages'))
        self.assertRedirects(response, reverse('dashboard'))

