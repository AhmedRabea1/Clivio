import json
from collections import defaultdict

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import LoginForm, UserForm, ConfigurationForm, DoctorForm
from .models import User, Configuration, Doctor
from branches.models import UserBranchAssignment


def login_view(request):
    if request.user.is_authenticated:
        return redirect('branch_list' if request.user.is_super_admin else 'dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        if user.is_super_admin:
            return redirect('branch_list')
        if user.role == 'doctor':
            return redirect('patient_list')
        return redirect('dashboard')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    from appointments.models import Patient
    from django.utils import timezone
    user = request.user

    # Doctors land on today's patient list directly
    if user.role == 'doctor':
        return redirect('patient_list')

    qs = Patient.objects.filter(clinic=user.clinic)
    context = {
        'total_users':    User.objects.filter(clinic=user.clinic).count() if user.clinic else 0,
        'total_branches': user.clinic.branches.count() if user.clinic else 0,
        'total_patients': qs.count(),
        'today_patients': qs.filter(visit_date=timezone.localdate()).count(),
        'recent_patients': qs.select_related('clinic_location', 'doctor').order_by('-created_at')[:10],
    }
    return render(request, 'dashboard.html', context)


@login_required
def user_list(request):
    users = User.objects.select_related('clinic').filter(clinic=request.user.clinic)
    return render(request, 'accounts/users.html', {'users': users})


@login_required
def user_create(request):
    from branches.models import Branch, UserBranchAssignment
    branches = Branch.objects.filter(clinic=request.user.clinic, is_active=True)
    form = UserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.clinic = request.user.clinic
        password = form.cleaned_data.get('password')
        if not password:
            messages.error(request, 'Password is required for new users.')
            return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Add User', 'branches': branches})
        user.set_password(password)
        user.save()
        branch_ids = request.POST.getlist('branch_ids')
        for bid in branch_ids:
            try:
                branch = branches.get(pk=bid)
                UserBranchAssignment.objects.get_or_create(
                    user=user, branch=branch, defaults={'assigned_by': request.user}
                )
            except Branch.DoesNotExist:
                pass
        messages.success(request, f'User {user.name} created successfully.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Add User', 'branches': branches})


@login_required
def user_edit(request, pk):
    from branches.models import Branch, UserBranchAssignment
    user = get_object_or_404(User, pk=pk, clinic=request.user.clinic)
    branches = Branch.objects.filter(clinic=request.user.clinic, is_active=True)
    assigned_ids = list(user.branch_assignments.values_list('branch_id', flat=True))
    form = UserForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        branch_ids = request.POST.getlist('branch_ids')
        # Remove unselected, add new
        user.branch_assignments.exclude(branch_id__in=branch_ids).delete()
        for bid in branch_ids:
            try:
                branch = branches.get(pk=bid)
                UserBranchAssignment.objects.get_or_create(
                    user=user, branch=branch, defaults={'assigned_by': request.user}
                )
            except Branch.DoesNotExist:
                pass
        messages.success(request, f'User {user.name} updated successfully.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Edit {user.name}',
        'user_obj': user,
        'branches': branches,
        'assigned_ids': assigned_ids,
    })


