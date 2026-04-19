from rest_framework import serializers
from accounts.models import User
from .models import Branch, UserBranchAssignment


class PublicBranchSerializer(serializers.ModelSerializer):
    total_doctors = serializers.SerializerMethodField()
    working_hours = serializers.SerializerMethodField()
    vacation_days_labels = serializers.SerializerMethodField()

    DAY_LABELS = {0: 'Saturday', 1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday', 5: 'Thursday', 6: 'Friday'}

    class Meta:
        model = Branch
        fields = ('id', 'name', 'address', 'phone', 'working_hours', 'vacation_days', 'vacation_days_labels', 'is_active', 'total_doctors')

    def get_total_doctors(self, obj):
        return obj.user_assignments.filter(user__role=User.Role.DOCTOR, user__is_active=True).count()

    def get_working_hours(self, obj):
        if obj.from_time and obj.to_time:
            return {'from': obj.from_time.strftime('%H:%M'), 'to': obj.to_time.strftime('%H:%M')}
        return None

    def get_vacation_days_labels(self, obj):
        return [self.DAY_LABELS[d] for d in obj.vacation_days if d in self.DAY_LABELS]


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
    is_active = serializers.BooleanField(source='user.is_active')
    assigned_at = serializers.DateTimeField()
    schedule = serializers.SerializerMethodField()

    def get_role_display(self, obj):
        return obj.user.get_role_display()

    def get_schedule(self, obj):
        from .models import DoctorSchedule
        schedules = DoctorSchedule.objects.filter(
            user=obj.user, branch=obj.branch
        ).order_by('day', 'from_time')
        return [
            {'day': s.day, 'from_time': str(s.from_time)[:5], 'to_time': str(s.to_time)[:5]}
            for s in schedules
        ]
