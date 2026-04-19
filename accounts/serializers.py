from rest_framework import serializers
from .models import User, Clinic, Configuration, Doctor


class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ('id', 'name', 'slug')


class BranchMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class TimeSlotSerializer(serializers.Serializer):
    from_time = serializers.TimeField()
    to_time = serializers.TimeField()

    def validate(self, attrs):
        if attrs['from_time'] >= attrs['to_time']:
            raise serializers.ValidationError('from_time must be before to_time.')
        return attrs


class DayScheduleSerializer(serializers.Serializer):
    day = serializers.IntegerField(min_value=0, max_value=6)
    slots = TimeSlotSerializer(many=True)

    def validate_slots(self, value):
        if not value:
            raise serializers.ValidationError('At least one slot is required per day.')
        seen = set()
        for slot in value:
            key = (slot['from_time'], slot['to_time'])
            if key in seen:
                raise serializers.ValidationError('Duplicate slots are not allowed.')
            seen.add(key)
        sorted_slots = sorted(value, key=lambda s: s['from_time'])
        for i in range(len(sorted_slots) - 1):
            if sorted_slots[i]['to_time'] > sorted_slots[i + 1]['from_time']:
                raise serializers.ValidationError('Time slots must not overlap.')
        return value


class BranchScheduleSerializer(serializers.Serializer):
    branch_id = serializers.IntegerField()
    days = DayScheduleSerializer(many=True)


class UserSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    assigned_branches = serializers.SerializerMethodField()
    branch_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'role', 'role_display', 'phone',
            'specialty', 'clinic', 'clinic_name',
            'is_active', 'date_joined', 'assigned_branches', 'branch_count',
        )
        read_only_fields = ('clinic', 'date_joined')

    def get_assigned_branches(self, obj):
        from branches.models import DoctorSchedule
        assignments = obj.branch_assignments.select_related('branch').all()
        result = []
        for a in assignments:
            schedules = DoctorSchedule.objects.filter(user=obj, branch=a.branch).order_by('day', 'from_time')
            result.append({
                'id': a.branch.id,
                'name': a.branch.name,
                'schedule': [
                    {'day': s.day, 'from_time': str(s.from_time)[:5], 'to_time': str(s.to_time)[:5]}
                    for s in schedules
                ],
            })
        return result

    def get_branch_count(self, obj):
        return obj.branch_assignments.count()


class UserCreateSerializer(serializers.ModelSerializer):
    branch_schedules = BranchScheduleSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            'name', 'email', 'role', 'phone',
            'specialty', 'branch_schedules',
        )

    def validate_email(self, value):
        request = self.context.get('request')
        qs = User.objects.filter(clinic=request.user.clinic, email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This email is already registered.')
        return value.lower()

    def validate(self, attrs):
        role = attrs.get('role') or (self.instance.role if self.instance else None)
        if role in (User.Role.DOCTOR, User.Role.ASSISTANT):
            if not attrs.get('branch_schedules'):
                raise serializers.ValidationError(
                    {'branch_schedules': 'At least one branch with schedule is required.'}
                )
        return attrs

    def _save_schedules(self, user, branch_schedules, request):
        from branches.models import Branch, UserBranchAssignment, DoctorSchedule
        for bs in branch_schedules:
            try:
                branch = Branch.objects.get(pk=bs['branch_id'], clinic=request.user.clinic, is_active=True)
            except Branch.DoesNotExist:
                continue
            UserBranchAssignment.objects.get_or_create(
                user=user, branch=branch, defaults={'assigned_by': request.user}
            )
            DoctorSchedule.objects.filter(user=user, branch=branch).delete()
            for day_data in bs.get('days', []):
                for slot in day_data.get('slots', []):
                    DoctorSchedule.objects.create(
                        user=user, branch=branch,
                        day=day_data['day'],
                        from_time=slot['from_time'],
                        to_time=slot['to_time'],
                    )

    def create(self, validated_data):
        branch_schedules = validated_data.pop('branch_schedules', [])
        request = self.context.get('request')

        user = User(**validated_data)
        user.clinic = request.user.clinic
        user.save()
        self._save_schedules(user, branch_schedules, request)
        return user

    def update(self, instance, validated_data):
        branch_schedules = validated_data.pop('branch_schedules', None)
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if branch_schedules is not None:
            self._save_schedules(instance, branch_schedules, request)
        return instance


class UserUpdateBranchesSerializer(serializers.Serializer):
    branch_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def validate_branch_ids(self, value):
        request = self.context.get('request')
        from branches.models import Branch
        valid = Branch.objects.filter(
            id__in=value, clinic=request.user.clinic, is_active=True
        ).values_list('id', flat=True)
        invalid = set(value) - set(valid)
        if invalid:
            raise serializers.ValidationError(f'Invalid branch IDs: {list(invalid)}')
        return value


class ConfigurationSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=True, use_url=True)
    hero_image = serializers.ImageField(required=False, allow_null=True, use_url=True)
    logo_url = serializers.SerializerMethodField()
    hero_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Configuration
        fields = (
            'id', 'clinic_name',
            'logo', 'logo_url',
            'hero_image', 'hero_image_url',
            'slogan', 'sub_slogan', 'footer_info',
            'linkedin_url', 'instagram_url', 'facebook_url', 'whatsapp_url',
            'primary_color', 'secondary_color', 'updated_at',
        )

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None

    def get_hero_image_url(self, obj):
        request = self.context.get('request')
        if obj.hero_image and request:
            return request.build_absolute_uri(obj.hero_image.url)
        return None

    def validate_primary_color(self, value):
        if not value.startswith('#') or len(value) not in (4, 7):
            raise serializers.ValidationError('Must be a valid hex color (e.g. #1ABC9C).')
        return value

    def validate_secondary_color(self, value):
        if value and (not value.startswith('#') or len(value) not in (4, 7)):
            raise serializers.ValidationError('Must be a valid hex color (e.g. #FFFFFF).')
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.EmailField()   # email used as username
    password = serializers.CharField(write_only=True)


