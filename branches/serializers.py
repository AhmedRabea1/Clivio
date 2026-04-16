from rest_framework import serializers
from .models import Branch, UserBranchAssignment


class BranchSerializer(serializers.ModelSerializer):
    doctor_count = serializers.SerializerMethodField()
    assistant_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = (
            'id', 'clinic', 'name', 'city', 'area', 'address', 'phone', 'email',
            'opening_time', 'closing_time', 'is_active', 'status',
            'created_at', 'doctor_count', 'assistant_count',
        )
        read_only_fields = ('clinic', 'created_at')

    def get_doctor_count(self, obj):
        return obj.user_assignments.filter(user__role='doctor', user__is_active=True).count()

    def get_assistant_count(self, obj):
        return obj.user_assignments.filter(user__role='assistant', user__is_active=True).count()

    def get_status(self, obj):
        return 'active' if obj.is_active else 'inactive'

    def validate_name(self, value):
        request = self.context.get('request')
        qs = Branch.objects.filter(clinic=request.user.clinic, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A branch with this name already exists.')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['clinic'] = request.user.clinic
        return super().create(validated_data)


class BranchUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='user.id')
    name = serializers.CharField(source='user.name')
    email = serializers.EmailField(source='user.email')
    role = serializers.CharField(source='user.role')
    role_display = serializers.SerializerMethodField()
    phone = serializers.CharField(source='user.phone')
    specialty = serializers.CharField(source='user.specialty')
    role_title = serializers.CharField(source='user.role_title')
    is_active = serializers.BooleanField(source='user.is_active')
    assigned_at = serializers.DateTimeField()

    def get_role_display(self, obj):
        return obj.user.get_role_display()
