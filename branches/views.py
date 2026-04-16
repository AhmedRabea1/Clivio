from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Branch, UserBranchAssignment
from .forms import BranchForm, UserBranchAssignmentForm


@login_required
def branch_list(request):
    branches = Branch.objects.select_related('clinic').filter(clinic=request.user.clinic)
    return render(request, 'branches/branches.html', {'branches': branches})


@login_required
def branch_create(request):
    form = BranchForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        branch = form.save(commit=False)
        branch.clinic = request.user.clinic
        branch.save()
        messages.success(request, f'Branch "{branch.name}" created successfully.')
        return redirect('branch_list')
    return render(request, 'branches/branch_form.html', {'form': form, 'title': 'Add Branch'})


@login_required
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk, clinic=request.user.clinic)
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Branch "{branch.name}" updated.')
        return redirect('branch_list')
    return render(request, 'branches/branch_form.html', {'form': form, 'title': f'Edit {branch.name}'})


@login_required
def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk, clinic=request.user.clinic)
    if request.method == 'POST':
        name = branch.name
        branch.delete()
        messages.success(request, f'Branch "{name}" deleted.')
        return redirect('branch_list')
    return render(request, 'branches/branch_confirm_delete.html', {'branch': branch})


@login_required
def manage_branches(request):
    """Assign/unassign staff to branches."""
    clinic = request.user.clinic
    branches = Branch.objects.filter(clinic=clinic, is_active=True).prefetch_related(
        'user_assignments__user'
    )
    form = UserBranchAssignmentForm(request.POST or None)

    # Scope queryset to clinic
    from accounts.models import User
    form.fields['user'].queryset = User.objects.filter(
        clinic=clinic, role__in=['doctor', 'assistant'], is_active=True
    )
    form.fields['branch'].queryset = Branch.objects.filter(clinic=clinic, is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign' and form.is_valid():
            user = form.cleaned_data['user']
            branch = form.cleaned_data['branch']
            _, created = UserBranchAssignment.objects.get_or_create(
                user=user, branch=branch,
                defaults={'assigned_by': request.user}
            )
            if created:
                messages.success(request, f'{user.name} assigned to {branch.name}.')
            else:
                messages.info(request, f'{user.name} is already assigned to {branch.name}.')
            return redirect('manage_branches')
        elif action == 'unassign':
            assignment_id = request.POST.get('assignment_id')
            UserBranchAssignment.objects.filter(pk=assignment_id, branch__clinic=clinic).delete()
            messages.success(request, 'Assignment removed.')
            return redirect('manage_branches')

    return render(request, 'branches/manage_branches.html', {
        'branches': branches,
        'form': form,
    })
