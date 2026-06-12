from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from .models import HourlyPackage, Purchase, Subject, Session, StudentEnrollment, TeacherSubjectRequest
from .forms import SessionForm
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal


def _template(lang, name):
    """Return 'ar/<name>' for Arabic, 'en/<name>' for English."""
    prefix = "ar" if (lang or "").startswith("ar") else "en"
    return f"{prefix}/{name}"


def packages_view(request):
    if request.user.is_authenticated:
        try:
            if request.user.profile.is_teacher:
                messages.error(request, _("Teachers are not allowed to view or purchase packages."))
                return redirect('dashboard')
        except Exception:
            pass
    lang = translation.get_language() or "en"
    packages = HourlyPackage.objects.filter(is_active=True).order_by("hours")
    return render(
        request,
        _template(lang, "courses/packages.html"),
        {"packages": packages, "lang": lang},
    )


@login_required
def purchase_package(request):
    if request.method != "POST":
        return redirect("packages")

    package_id = request.POST.get("package_id")
    package = get_object_or_404(HourlyPackage, pk=package_id, is_active=True)

    try:
        student = request.user.profile.student_profile
    except Exception:
        messages.error(request, _("Only students can purchase packages."))
        return redirect("packages")

    # Placeholder payment — in production, integrate Stripe/Moyasar here
    purchase = Purchase(student=student, package=package)
    purchase.save()

    # Add hours to student balance
    student.hourly_balance += package.hours
    student.save(update_fields=["hourly_balance"])

    messages.success(
        request,
        _(
            f"Successfully purchased {package.hours} hours! Your new balance is {student.hourly_balance}h."
        ),
    )
    return redirect("dashboard")


