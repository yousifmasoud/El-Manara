from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import translation

from .models import Subject, HourlyPackage, Purchase


def packages_view(request):
    packages = HourlyPackage.objects.filter(is_active=True).order_by('hours')
    lang = translation.get_language() or 'en'
    return render(request, 'courses/packages.html', {'packages': packages, 'lang': lang})


@login_required
def purchase_package(request):
    if request.method != 'POST':
        return redirect('packages')

    package_id = request.POST.get('package_id')
    package = get_object_or_404(HourlyPackage, pk=package_id, is_active=True)

    try:
        student = request.user.profile.student_profile
    except Exception:
        messages.error(request, _('Only students can purchase packages.'))
        return redirect('packages')

    # Placeholder payment — in production, integrate Stripe/Moyasar here
    purchase = Purchase(student=student, package=package)
    purchase.save()

    # Add hours to student balance
    student.hourly_balance += package.hours
    student.save(update_fields=['hourly_balance'])

    messages.success(
        request,
        _(f'Successfully purchased {package.hours} hours! Your new balance is {student.hourly_balance}h.'),
    )
    return redirect('dashboard')
