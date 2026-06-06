from rest_framework import serializers
from .models import (
    Patient, Reservation, ReservationAttachment,
    DermaFaceMappingLine, DermaFaceMappingZoneService, DermaFaceMappingZone, DermaFaceMapping,
    DermaBodyMappingLine, DermaBodyMappingZoneService, DermaBodyMappingZone, DermaBodyMapping,
    PatientPulsePackage, PatientAreaPackage,
)


class ReservationAttachmentSerializer(serializers.ModelSerializer):
    file_url         = serializers.SerializerMethodField()
    file_name        = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.name', read_only=True, default=None)

    class Meta:
        model  = ReservationAttachment
        fields = ('id', 'file', 'file_url', 'file_name', 'uploaded_by_name', 'created_at')
        extra_kwargs = {'file': {'write_only': True}}

    def get_file_url(self, obj):
        if obj.url:
            return obj.url
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None

    def get_file_name(self, obj):
        if obj.name:
            return obj.name
        if obj.file:
            return obj.file.name.split('/')[-1]
        return None


class PatientFamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ('id', 'first_name', 'last_name', 'date_of_birth', 'medical_notes')


class PatientSerializer(serializers.ModelSerializer):
    family_members = PatientFamilyMemberSerializer(many=True, read_only=True)
    packages       = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = (
            'id', 'first_name', 'last_name', 'mobile_number', 'date_of_birth',
            'medical_notes', 'is_primary', 'primary_patient_id', 'family_members', 'packages',
        )

    def get_packages(self, obj):
        result = []
        for r in obj.pulse_package_records.select_related('package').all():
            result.append({
                'type': 1,
                'record_id': r.id,
                'package_id': r.package.id,
                'pulses': r.package.pulses,
                'total_pulses': r.total_pulses,
                'remaining_pulses': r.remaining_pulses,
                'price': str(r.package.price),
                'description': r.package.description,
            })
        for r in obj.area_package_records.select_related('package').all():
            result.append({
                'type': 2,
                'record_id': r.id,
                'package_id': r.package.id,
                'name': r.package.name,
                'is_used': r.is_used,
                'price': str(r.package.price),
                'description': r.package.description,
            })
        return result