# ─── Doctor serializers ────────────────────────────────────────────────────────

class DoctorSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)
    name = serializers.CharField(source='user.name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    clinic = serializers.IntegerField(source='user.clinic_id', read_only=True)
    clinic_name = serializers.CharField(source='user.clinic.name', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    assigned_branches = serializers.SerializerMethodField()
    branch_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = (
            'id', 'name', 'email', 'phone', 'specialty',
            'clinic', 'clinic_name', 'is_active', 'date_joined',
            'assigned_branches', 'branch_count',
        )

    def get_assigned_branches(self, obj):
        from branches.models import DoctorSchedule
        assignments = obj.user.branch_assignments.select_related('branch').all()
        result = []
        for a in assignments:
            schedules = DoctorSchedule.objects.filter(
                user=obj.user, branch=a.branch
            ).order_by('day', 'from_time')
            result.append({
                'id': a.branch.id,
                'name': a.branch.name,
                'schedule': [
                    {'day': s.day, 'from_time': str(s.from_time)[:5], 'to_time': str(s.to_time)[:5]}
                    for s in schedules
                ],
            })
        return result

    def get_branch_count(self, obj):
        return obj.user.branch_assignments.count()


class DoctorCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    specialty = serializers.CharField(required=False, allow_blank=True, default='')
    branch_schedules = BranchScheduleSerializer(many=True, required=False)

    def validate_email(self, value):
        request = self.context.get('request')
        if User.objects.filter(clinic=request.user.clinic, email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value.lower()

    def _save_schedules(self, user, branch_schedules, request):
        from branches.models import Branch, UserBranchAssignment, DoctorSchedule
        for bs in branch_schedules:
            try:
                branch = Branch.objects.get(pk=bs['branch_id'], clinic=request.user.clinic, is_active=True)
            except Branch.DoesNotExist:
                continue
            UserBranchAssignment.objects.get_or_create(
                user=user, branch=branch, defaults={'assigned_by': request.user}
            )
            DoctorSchedule.objects.filter(user=user, branch=branch).delete()
            for day_data in bs.get('days', []):
                for slot in day_data.get('slots', []):
                    DoctorSchedule.objects.create(
                        user=user, branch=branch,
                        day=day_data['day'],
                        from_time=slot['from_time'],
                        to_time=slot['to_time'],
                    )

    def create(self, validated_data):
        branch_schedules = validated_data.pop('branch_schedules', [])
        request = self.context.get('request')
        user = User.objects.create(
            email=validated_data['email'],
            name=validated_data['name'],
            phone=validated_data.get('phone', ''),
            role=User.Role.DOCTOR,
            clinic=request.user.clinic,
        )
        doctor = Doctor.objects.create(
            user=user,
            specialty=validated_data.get('specialty', ''),
        )
        self._save_schedules(user, branch_schedules, request)
        return doctor

    def update(self, instance, validated_data):
        branch_schedules = validated_data.pop('branch_schedules', None)
        request = self.context.get('request')
        user = instance.user
        user.name = validated_data.get('name', user.name)
        user.phone = validated_data.get('phone', user.phone)
        if 'email' in validated_data:
            if User.objects.filter(
                clinic=request.user.clinic, email__iexact=validated_data['email']
            ).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({'email': 'This email is already registered.'})
            user.email = validated_data['email'].lower()
        user.save()
        instance.specialty = validated_data.get('specialty', instance.specialty)
        instance.save()
        if branch_schedules is not None:
            self._save_schedules(user, branch_schedules, request)
        return instance
