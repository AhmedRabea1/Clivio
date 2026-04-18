from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import LoginForm, UserForm, ConfigurationForm
from .models import User, Configuration
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
