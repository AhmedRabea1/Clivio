from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import Branch, UserBranchAssignment
from .serializers import BranchSerializer, BranchUserSerializer, PublicBranchSerializer


# ─── Public branches endpoint ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def api_public_branches(request):
    """GET /api/public/branches — no auth required, returns all active branches with doctor count."""
    qs = Branch.objects.prefetch_related('user_assignments__user').filter(is_active=True).order_by('-created_at')
    serializer = PublicBranchSerializer(qs, many=True)
    return Response({'total': qs.count(), 'results': serializer.data})


# ─── Branch list / create ──────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_branches(request):
    """
    GET  /api/branches  — list all branches for the clinic
    POST /api/branches  — create a new branch (super_admin only)
    """
    if request.method == 'GET':
        qs = Branch.objects.filter(clinic=request.user.clinic).order_by('-created_at')

        # Pagination
        page_size = 10
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        results = qs[start:end]

        base_url = request.build_absolute_uri(request.path)
        next_url = f'{base_url}?page={page + 1}' if end < total else None
        prev_url = f'{base_url}?page={page - 1}' if page > 1 else None

        serializer = BranchSerializer(results, many=True, context={'request': request})
        return Response({
            'total': total,
            'page_size': page_size,
            'page': page,
            'next': next_url,
            'previous': prev_url,
            'results': serializer.data,
        })

    serializer = BranchSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        branch = serializer.save()
        return Response(
            BranchSerializer(branch, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
    errors = serializer.errors
    # Flatten field errors into a single message
    message = next(
        (str(v[0]) for v in errors.values() if v),
        'Invalid data.'
    )
    return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)


# ─── Branch detail / update ────────────────────────────────────────────────────

@api_view(['GET', 'PATCH', 'DELETE'])
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

    if request.method == 'DELETE':
        branch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    try:
        branch = Branch.objects.get(pk=pk, clinic=request.user.clinic)
    except Branch.DoesNotExist:
        return Response({'error': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'error': 'is_active field is required.'}, status=status.HTTP_400_BAD_REQUEST)

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
