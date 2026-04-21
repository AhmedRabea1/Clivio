from rest_framework import serializers
from .models import Patient, Reservation


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ('id', 'first_name', 'last_name', 'mobile_number', 'date_of_birth', 'medical_notes')


class ReservationSerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.name', read_only=True, default=None)

    class Meta:
        model = Reservation
        fields = (
            'id', 'patient', 'branch_name',
            'doctor_name', 'date_of_visit', 'slot', 'status', 'created_at',
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
            if not Doctor.objects.filter(pk=attrs['doctor_id'], user__is_active=True).exists():
                raise serializers.ValidationError({'doctor_id': 'Invalid or inactive doctor.'})

        # If mobile is new, patient fields are required
        mobile_exists = Patient.objects.filter(mobile_number=attrs['mobile_number']).exists()
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

        # Get or create patient
        patient, _ = Patient.objects.get_or_create(
            mobile_number=data['mobile_number'],
            defaults={
                'first_name':    data.get('first_name', ''),
                'last_name':     data.get('last_name', ''),
                'date_of_birth': data.get('date_of_birth'),
                'medical_notes': data.get('medical_notes', ''),
            },
        )

        branch = Branch.objects.get(pk=data['branch_id'])
        doctor = Doctor.objects.filter(pk=data.get('doctor_id')).first() if data.get('doctor_id') else None

        reservation = Reservation.objects.create(
            patient=patient,
            branch=branch,
            doctor=doctor,
            date_of_visit=data['date_of_visit'],
            slot=data.get('slot'),
        )

        return reservation
