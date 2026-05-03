from rest_framework import serializers
from .models import Patient, Reservation


class PatientFamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ('id', 'first_name', 'last_name', 'date_of_birth', 'medical_notes')


class PatientSerializer(serializers.ModelSerializer):
    family_members = PatientFamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = (
            'id', 'first_name', 'last_name', 'mobile_number', 'date_of_birth',
            'medical_notes', 'is_primary', 'primary_patient_id', 'family_members',
        )


class ReservationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    branch_name  = serializers.CharField(source='branch.name', read_only=True)
    doctor_name  = serializers.CharField(source='doctor.user.name', read_only=True, default=None)

    class Meta:
        model = Reservation
        fields = (
            'id', 'patient_name', 'branch_name',
            'doctor_name', 'date_of_visit', 'slot', 'status', 'created_at',
        )

    def get_patient_name(self, obj):
        return obj.patient.full_name if obj.patient else None


class ReservationUpdateSerializer(serializers.Serializer):
    branch_id     = serializers.IntegerField(required=False)
    doctor_id     = serializers.IntegerField(required=False, allow_null=True)
    date_of_visit = serializers.DateField(required=False)
    slot          = serializers.TimeField(required=False, allow_null=True)
    status        = serializers.ChoiceField(choices=Reservation.Status.choices, required=False)

    def validate_branch_id(self, value):
        from branches.models import Branch
        if not Branch.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive branch.')
        return value

    def validate_doctor_id(self, value):
        if value is None:
            return value
        from accounts.models import Doctor
        if not Doctor.objects.filter(user__pk=value, user__is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive doctor.')
        return value

    def save(self, instance):
        from branches.models import Branch
        from accounts.models import Doctor
        data = self.validated_data
        if 'branch_id' in data:
            instance.branch = Branch.objects.get(pk=data['branch_id'])
        if 'doctor_id' in data:
            instance.doctor = Doctor.objects.filter(user__pk=data['doctor_id']).first() if data['doctor_id'] else None
        if 'date_of_visit' in data:
            instance.date_of_visit = data['date_of_visit']
        if 'slot' in data:
            instance.slot = data['slot']
        if 'status' in data:
            instance.status = data['status']
        instance.save()
        return instance


class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ('first_name', 'last_name', 'mobile_number', 'date_of_birth', 'medical_notes')
        extra_kwargs = {
            'medical_notes': {'required': False, 'allow_blank': True},
        }


class ReservationCreateSerializer(serializers.Serializer):
    patient_id    = serializers.IntegerField()
    branch_id     = serializers.IntegerField()
    doctor_id     = serializers.IntegerField(required=False, allow_null=True, default=None)
    date_of_visit = serializers.DateField()
    slot          = serializers.TimeField(required=False, allow_null=True, default=None)

    def validate_patient_id(self, value):
        if not Patient.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Patient not found.')
        return value

    def validate_branch_id(self, value):
        from branches.models import Branch
        if not Branch.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive branch.')
        return value

    def validate_doctor_id(self, value):
        if value is None:
            return value
        from accounts.models import Doctor
        if not Doctor.objects.filter(user__pk=value, user__is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive doctor.')
        return value

    def save(self):
        from branches.models import Branch
        from accounts.models import Doctor
        data = self.validated_data
        return Reservation.objects.create(
            patient_id=data['patient_id'],
            branch=Branch.objects.get(pk=data['branch_id']),
            doctor=Doctor.objects.filter(user__pk=data.get('doctor_id')).first() if data.get('doctor_id') else None,
            date_of_visit=data['date_of_visit'],
            slot=data.get('slot'),
        )


class PublicReservationCreateSerializer(serializers.Serializer):
    # Patient fields — required only when mobile is new
    mobile_number = serializers.CharField(max_length=20)
    first_name    = serializers.CharField(required=False)
    last_name     = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(required=False)
    medical_notes = serializers.CharField(required=False, allow_blank=True, default='')

    # Reservation fields
    branch_id     = serializers.IntegerField()
    doctor_id     = serializers.IntegerField(required=False, allow_null=True, default=None)
    date_of_visit = serializers.DateField()
    slot          = serializers.TimeField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        from branches.models import Branch
        from accounts.models import Doctor

        # Validate branch exists
        if not Branch.objects.filter(pk=attrs['branch_id'], is_active=True).exists():
            raise serializers.ValidationError({'branch_id': 'Invalid or inactive branch.'})

        # Validate doctor if provided
        if attrs.get('doctor_id'):
            if not Doctor.objects.filter(user__pk=attrs['doctor_id'], user__is_active=True).exists():
                raise serializers.ValidationError({'doctor_id': 'Invalid or inactive doctor.'})

        # If mobile is new (no primary patient), patient fields are required
        mobile_exists = Patient.objects.filter(mobile_number=attrs['mobile_number'], is_primary=True).exists()
        if not mobile_exists:
            for field in ('first_name', 'last_name', 'date_of_birth'):
                if not attrs.get(field):
                    raise serializers.ValidationError(
                        {field: 'This field is required for new patients.'}
                    )

        return attrs

    def save(self):
        from branches.models import Branch
        from accounts.models import Doctor

        data = self.validated_data

        # Get or create primary patient
        patient, _ = Patient.objects.get_or_create(
            mobile_number=data['mobile_number'],
            is_primary=True,
            defaults={
                'first_name':    data.get('first_name', ''),
                'last_name':     data.get('last_name', ''),
                'date_of_birth': data.get('date_of_birth'),
                'medical_notes': data.get('medical_notes', ''),
            },
        )

        branch = Branch.objects.get(pk=data['branch_id'])
        doctor = Doctor.objects.filter(user__pk=data.get('doctor_id')).first() if data.get('doctor_id') else None

        reservation = Reservation.objects.create(
            patient=patient,
            branch=branch,
            doctor=doctor,
            date_of_visit=data['date_of_visit'],
            slot=data.get('slot'),
        )

        return reservation
