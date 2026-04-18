from rest_framework import serializers
from .models import Branch, UserBranchAssignment


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ('id', 'name', 'address', 'phone', 'from_time', 'to_time', 'vacation_days', 'is_active')
        read_only_fields = ('id',)

    def validate_vacation_days(self, value):
        valid = {0, 1, 2, 3, 4, 5, 6}
        invalid = [d for d in value if d not in valid]
        if invalid:
            raise serializers.ValidationError(f'Invalid day indexes: {invalid}. Use 0 (Sat) to 6 (Fri).')
        return list(set(value))  # remove duplicates

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