@login_required
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk, clinic=request.user.clinic)
    if request.method == 'POST':
        name = user.name
        user.delete()
        messages.success(request, f'User {name} deleted.')
        return redirect('user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'user_obj': user})


def _parse_doctor_schedules(request):
    """
    Reads parallel POST lists (slot_branch, slot_day, slot_from, slot_to).
    Returns (grouped, error_string). grouped = {branch_id: [(day, from, to), ...]}
    Validates no duplicates and no overlaps per (branch, day).
    """
    branches = request.POST.getlist('slot_branch')
    days     = request.POST.getlist('slot_day')
    froms    = request.POST.getlist('slot_from')
    tos      = request.POST.getlist('slot_to')

    grouped = defaultdict(list)
    for bid, day, from_t, to_t in zip(branches, days, froms, tos):
        if not all([bid, day, from_t, to_t]):
            continue
        grouped[bid].append((int(day), from_t, to_t))

    for bid, slots in grouped.items():
        by_day = defaultdict(list)
        for day, from_t, to_t in slots:
            by_day[day].append((from_t, to_t))
        for day, day_slots in by_day.items():
            seen = set()
            for pair in day_slots:
                if pair in seen:
                    return None, 'Duplicate time slots found. Please remove duplicates.'
                seen.add(pair)
            sorted_slots = sorted(day_slots)
            for i in range(len(sorted_slots) - 1):
                if sorted_slots[i][1] > sorted_slots[i + 1][0]:
                    return None, 'Overlapping time slots found. Slots on the same day must not overlap.'

    return grouped, None


def _save_doctor_schedule_from_grouped(user, grouped, available_branches, assigned_by):
    from branches.models import Branch, UserBranchAssignment, DoctorSchedule
    branch_map = {str(b.pk): b for b in available_branches}
    processed = set()
    for bid, slots in grouped.items():
        branch = branch_map.get(str(bid))
        if not branch:
            continue
        if bid not in processed:
            UserBranchAssignment.objects.get_or_create(
                user=user, branch=branch, defaults={'assigned_by': assigned_by}
            )
            DoctorSchedule.objects.filter(user=user, branch=branch).delete()
            processed.add(bid)
        for day, from_t, to_t in slots:
            DoctorSchedule.objects.create(
                user=user, branch=branch, day=day, from_time=from_t, to_time=to_t
            )
    # Remove assignments for branches no longer scheduled
    user.branch_assignments.exclude(branch_id__in=[int(k) for k in processed]).delete()


@login_required
def doctor_list(request):
    doctors = Doctor.objects.select_related('user').filter(user__clinic=request.user.clinic)
    return render(request, 'accounts/doctors.html', {'doctors': doctors})


@login_required
def doctor_create(request):
    from branches.models import Branch
    branches = Branch.objects.filter(clinic=request.user.clinic, is_active=True)
    form = DoctorForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        if User.objects.filter(clinic=request.user.clinic, email__iexact=email).exists():
            form.add_error('email', 'This email is already registered.')
        else:
            grouped, error = _parse_doctor_schedules(request)
            if error:
                messages.error(request, error)
            else:
                user = User.objects.create(
                    email=email,
                    name=form.cleaned_data['name'],
                    phone=form.cleaned_data.get('phone', ''),
                    role=User.Role.DOCTOR,
                    clinic=request.user.clinic,
                    is_active=form.cleaned_data.get('is_active', True),
                )
                doctor = Doctor.objects.create(user=user, specialty=form.cleaned_data.get('specialty', ''))
                _save_doctor_schedule_from_grouped(user, grouped, branches, request.user)
                messages.success(request, f'Dr. {user.name} created successfully.')
                return redirect('doctor_list')

    return render(request, 'accounts/doctor_form.html', {
        'form': form, 'title': 'Add Doctor', 'branches': branches,
        'existing_schedules_json': 'null',
    })


@login_required
def doctor_edit(request, pk):
    from branches.models import Branch, DoctorSchedule
    doctor = get_object_or_404(Doctor, user__pk=pk, user__clinic=request.user.clinic)
    branches = Branch.objects.filter(clinic=request.user.clinic, is_active=True)

    # Build existing schedule JSON for JS pre-population
    existing = defaultdict(list)
    for a in doctor.user.branch_assignments.select_related('branch').all():
        for s in DoctorSchedule.objects.filter(user=doctor.user, branch=a.branch).order_by('day', 'from_time'):
            existing[str(a.branch.pk)].append({
                'day': s.day, 'from_time': str(s.from_time)[:5], 'to_time': str(s.to_time)[:5]
            })

    form = DoctorForm(request.POST or None, initial={
        'name': doctor.user.name,
        'email': doctor.user.email,
        'phone': doctor.user.phone,
        'specialty': doctor.specialty,
        'is_active': doctor.user.is_active,
    })

    if request.method == 'POST' and form.is_valid():
        new_email = form.cleaned_data['email'].lower()
        email_conflict = User.objects.filter(
            clinic=request.user.clinic, email__iexact=new_email
        ).exclude(pk=doctor.user.pk).exists()
        if email_conflict:
            form.add_error('email', 'This email is already registered.')
        else:
            grouped, error = _parse_doctor_schedules(request)
            if error:
                messages.error(request, error)
            else:
                doctor.user.name = form.cleaned_data['name']
                doctor.user.email = new_email
                doctor.user.phone = form.cleaned_data.get('phone', '')
                doctor.user.is_active = form.cleaned_data.get('is_active', True)
                doctor.user.save()
                doctor.specialty = form.cleaned_data.get('specialty', '')
                doctor.save()
                _save_doctor_schedule_from_grouped(doctor.user, grouped, branches, request.user)
                messages.success(request, f'Dr. {doctor.user.name} updated successfully.')
                return redirect('doctor_list')

    return render(request, 'accounts/doctor_form.html', {
        'form': form,
        'title': f'Edit Dr. {doctor.user.name}',
        'doctor': doctor,
        'branches': branches,
        'existing_schedules_json': json.dumps(dict(existing)),
    })


@login_required
def doctor_delete(request, pk):
    doctor = get_object_or_404(Doctor, user__pk=pk, user__clinic=request.user.clinic)
    if request.method == 'POST':
        name = doctor.user.name
        doctor.user.delete()
        messages.success(request, f'Dr. {name} deleted.')
        return redirect('doctor_list')
    return render(request, 'accounts/doctor_confirm_delete.html', {'doctor': doctor})


@login_required
def configuration_view(request):
    clinic = request.user.clinic
    config = Configuration.objects.filter(clinic=clinic).first()
    form = ConfigurationForm(request.POST or None, request.FILES or None, instance=config)

    if request.method == 'POST' and form.is_valid():
        cfg = form.save(commit=False)
        cfg.clinic = clinic
        cfg.save()
        messages.success(request, 'Configuration saved successfully.')
        return redirect('configuration')

    logo_preview = config.logo.url if config and config.logo else None
    hero_preview = config.hero_image.url if config and config.hero_image else None

    return render(request, 'accounts/configuration.html', {
        'form': form,
        'config': config,
        'logo_preview': logo_preview,
        'hero_preview': hero_preview,
        'title': 'Clinic Configuration',
    })