class ReservationSerializer(serializers.ModelSerializer):
    patient_name   = serializers.SerializerMethodField()
    patient_mobile = serializers.CharField(source='patient.mobile_number', read_only=True)
    branch_name    = serializers.CharField(source='branch.name', read_only=True)
    doctor_name    = serializers.CharField(source='doctor.user.name', read_only=True, default=None)

    class Meta:
        model = Reservation
        fields = (
            'id', 'patient_id', 'patient_name', 'patient_mobile', 'branch_name',
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
    # Patient fields — required only when patient is new
    mobile_number = serializers.CharField(max_length=20)
    is_for_self   = serializers.BooleanField(default=True)
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

        if not Branch.objects.filter(pk=attrs['branch_id'], is_active=True).exists():
            raise serializers.ValidationError({'branch_id': 'Invalid or inactive branch.'})

        if attrs.get('doctor_id'):
            if not Doctor.objects.filter(user__pk=attrs['doctor_id'], user__is_active=True).exists():
                raise serializers.ValidationError({'doctor_id': 'Invalid or inactive doctor.'})

        mobile = attrs['mobile_number']
        is_for_self = attrs.get('is_for_self', True)

        if is_for_self:
            patient_exists = Patient.objects.filter(mobile_number=mobile, is_primary=True).exists()
        else:
            first_name = attrs.get('first_name', '').strip()
            last_name  = attrs.get('last_name', '').strip()
            patient_exists = Patient.objects.filter(
                mobile_number=mobile, is_primary=False,
                first_name__iexact=first_name, last_name__iexact=last_name,
            ).exists()

        if not patient_exists:
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
        mobile      = data['mobile_number']
        is_for_self = data.get('is_for_self', True)

        if is_for_self:
            patient, created = Patient.objects.get_or_create(
                mobile_number=mobile,
                is_primary=True,
                defaults={
                    'first_name':    data.get('first_name', ''),
                    'last_name':     data.get('last_name', ''),
                    'date_of_birth': data.get('date_of_birth'),
                    'medical_notes': data.get('medical_notes', ''),
                },
            )
            if created:
                Patient.objects.filter(
                    mobile_number=mobile, is_primary=False, primary_patient__isnull=True
                ).update(primary_patient=patient)
        else:
            first_name = data.get('first_name', '').strip()
            last_name  = data.get('last_name', '').strip()
            primary    = Patient.objects.filter(mobile_number=mobile, is_primary=True).first()
            patient = Patient.objects.filter(
                mobile_number=mobile, is_primary=False,
                first_name__iexact=first_name, last_name__iexact=last_name,
            ).first()
            if not patient:
                patient = Patient.objects.create(
                    mobile_number=mobile,
                    is_primary=False,
                    primary_patient=primary,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=data.get('date_of_birth'),
                    medical_notes=data.get('medical_notes', ''),
                )

        branch = Branch.objects.get(pk=data['branch_id'])
        doctor = Doctor.objects.filter(user__pk=data.get('doctor_id')).first() if data.get('doctor_id') else None

        return Reservation.objects.create(
            patient=patient,
            branch=branch,
            doctor=doctor,
            date_of_visit=data['date_of_visit'],
            slot=data.get('slot'),
        )


class DermaFaceMappingLineSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    machine_name = serializers.SerializerMethodField()

    class Meta:
        model  = DermaFaceMappingLine
        fields = (
            'id', 'line_type',
            'product_id', 'product_name', 'product_type', 'quantity', 'volume_ml',
            'machine_id', 'machine_name', 'machine_type', 'minutes', 'pulses',
        )

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None

    def get_machine_name(self, obj):
        return obj.machine.name if obj.machine_id else None


class DermaFaceMappingZoneServiceSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    lines   = DermaFaceMappingLineSerializer(many=True, read_only=True)

    class Meta:
        model  = DermaFaceMappingZoneService
        fields = ('id', 'service', 'lines')

    def get_service(self, obj):
        if not obj.service:
            return None
        return {
            'id':               obj.service.id,
            'name':             obj.service.name,
            'category':         obj.service.category,
            'category_display': obj.service.get_category_display(),
        }


class DermaFaceMappingZoneSerializer(serializers.ModelSerializer):
    services = DermaFaceMappingZoneServiceSerializer(many=True, read_only=True, source='zone_services')

    class Meta:
        model  = DermaFaceMappingZone
        fields = ('id', 'zone_id', 'zone_label', 'services')


class DermaFaceMappingSerializer(serializers.ModelSerializer):
    zones = DermaFaceMappingZoneSerializer(many=True, read_only=True)

    class Meta:
        model  = DermaFaceMapping
        fields = ('id', 'reservation_id', 'patient_id', 'mapping_type', 'created_at', 'zones')


# ─── Body Mapping Serializers ─────────────────────────────────────────────────

class DermaBodyMappingLineSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    machine_name = serializers.SerializerMethodField()

    class Meta:
        model  = DermaBodyMappingLine
        fields = (
            'id', 'line_type',
            'product_id', 'product_name', 'product_type', 'quantity', 'volume_ml',
            'machine_id', 'machine_name', 'machine_type', 'minutes', 'pulses',
        )

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None

    def get_machine_name(self, obj):
        return obj.machine.name if obj.machine_id else None


class DermaBodyMappingZoneServiceSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    lines   = DermaBodyMappingLineSerializer(many=True, read_only=True)

    class Meta:
        model  = DermaBodyMappingZoneService
        fields = ('id', 'service', 'lines')

    def get_service(self, obj):
        if not obj.service:
            return None
        return {
            'id':               obj.service.id,
            'name':             obj.service.name,
            'category':         obj.service.category,
            'category_display': obj.service.get_category_display(),
        }


class DermaBodyMappingZoneSerializer(serializers.ModelSerializer):
    services = DermaBodyMappingZoneServiceSerializer(many=True, read_only=True, source='zone_services')

    class Meta:
        model  = DermaBodyMappingZone
        fields = ('id', 'zone_id', 'zone_label', 'services')


class DermaBodyMappingSerializer(serializers.ModelSerializer):
    zones = DermaBodyMappingZoneSerializer(many=True, read_only=True)

    class Meta:
        model  = DermaBodyMapping
        fields = ('id', 'reservation_id', 'patient_id', 'mapping_type', 'created_at', 'zones')
