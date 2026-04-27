from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User, Configuration, Doctor, AssistantRole, Assistant, Service, Product, Machine
from .serializers import (
    LoginSerializer, UserSerializer,
    UserCreateSerializer, UserUpdateBranchesSerializer,
    ConfigurationSerializer, DoctorSerializer, DoctorCreateSerializer,
    AssistantRoleSerializer, AssistantSerializer, AssistantCreateSerializer,
    ServiceSerializer, ProductSerializer, MachineSerializer,
)
from branches.models import Branch, UserBranchAssignment


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '0.0.0.0')


def _check_rate_limit(ip, max_attempts=5, window=900):
    """Returns (is_limited, attempts_remaining)."""
    key = f'login_rate_{ip}'
    attempts = cache.get(key, 0)
    if attempts >= max_attempts:
        return True, 0
    return False, max_attempts - attempts


def _increment_rate_limit(ip, window=900):
    key = f'login_rate_{ip}'
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, window)


def _clear_rate_limit(ip):
    cache.delete(f'login_rate_{ip}')


def _token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['clinic_id'] = user.clinic_id
    refresh['name'] = user.name
    refresh['token_version'] = user.token_version
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


# ─── Auth endpoints ────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_change_password(request):
    """
    POST /api/auth/change-password
    Body: { password, confirm_password }
    Sets the new password and clears must_change_password flag.
    """
    password         = request.data.get('password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not password or not confirm_password:
        return Response(
            {'error': 'password and confirm_password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if password != confirm_password:
        return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(password) < 6:
        return Response({'error': 'Password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.set_password(password)
    user.must_change_password = False
    user.save()
    return Response({'message': 'Password changed successfully.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    POST /api/auth/login
    Rate-limited: 5 attempts per 15 min per IP.
    Returns JWT access + refresh tokens.
    """
    ip = _get_client_ip(request)
    limited, remaining = _check_rate_limit(ip)
    if limited:
        return Response(
            {'error': 'Too many failed attempts. Try again in 15 minutes.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['username']
    password = serializer.validated_data['password']
    user = authenticate(request, username=email, password=password)

    if not user:
        _increment_rate_limit(ip)
        return Response(
            {'error': 'Invalid email or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {'error': 'This account has been deactivated.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    _clear_rate_limit(ip)
    tokens = _token_pair_for_user(user)

    user_data = {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'clinic_id': user.clinic_id,
        'clinic_name': user.clinic.name if user.clinic else None,
        'must_change_password': user.must_change_password,
    }

    if user.role == User.Role.ASSISTANT:
        try:
            roles = list(user.assistant_profile.roles.values('id', 'role_name'))
            user_data['roles'] = roles
        except Exception:
            user_data['roles'] = []

    return Response({
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': user_data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_refresh(request):
    """POST /api/auth/refresh — rotate refresh token."""
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        refresh = RefreshToken(refresh_token)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })
    except TokenError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """POST /api/auth/logout — blacklist the refresh token."""
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        RefreshToken(refresh_token).blacklist()
        return Response({'message': 'Logged out successfully.'})
    except TokenError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_forgot_password(request):
    """
    POST /api/auth/forgot-password
    Generates a reset token (valid 1h) and sends email.
    """
    email = request.data.get('email', '').lower().strip()
    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Always return 200 to avoid email enumeration
    try:
        user = User.objects.get(email=email, is_active=True)
        token = get_random_string(64)
        cache.set(f'pwd_reset_{token}', user.id, 3600)  # 1 hour
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_mail(
            subject='Reset your Clivio password',
            message=f'Hi {user.name},\n\nClick the link to reset your password:\n{reset_url}\n\nThis link expires in 1 hour.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except User.DoesNotExist:
        pass

    return Response({'message': 'If that email exists, a reset link has been sent.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_reset_password(request):
    """POST /api/auth/reset-password — consume reset token and set new password."""
    token = request.data.get('token', '')
    new_password = request.data.get('password', '')

    if not token or not new_password:
        return Response({'error': 'Token and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user_id = cache.get(f'pwd_reset_{token}')
    if not user_id:
        return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
        user.set_password(new_password)
        user.save()
        cache.delete(f'pwd_reset_{token}')
        return Response({'message': 'Password updated successfully.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


# ─── User endpoints ────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_users(request):
    """
    GET  /api/users?role=doctor|assistant  — list users in clinic
    POST /api/users                         — create doctor or assistant
    """
    if request.method == 'GET':
        qs = User.objects.filter(clinic=request.user.clinic).prefetch_related('branch_assignments__branch')
        role = request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        serializer = UserSerializer(qs, many=True)
        return Response(serializer.data)

    # POST
    serializer = UserCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_user_detail(request, pk):
    """
    GET    /api/users/:id  — retrieve user
    PATCH  /api/users/:id  — update user details
    DELETE /api/users/:id  — delete user (super_admin only)
    """
    try:
        user = User.objects.get(pk=pk, clinic=request.user.clinic)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(UserSerializer(user).data)

    if request.method == 'DELETE':
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = UserCreateSerializer(
        user, data=request.data, partial=True, context={'request': request}
    )
    if serializer.is_valid():
        serializer.save()
        return Response(UserSerializer(user).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_user_status(request, pk):
    """PATCH /api/users/:id/status — activate or deactivate user."""
    try:
        user = User.objects.get(pk=pk, clinic=request.user.clinic)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'error': 'is_active field is required.'}, status=status.HTTP_400_BAD_REQUEST)

    user.is_active = bool(is_active)
    user.save()
    return Response({'id': user.id, 'is_active': user.is_active})


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_user_branches(request, pk):
    """
    POST  /api/users/:id/branches — bulk-add branch assignments
    PATCH /api/users/:id/branches — replace all branch assignments
    """
    try:
        user = User.objects.get(pk=pk, clinic=request.user.clinic)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = UserUpdateBranchesSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    branch_ids = serializer.validated_data['branch_ids']
    branches = Branch.objects.filter(id__in=branch_ids, clinic=request.user.clinic)

    if request.method == 'PATCH':
        # Replace: remove old assignments, add new
        user.branch_assignments.exclude(branch_id__in=branch_ids).delete()

    for branch in branches:
        UserBranchAssignment.objects.get_or_create(
            user=user, branch=branch,
            defaults={'assigned_by': request.user}
        )

    user.refresh_from_db()
    return Response(UserSerializer(user).data)


# ─── Public doctor endpoints ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def api_public_doctors(request):
    """GET /api/public/doctors?branch_id=1 — no auth required."""
    branch_id = request.query_params.get('branch_id')
    if not branch_id:
        return Response({'error': 'branch_id query param is required.'}, status=status.HTTP_400_BAD_REQUEST)

    doctors = Doctor.objects.filter(
        user__branch_assignments__branch_id=branch_id,
        user__is_active=True,
    ).select_related('user').distinct()

    return Response(DoctorSerializer(doctors, many=True).data)


# ─── Doctor endpoints ─────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_doctors(request):
    """
    GET  /api/doctors  — list all doctors in clinic
    POST /api/doctors  — create a new doctor
    """
    if request.method == 'GET':
        doctors = Doctor.objects.filter(
            user__clinic=request.user.clinic
        ).select_related('user')
        return Response(DoctorSerializer(doctors, many=True).data)

    serializer = DoctorCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        doctor = serializer.save()
        return Response(DoctorSerializer(doctor).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_doctor_detail(request, pk):
    """
    GET    /api/doctors/:id  — retrieve doctor  (pk = user.id)
    PATCH  /api/doctors/:id  — update doctor
    DELETE /api/doctors/:id  — delete doctor
    """
    try:
        doctor = Doctor.objects.select_related('user').get(
            user__pk=pk, user__clinic=request.user.clinic
        )
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(DoctorSerializer(doctor).data)

    if request.method == 'DELETE':
        doctor.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = DoctorCreateSerializer(doctor, data=request.data, partial=True, context={'request': request})
    if serializer.is_valid():
        doctor = serializer.save()
        return Response(DoctorSerializer(doctor).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_doctor_status(request, pk):
    """PATCH /api/doctors/:id/status — activate or deactivate doctor."""
    try:
        doctor = Doctor.objects.select_related('user').get(
            user__pk=pk, user__clinic=request.user.clinic
        )
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'error': 'is_active field is required.'}, status=status.HTTP_400_BAD_REQUEST)

    doctor.user.is_active = bool(is_active)
    doctor.user.save()
    return Response({'id': doctor.user.id, 'is_active': doctor.user.is_active})


# ─── Assistant endpoints ──────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_assistants(request):
    """
    GET  /api/assistants  — list all assistants in clinic
    POST /api/assistants  — create assistant
    """
    if request.method == 'GET':
        assistants = Assistant.objects.filter(
            user__clinic=request.user.clinic
        ).select_related('user', 'branch').prefetch_related('roles')
        return Response(AssistantSerializer(assistants, many=True).data)

    serializer = AssistantCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        assistant = serializer.save()
        return Response(AssistantSerializer(assistant).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_assistant_detail(request, pk):
    """
    GET    /api/assistants/:id  — retrieve assistant  (pk = user.id)
    PATCH  /api/assistants/:id  — update assistant
    DELETE /api/assistants/:id  — delete assistant
    """
    try:
        assistant = Assistant.objects.select_related('user', 'branch').prefetch_related('roles').get(
            user__pk=pk, user__clinic=request.user.clinic
        )
    except Assistant.DoesNotExist:
        return Response({'error': 'Assistant not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(AssistantSerializer(assistant).data)

    if request.method == 'DELETE':
        assistant.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    roles_before = set(assistant.roles.values_list('id', flat=True))
    serializer = AssistantCreateSerializer(
        assistant, data=request.data, partial=True, context={'request': request}
    )
    if serializer.is_valid():
        assistant = serializer.save()
        if 'role_ids' in request.data:
            roles_after = set(assistant.roles.values_list('id', flat=True))
            if roles_before != roles_after:
                assistant.user.token_version += 1
                assistant.user.save(update_fields=['token_version'])
        return Response(AssistantSerializer(assistant).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_assistant_status(request, pk):
    """PATCH /api/assistants/:id/status — activate or deactivate assistant."""
    try:
        assistant = Assistant.objects.select_related('user').get(
            user__pk=pk, user__clinic=request.user.clinic
        )
    except Assistant.DoesNotExist:
        return Response({'error': 'Assistant not found.'}, status=status.HTTP_404_NOT_FOUND)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'error': 'is_active field is required.'}, status=status.HTTP_400_BAD_REQUEST)

    assistant.user.is_active = bool(is_active)
    assistant.user.save()
    return Response({'id': assistant.user.id, 'is_active': assistant.user.is_active})


# ─── Assistant roles endpoint ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_assistant_roles(request):
    """GET /api/assistant-roles — list all predefined assistant roles."""
    roles = AssistantRole.objects.all()
    return Response(AssistantRoleSerializer(roles, many=True).data)


# ─── Public configuration endpoint ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def api_public_configuration(request):
    """GET /api/public/configuration — no auth required, for external portals."""
    config = Configuration.objects.select_related('clinic').first()
    if not config:
        return Response({'detail': 'No configuration found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ConfigurationSerializer(config, context={'request': request}).data)


# ─── Configuration endpoint ────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([AllowAny])
def api_configuration(request):
    """
    GET   /api/configuration  — retrieve clinic configuration (all roles)
    POST  /api/configuration  — create configuration (super_admin only, first-time setup)
    PATCH /api/configuration  — update configuration (super_admin only)
    Accepts multipart/form-data to support file uploads (logo, hero_image).
    """
    if request.method == 'GET':
        config = Configuration.objects.select_related('clinic').first()
        if not config:
            return Response({'detail': 'No configuration found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ConfigurationSerializer(config, context={'request': request}).data)

    # POST / PATCH — must be authenticated super_admin
    if not request.user or not request.user.is_authenticated:
        return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

    clinic = request.user.clinic
    if not clinic:
        return Response({'error': 'No clinic associated with this account.'}, status=status.HTTP_400_BAD_REQUEST)

    config = Configuration.objects.filter(clinic=clinic).first()

    if request.method == 'POST':
        if config:
            return Response(
                {'error': 'Configuration already exists. Use PATCH to update.'},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = ConfigurationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(clinic=clinic)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # PATCH
    if not config:
        return Response({'error': 'No configuration found. Use POST to create it first.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ConfigurationSerializer(config, data=request.data, partial=True, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Service endpoints ────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_services(request):
    if request.method == "GET":
        qs = Service.objects.all()
        name     = request.query_params.get('name', '').strip()
        category = request.query_params.get('category', '').strip()
        if name:
            qs = qs.filter(name__icontains=name)
        if category:
            qs = qs.filter(category=category)
        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ServiceSerializer(page, many=True).data)
    serializer = ServiceSerializer(data=request.data)
    if serializer.is_valid():
        service = serializer.save()
        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def api_service_detail(request, pk):
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response({"error": "Service not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(ServiceSerializer(service).data)

    if request.method == "DELETE":
        service.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ServiceSerializer(service, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(ServiceSerializer(service).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# ─── Product endpoints ────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_products(request):
    if request.method == 'GET':
        qs = Product.objects.select_related('service').all()
        name       = request.query_params.get('name', '').strip()
        service_id = request.query_params.get('service_id', '').strip()
        if name:
            qs = qs.filter(name__icontains=name)
        if service_id:
            qs = qs.filter(service_id=service_id)
        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)
    serializer = ProductSerializer(data=request.data)
    if serializer.is_valid():
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_product_detail(request, pk):
    try:
        product = Product.objects.select_related('service').get(pk=pk)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ProductSerializer(product).data)

    if request.method == 'DELETE':
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ProductSerializer(product, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(ProductSerializer(product).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Machine endpoints ────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_machines(request):
    if request.method == 'GET':
        qs = Machine.objects.select_related('service').all()
        name       = request.query_params.get('name', '').strip()
        service_id = request.query_params.get('service_id', '').strip()
        if name:
            qs = qs.filter(name__icontains=name)
        if service_id:
            qs = qs.filter(service_id=service_id)
        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(MachineSerializer(page, many=True).data)
    serializer = MachineSerializer(data=request.data)
    if serializer.is_valid():
        machine = serializer.save()
        return Response(MachineSerializer(machine).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_machine_detail(request, pk):
    try:
        machine = Machine.objects.select_related('service').get(pk=pk)
    except Machine.DoesNotExist:
        return Response({'error': 'Machine not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(MachineSerializer(machine).data)

    if request.method == 'DELETE':
        machine.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = MachineSerializer(machine, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(MachineSerializer(machine).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
