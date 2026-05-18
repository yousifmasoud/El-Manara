"""
Seed initial subjects (including SAT, IELTS, TOEFL) and hourly packages.
Run with: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from courses.models import Subject, HourlyPackage

SUBJECTS = [
    # (name_en, name_ar, slug, icon_svg, is_test_prep, badge, desc_en, order)
    ("Mathematics", "الرياضيات", "mathematics", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="22" font-weight="bold" fill="#009a9a" font-family="serif">∑</text></svg>""", False, "", "Algebra, geometry, calculus and more.", 1),
    ("Physics", "الفيزياء", "physics", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="20" font-weight="bold" fill="#009a9a" font-family="serif">⚛</text></svg>""", False, "", "Mechanics, waves, electricity and modern physics.", 2),
    ("Chemistry", "الكيمياء", "chemistry", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="20" font-weight="bold" fill="#009a9a">⚗️</text></svg>""", False, "", "Organic, inorganic and physical chemistry.", 3),
    ("Biology", "الأحياء", "biology", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="20" fill="#009a9a">🧬</text></svg>""", False, "", "Cell biology, genetics, ecology and anatomy.", 4),
    ("English", "اللغة الإنجليزية", "english", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="18" font-weight="bold" fill="#009a9a">A</text></svg>""", False, "", "Grammar, literature, writing and reading comprehension.", 5),
    ("Arabic", "اللغة العربية", "arabic", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="18" font-weight="bold" fill="#009a9a" font-family="Cairo,sans-serif">ع</text></svg>""", False, "", "Grammar, literature, writing and expression.", 6),
    ("Computer Science", "علوم الحاسوب", "computer-science", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="16" font-weight="bold" fill="#009a9a">&lt;/&gt;</text></svg>""", False, "", "Programming, algorithms, data structures and web development.", 7),
    ("History", "التاريخ", "history", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="33" text-anchor="middle" font-size="20" fill="#009a9a">🏛</text></svg>""", False, "", "World history, Islamic history and social studies.", 8),
    # Test Prep
    ("SAT Preparation", "التحضير للـ SAT", "sat", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="32" text-anchor="middle" font-size="14" font-weight="bold" fill="#009a9a">SAT</text></svg>""", True, "SAT", "Expert coaching for the SAT — math, reading and writing sections.", 1),
    ("IELTS Preparation", "التحضير للـ IELTS", "ielts", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="32" text-anchor="middle" font-size="11" font-weight="bold" fill="#009a9a">IELTS</text></svg>""", True, "IELTS", "Achieve your target band score with our expert IELTS tutors.", 2),
    ("TOEFL Preparation", "التحضير للـ TOEFL", "toefl", """<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="52" height="52" rx="12" fill="#e0fafa"/><text x="26" y="32" text-anchor="middle" font-size="10" font-weight="bold" fill="#009a9a">TOEFL</text></svg>""", True, "TOEFL", "Master the TOEFL iBT with targeted reading, listening and speaking practice.", 3),
]

PACKAGES = [
    # (hours, price_usd, price_aed, desc_en, desc_ar, is_featured)
    (8,  79.00,  290,  "Perfect for a quick revision boost or a single subject sprint.", "مثالية لمراجعة سريعة أو تعزيز مادة واحدة.", False),
    (16, 149.00, 549,  "Two weeks of focused learning. Ideal for exam prep starts.", "أسبوعان من التعلم المركّز. مثالية لبداية التحضير للامتحانات.", False),
    (24, 215.00, 789,  "A full month of regular sessions. Build strong foundations.", "شهر كامل من الجلسات المنتظمة. ابنِ أسساً متينة.", False),
    (32, 275.00, 999,  "Our most popular package. Consistent progress over 4+ weeks.", "باقتنا الأكثر شعبية. تقدم مستمر لأكثر من 4 أسابيع.", True),
    (40, 330.00, 1199, "Intensive preparation. Recommended before major standardized tests.", "تحضير مكثف. مُوصى به قبل الاختبارات الدولية الكبرى.", False),
    (48, 385.00, 1399, "Semester-long support. Stay ahead all term.", "دعم طوال الفصل الدراسي. ابقَ متقدماً طوال الترم.", False),
    (56, 435.00, 1599, "Extended commitment for transformative results.", "التزام ممتد لنتائج تحويلية.", False),
    (64, 479.00, 1749, "Our best value — 64 hours of unlimited subject access.", "أفضل قيمة — 64 ساعة وصول غير محدود لجميع المواد.", True),
]


class Command(BaseCommand):
    help = "Seed initial subjects and hourly packages."

    def handle(self, *args, **options):
        self.stdout.write("Seeding subjects…")
        for name_en, name_ar, slug, icon_svg, is_test_prep, badge, desc_en, order in SUBJECTS:
            obj, created = Subject.objects.update_or_create(
                slug=slug,
                defaults=dict(
                    name_en=name_en,
                    name_ar=name_ar,
                    icon_svg=icon_svg,
                    is_test_prep=is_test_prep,
                    test_prep_badge=badge,
                    description_en=desc_en,
                    order=order,
                    is_active=True,
                ),
            )
            self.stdout.write(f"  {'Created' if created else 'Updated'}: {name_en}")

        self.stdout.write("Seeding hourly packages…")
        for hours, price, price_aed, desc, desc_ar, featured in PACKAGES:
            obj, created = HourlyPackage.objects.update_or_create(
                hours=hours,
                defaults=dict(
                    price_usd=price,
                    price_aed=price_aed,
                    description_en=desc,
                    description_ar=desc_ar,
                    is_featured=featured,
                    is_active=True,
                ),
            )
            self.stdout.write(f"  {'Created' if created else 'Updated'}: {hours}h package")

        self.stdout.write(self.style.SUCCESS("✅ Seed complete."))