@login_required
def create_session(request):
    profile = request.user.profile
    lang = translation.get_language() or "en"
    
    if not (profile.is_teacher or profile.is_student):
        messages.error(request, _("Only teachers or students can schedule sessions."))
        return redirect('dashboard')
        
    if request.method == "POST":
        form = SessionForm(request.POST, user=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            if profile.is_teacher:
                session.teacher = profile.teacher_profile
                session.status = Session.STATUS_REQUESTED
                session.save()
                messages.success(request, _("Session request successfully sent to student! It will be scheduled once they accept it."))
            elif profile.is_student:
                session.student = profile.student_profile
                session.status = Session.STATUS_SCHEDULED
                session.save()
                # Deduct hours from student balance immediately
                duration_hours = Decimal(session.duration_minutes) / Decimal(60.0)
                student = session.student
                student.hourly_balance -= duration_hours
                student.save(update_fields=['hourly_balance'])
                messages.success(request, _("Session successfully scheduled!"))
            return redirect('dashboard')
    else:
        form = SessionForm(user=request.user)
        if profile.is_student:
            form.fields['student'].initial = profile.student_profile
        elif profile.is_teacher:
            form.fields['teacher'].initial = profile.teacher_profile
            
    return render(
        request,
        _template(lang, "courses/create_session.html"),
        {"form": form, "profile": profile, "lang": lang},
    )


@login_required
@require_POST
def cancel_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    profile = request.user.profile
    
    # Authorize cancellation
    authorized = False
    if profile.is_teacher and session.teacher == profile.teacher_profile:
        authorized = True
    elif profile.is_student and session.student == profile.student_profile:
        authorized = True
    elif profile.is_parent and session.student in profile.parent_profile.children.all():
        authorized = True
        
    if not authorized:
        messages.error(request, _("You are not authorized to cancel this session."))
        return redirect('dashboard')
        
    if session.status == Session.STATUS_CANCELED:
        messages.warning(request, _("This session has already been canceled."))
        return redirect('dashboard')
        
    session.status = Session.STATUS_CANCELED
    session.save(update_fields=['status'])
    
    # Refund hours
    duration_hours = Decimal(session.duration_minutes) / Decimal(60.0)
    student = session.student
    student.hourly_balance += duration_hours
    student.save(update_fields=['hourly_balance'])
    
    messages.success(request, _("Session successfully canceled and hours refunded."))
    return redirect('dashboard')


def courses_list(request):
    lang = translation.get_language() or "en"
    subjects = Subject.objects.filter(is_active=True).order_by('order', 'name_en')
    
    context = {
        "subjects": subjects,
        "lang": lang,
    }
    
    if request.user.is_authenticated:
        profile = request.user.profile
        context["profile"] = profile
        
        if profile.is_student:
            student = profile.student_profile
            enrolled_subject_ids = set(student.enrollments.values_list('subject_id', flat=True))
            context["enrolled_subject_ids"] = enrolled_subject_ids
            
        elif profile.is_parent:
            parent = profile.parent_profile
            children = parent.children.select_related('profile__user').all()
            context["children"] = children
            
            # Map child to their enrollments
            child_enrollments = {}
            for child in children:
                child_enrollments[child.id] = set(child.enrollments.values_list('subject_id', flat=True))
            context["child_enrollments"] = child_enrollments
            
        elif profile.is_teacher:
            teacher = profile.teacher_profile
            teaching_subject_ids = set(teacher.subjects.values_list('id', flat=True))
            pending_request_subject_ids = set(
                TeacherSubjectRequest.objects.filter(teacher=teacher, status=TeacherSubjectRequest.STATUS_PENDING)
                .values_list('subject_id', flat=True)
            )
            
            context.update({
                "teaching_subject_ids": teaching_subject_ids,
                "pending_request_subject_ids": pending_request_subject_ids,
                "teacher_requests": TeacherSubjectRequest.objects.filter(teacher=teacher).select_related('subject')
            })
            
    return render(request, _template(lang, "courses/course_list.html"), context)


@login_required
@require_POST
def enroll_in_course(request):
    profile = request.user.profile
    subject_id = request.POST.get("subject_id")
    subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
    
    if profile.is_student:
        student = profile.student_profile
        StudentEnrollment.objects.get_or_create(student=student, subject=subject)
        messages.success(request, _(f"Successfully enrolled in {subject.get_name(translation.get_language())}!"))
        
    elif profile.is_parent:
        child_id = request.POST.get("child_id")
        parent = profile.parent_profile
        child = get_object_or_404(parent.children.all(), pk=child_id)
        StudentEnrollment.objects.get_or_create(student=child, subject=subject)
        messages.success(request, _(f"Successfully enrolled {child.profile.user.get_full_name() or child.profile.user.username} in {subject.get_name(translation.get_language())}!"))
        
    else:
        messages.error(request, _("Only students or parents can enroll in courses."))
        
    return redirect("courses_list")


@login_required
@require_POST
def request_to_teach(request):
    profile = request.user.profile
    if not profile.is_teacher:
        messages.error(request, _("Only teachers can request to teach subjects."))
        return redirect("dashboard")
        
    subject_id = request.POST.get("subject_id")
    proposed_rate = request.POST.get("proposed_rate")
    
    subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
    teacher = profile.teacher_profile
    
    # Simple validation
    try:
        rate = Decimal(proposed_rate)
        if rate < 0:
            raise ValueError()
    except Exception:
        messages.error(request, _("Please enter a valid positive hourly rate."))
        return redirect("courses_list")
        
    # Check if already teaching this subject
    if teacher.subjects.filter(pk=subject.pk).exists():
        messages.warning(request, _("You are already approved to teach this subject."))
        return redirect("courses_list")
        
    # Create request
    TeacherSubjectRequest.objects.update_or_create(
        teacher=teacher,
        subject=subject,
        defaults={"proposed_rate": rate, "status": TeacherSubjectRequest.STATUS_PENDING}
    )
    
    messages.success(request, _(f"Request to teach {subject.get_name(translation.get_language())} at ${rate}/hr submitted successfully for review."))
    return redirect("courses_list")


@login_required
@require_POST
def accept_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    profile = request.user.profile
    
    # Check authorization
    authorized = False
    if profile.is_student and session.student == profile.student_profile:
        authorized = True
    elif profile.is_parent and session.student in profile.parent_profile.children.all():
        authorized = True
        
    if not authorized:
        messages.error(request, _("You are not authorized to accept this session request."))
        return redirect('dashboard')
        
    if session.status != Session.STATUS_REQUESTED:
        messages.warning(request, _("This session request is no longer active."))
        return redirect('dashboard')
        
    # Check student balance
    duration_hours = Decimal(session.duration_minutes) / Decimal(60.0)
    student = session.student
    if student.hourly_balance < duration_hours:
        messages.error(request, _(f"Insufficient hourly balance. Required: {duration_hours}h, available: {student.hourly_balance}h. Please buy a package first."))
        return redirect('dashboard')
        
    # Deduct hours & approve session
    student.hourly_balance -= duration_hours
    student.save(update_fields=['hourly_balance'])
    
    session.status = Session.STATUS_SCHEDULED
    session.save(update_fields=['status'])
    
    messages.success(request, _("Session request accepted and scheduled!"))
    return redirect('dashboard')


@login_required
@require_POST
def reject_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    profile = request.user.profile
    
    # Check authorization
    authorized = False
    if profile.is_student and session.student == profile.student_profile:
        authorized = True
    elif profile.is_parent and session.student in profile.parent_profile.children.all():
        authorized = True
    elif profile.is_teacher and session.teacher == profile.teacher_profile:
        authorized = True
        
    if not authorized:
        messages.error(request, _("You are not authorized to decline this session request."))
        return redirect('dashboard')
        
    if session.status != Session.STATUS_REQUESTED:
        messages.warning(request, _("This session request is no longer active."))
        return redirect('dashboard')
        
    session.status = Session.STATUS_CANCELED
    session.save(update_fields=['status'])
    
    messages.info(request, _("Session request declined."))
    return redirect('dashboard')


