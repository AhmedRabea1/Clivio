import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .models import Patient
from .forms import PatientForm
from branches.models import Branch, UserBranchAssignment
from accounts.models import User


@login_required
def patient_list(request):
    user = request.user
    qs = Patient.objects.select_related('clinic_location', 'doctor').filter(clinic=user.clinic)

    # Doctors only see today's confirmed patients assigned to them
    if user.role == 'doctor':
        qs = qs.filter(doctor=user, status=Patient.Status.CONFIRMED, visit_date=timezone.localdate())

    # Filters from query params (super_admin / assistant)
    status = request.GET.get('status')
    branch = request.GET.get('branch')
    doctor = request.GET.get('doctor')
    date   = request.GET.get('date')

    if status:
        qs = qs.filter(status=status)
    if branch:
        qs = qs.filter(clinic_location_id=branch)
    if doctor:
        qs = qs.filter(doctor_id=doctor)
    if date:
        qs = qs.filter(visit_date=date)

    branches = Branch.objects.filter(clinic=user.clinic, is_active=True)
    doctors  = User.objects.filter(clinic=user.clinic, role='doctor', is_active=True)

    return render(request, 'appointments/patients.html', {
        'patients': qs,
        'branches': branches,
        'doctors':  doctors,
        'statuses': Patient.Status.choices,
        'filter_status': status or '',
        'filter_branch': branch or '',
        'filter_doctor': doctor or '',
        'filter_date':   date or '',
    })


@login_required
def patient_create(request):
    user = request.user
    clinic = user.clinic

    # Build branch→doctors map for JS filtering
    branches = Branch.objects.filter(clinic=clinic, is_active=True)
    branch_doctors = {}
    for branch in branches:
        doctor_ids = UserBranchAssignment.objects.filter(
            branch=branch,
            user__role='doctor',
            user__is_active=True,
        ).values_list('user_id', flat=True)
        branch_doctors[str(branch.pk)] = list(
            User.objects.filter(pk__in=doctor_ids).values('id', 'name')
        )

    form = PatientForm(request.POST or None, clinic=clinic)
    if request.method == 'POST' and form.is_valid():
        patient = form.save(commit=False)
        patient.clinic = clinic
        patient.created_by = user
        patient.save()
        messages.success(request, f'Patient {patient.full_name} added successfully.')
        return redirect('patient_list')

    return render(request, 'appointments/patient_form.html', {
        'form': form,
        'title': 'Add Patient',
        'branch_doctors_json': json.dumps(branch_doctors),
    })


@login_required
def patient_edit(request, pk):
    user = request.user
    clinic = user.clinic
    patient = get_object_or_404(Patient, pk=pk, clinic=clinic)

    branches = Branch.objects.filter(clinic=clinic, is_active=True)
    branch_doctors = {}
    for branch in branches:
        doctor_ids = UserBranchAssignment.objects.filter(
            branch=branch,
            user__role='doctor',
            user__is_active=True,
        ).values_list('user_id', flat=True)
        branch_doctors[str(branch.pk)] = list(
            User.objects.filter(pk__in=doctor_ids).values('id', 'name')
        )

    form = PatientForm(request.POST or None, instance=patient, clinic=clinic)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Patient {patient.full_name} updated.')
        return redirect('patient_list')

    return render(request, 'appointments/patient_form.html', {
        'form': form,
        'title': f'Edit {patient.full_name}',
        'patient': patient,
        'branch_doctors_json': json.dumps(branch_doctors),
    })


@login_required
def patient_delete(request, pk):
    user = request.user
    patient = get_object_or_404(Patient, pk=pk, clinic=user.clinic)
    if request.method == 'POST':
        name = patient.full_name
        patient.delete()
        messages.success(request, f'Patient {name} deleted.')
        return redirect('patient_list')
    return render(request, 'appointments/patient_confirm_delete.html', {'patient': patient})
