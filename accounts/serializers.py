from rest_framework import serializers
from .models import User, Clinic, Configuration


class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ('id', 'name', 'slug')


class BranchMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    city = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    assigned_branches = serializers.SerializerMethodField()
    branch_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'role', 'role_display', 'phone',
            'specialty', 'role_title', 'clinic', 'clinic_name',
            'is_active', 'date_joined', 'assigned_branches', 'branch_count',
        )
        read_only_fields = ('clinic', 'date_joined')

    def get_assigned_branches(self, obj):
        assignments = obj.branch_assignments.select_related('branch').all()
        return [
            {'id': a.branch.id, 'name': a.branch.name, 'city': a.branch.city}
            for a in assignments
        ]

    def get_branch_count(self, obj):
        return obj.branch_assignments.count()


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    branch_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = (
            'name', 'email', 'role', 'phone',
            'specialty', 'role_title', 'password', 'branch_ids',
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
        role = attrs.get('role')
        branch_ids = attrs.get('branch_ids', [])
        if role in (User.Role.DOCTOR, User.Role.ASSISTANT) and not branch_ids:
            raise serializers.ValidationError(
                {'branch_ids': 'At least one branch must be assigned.'}
            )
        return attrs

    def create(self, validated_data):
        from branches.models import Branch, UserBranchAssignment
        branch_ids = validated_data.pop('branch_ids', [])
        password = validated_data.pop('password')
        request = self.context.get('request')

        user = User(**validated_data)
        user.clinic = request.user.clinic
        user.set_password(password)
        user.save()

        if branch_ids:
            branches = Branch.objects.filter(
                id__in=branch_ids, clinic=request.user.clinic, is_active=True
            )
            for branch in branches:
                UserBranchAssignment.objects.get_or_create(
                    user=user, branch=branch,
                    defaults={'assigned_by': request.user}
                )
        return user


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
