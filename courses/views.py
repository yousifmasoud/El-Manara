from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from .models import HourlyPackage, Purchase, Subject, Session
from .forms import SessionForm
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal


def _template(lang, name):
    """Return 'ar/<name>' for Arabic, 'en/<name>' for English."""
    prefix = "ar" if (lang or "").startswith("ar") else "en"
    return f"{prefix}/{name}"


def packages_view(request):
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
            elif profile.is_student:
                session.student = profile.student_profile
            
            session.status = Session.STATUS_SCHEDULED
            session.save()
            
            # Deduct hours from student balance
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
