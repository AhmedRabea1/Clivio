from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from .models import Branch, UserBranchAssignment
from .serializers import BranchSerializer, BranchUserSerializer


def _require_super_admin(request):
    if request.user.role != User.Role.SUPER_ADMIN:
        return Response(
            {'error': 'Only super admins can perform this action.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ─── Branch list / create ──────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_branches(request):
    """
    GET  /api/branches  — list all branches for the clinic
    POST /api/branches  — create a new branch (super_admin only)
    """
    if request.method == 'GET':
        qs = Branch.objects.filter(clinic=request.user.clinic).prefetch_related('user_assignments__user')
        serializer = BranchSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    denied = _require_super_admin(request)
    if denied:
        return denied

    serializer = BranchSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        branch = serializer.save()
        return Response(
            BranchSerializer(branch, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Branch detail / update ────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_branch_detail(request, pk):
    """
    GET   /api/branches/:id  — retrieve branch with full details
    PATCH /api/branches/:id  — update branch (super_admin only)
    """
    try:
        branch = Branch.objects.get(pk=pk, clinic=request.user.clinic)
    except Branch.DoesNotExist:
        return Response({'error': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(BranchSerializer(branch, context={'request': request}).data)

    denied = _require_super_admin(request)
    if denied:
        return denied

    serializer = BranchSerializer(branch, data=request.data, partial=True, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(BranchSerializer(branch, context={'request': request}).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Branch status (activate / deactivate) ────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_branch_status(request, pk):
    """
    PATCH /api/branches/:id/status
    Deactivation is blocked if upcoming confirmed appointments exist.
    """
    denied = _require_super_admin(request)
    if denied:
        return denied

    try:
        branch = Branch.objects.get(pk=pk, clinic=request.user.clinic)
    except Branch.DoesNotExist:
        return Response({'error': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'error': 'is_active field is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if not is_active:
        from django.utils import timezone
        from appointments.models import Appointment
        upcoming = Appointment.objects.filter(
            branch=branch,
            status=Appointment.Status.CONFIRMED,
            date_time__gte=timezone.now(),
        ).count()
        if upcoming > 0:
            return Response(
                {
                    'error': f'Cannot deactivate branch. It has {upcoming} upcoming confirmed appointment(s).',
                    'upcoming_appointments': upcoming,
                },
                status=status.HTTP_409_CONFLICT,
            )

    branch.is_active = bool(is_active)
    branch.save()
    return Response({
        'id': branch.id,
        'is_active': branch.is_active,
        'status': 'active' if branch.is_active else 'inactive',
    })


# ─── Branch users ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_branch_users(request, pk):
    """
    GET /api/branches/:id/users?role=doctor|assistant
    Lists users assigned to this branch, filtered by role.
    """
    try:
        branch = Branch.objects.get(pk=pk, clinic=request.user.clinic)
    except Branch.DoesNotExist:
        return Response({'error': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

    assignments = branch.user_assignments.select_related('user').filter(user__is_active=True)
    role = request.query_params.get('role')
    if role:
        assignments = assignments.filter(user__role=role)

    serializer = BranchUserSerializer(assignments, many=True)
    return Response({
        'branch_id': branch.id,
        'branch_name': branch.name,
        'count': assignments.count(),
        'results': serializer.data,
    })
