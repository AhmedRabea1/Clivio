from datetime import datetime, timedelta

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django.db import transaction

from .models import (
    Reservation, Patient, ReservationAttachment, Invoice,
    DermaFaceMapping, DermaFaceMappingZone, DermaFaceMappingZoneService, DermaFaceMappingLine,
    DermaBodyMapping, DermaBodyMappingZone, DermaBodyMappingZoneService, DermaBodyMappingLine,
    ZoneDefinition, BodyZoneDefinition,
)
from .serializers import (
    PublicReservationCreateSerializer, ReservationSerializer, ReservationUpdateSerializer,
    PatientSerializer, PatientCreateSerializer, ReservationCreateSerializer,
    ReservationAttachmentSerializer, DermaFaceMappingSerializer, DermaBodyMappingSerializer,
)


# ─── Patient helpers ──────────────────────────────────────────────────────────

def _set_patient_packages(patient, packages_data):
    from accounts.models import PulsePackage, AreaPackage
    pulse_ids = [p['package_id'] for p in packages_data if p.get('type') == 1]
    area_ids  = [p['package_id'] for p in packages_data if p.get('type') == 2]
    patient.pulse_packages.set(PulsePackage.objects.filter(pk__in=pulse_ids))
    patient.area_packages.set(AreaPackage.objects.filter(pk__in=area_ids))


# ─── Patient endpoints ─────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_patients(request):
    """
    GET  /api/patients?search=name_or_mobile  — list patients
    POST /api/patients                         — create patient
    """
    if request.method == 'GET':
        qs = Patient.objects.all().order_by('-created_at')
        search    = request.query_params.get('search', '').strip()
        doctor_id = request.query_params.get('doctor_id', '').strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(mobile_number__icontains=search)
            )
        if doctor_id:
            qs = qs.filter(reservations__doctor__user__pk=doctor_id).distinct()
        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(PatientSerializer(page, many=True).data)

    mobile = request.data.get('mobile_number', '').strip()
    is_for_self = str(request.data.get('is_for_self', True)).lower() not in ('false', '0', 'no')

    if is_for_self:
        existing = Patient.objects.filter(mobile_number=mobile, is_primary=True).first()
        if existing:
            return Response(PatientSerializer(existing).data, status=status.HTTP_200_OK)
        serializer = PatientCreateSerializer(data=request.data)
        if serializer.is_valid():
            patient = serializer.save(is_primary=True, created_by=request.user)
            Patient.objects.filter(
                mobile_number=mobile, is_primary=False, primary_patient__isnull=True
            ).update(primary_patient=patient)
            if 'packages' in request.data:
                _set_patient_packages(patient, request.data['packages'])
            return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Family member
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()
    existing = Patient.objects.filter(
        mobile_number=mobile, is_primary=False,
        first_name__iexact=first_name, last_name__iexact=last_name,
    ).first()
    if existing:
        return Response(PatientSerializer(existing).data, status=status.HTTP_200_OK)
    primary = Patient.objects.filter(mobile_number=mobile, is_primary=True).first()
    serializer = PatientCreateSerializer(data=request.data)
    if serializer.is_valid():
        patient = serializer.save(is_primary=False, primary_patient=primary, created_by=request.user)
        if 'packages' in request.data:
            _set_patient_packages(patient, request.data['packages'])
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_patient_detail(request, pk):
    """
    GET    /api/patients/:id
    PATCH  /api/patients/:id
    DELETE /api/patients/:id
    """
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(PatientSerializer(patient).data)

    if request.method == 'DELETE':
        patient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = PatientCreateSerializer(patient, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        if 'packages' in request.data:
            _set_patient_packages(patient, request.data['packages'])
        return Response(PatientSerializer(patient).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Reservation endpoints ────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_reservations(request):
    """
    GET  /api/reservations  — list all reservations
    POST /api/reservations  — create reservation by patient id
    """
    if request.method == 'GET':
        qs = Reservation.objects.select_related(
            'patient', 'branch', 'doctor__user'
        ).order_by('-created_at')

        search        = request.query_params.get('search', '').strip()
        branch_name   = request.query_params.get('branch_name', '').strip()
        doctor_name   = request.query_params.get('doctor_name', '').strip()
        doctor_id     = request.query_params.get('doctor_id', '').strip()
        date_of_visit = request.query_params.get('date_of_visit', '').strip()
        res_status    = request.query_params.get('status', '').strip()

        if search:
            qs = qs.filter(
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search)  |
                Q(patient__mobile_number__icontains=search)
            )
        if branch_name:
            qs = qs.filter(branch__name__icontains=branch_name)
        if doctor_name:
            qs = qs.filter(doctor__user__name__icontains=doctor_name)
        if doctor_id:
            qs = qs.filter(doctor__user__pk=doctor_id)
        patient_id = request.query_params.get('patient_id', '').strip()
        if patient_id:
            qs = qs.filter(patient__pk=patient_id)
        if date_of_visit:
            qs = qs.filter(date_of_visit=date_of_visit)
        if res_status:
            qs = qs.filter(status=res_status)

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ReservationSerializer(page, many=True).data)

    serializer = ReservationCreateSerializer(data=request.data)
    if serializer.is_valid():
        reservation = serializer.save()
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_reservation_detail(request, pk):
    """
    GET   /api/reservations/:id — get reservation by id
    PATCH /api/reservations/:id — update reservation fields or status
    """
    try:
        reservation = Reservation.objects.select_related('patient', 'branch', 'doctor__user').get(pk=pk)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ReservationSerializer(reservation).data)

    serializer = ReservationUpdateSerializer(data=request.data)
    if serializer.is_valid():
        reservation = serializer.save(reservation)
        return Response(ReservationSerializer(reservation).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Slot generation helper ───────────────────────────────────────────────────

PYTHON_TO_MODEL_DAY = {5: 0, 6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6}


def _get_slots_for_doctor(doctor_id, branch_id, visit_date, interval):
    """Returns list of {time, available} dicts for a doctor on a given date."""
    from branches.models import DoctorSchedule

    model_day = PYTHON_TO_MODEL_DAY[visit_date.weekday()]
    schedules = DoctorSchedule.objects.filter(
        user__pk=doctor_id, branch_id=branch_id, day=model_day,
    )
    if not schedules.exists():
        return []

    all_slots = set()
    for schedule in schedules:
        current = datetime.combine(visit_date, schedule.from_time)
        end     = datetime.combine(visit_date, schedule.to_time)
        while current < end:
            all_slots.add(current.time())
            current += timedelta(minutes=interval)

    booked = set(
        Reservation.objects.filter(
            doctor__user__pk=doctor_id,
            branch_id=branch_id,
            date_of_visit=visit_date,
            slot__isnull=False,
        ).values_list('slot', flat=True)
    )

    return [
        {'time': t.strftime('%H:%M'), 'available': t not in booked}
        for t in sorted(all_slots)
    ]


# ─── Public slots endpoint ─────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def api_public_slots(request):
    """
    GET /api/public/slots?doctor_id=1&branch_id=1&date=2026-04-25
    Returns all slots for the doctor on that day, with availability.
    """
    doctor_id  = request.query_params.get('doctor_id')
    branch_id  = request.query_params.get('branch_id')
    date_str   = request.query_params.get('date')

    if not all([doctor_id, branch_id, date_str]):
        return Response(
            {'error': 'doctor_id, branch_id and date are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        visit_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

    from branches.models import DoctorSchedule
    from accounts.models import Doctor, Configuration

    # day index: Monday=0 in Python but our model uses 0=Saturday
    # Python weekday(): Mon=0..Sun=6 → map to our scheme: Sat=0,Sun=1,Mon=2,Tue=3,Wed=4,Thu=5,Fri=6
    PYTHON_TO_MODEL_DAY = {5: 0, 6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6}
    model_day = PYTHON_TO_MODEL_DAY[visit_date.weekday()]

    # Get doctor's schedule for this branch + day
    schedules = DoctorSchedule.objects.filter(
        user__pk=doctor_id,
        branch_id=branch_id,
        day=model_day,
    )

    if not schedules.exists():
        return Response({
            'date': date_str,
            'slot_interval': None,
            'slots': [],
            'message': 'Doctor has no schedule on this day.',
        })

    # Get slot interval from configuration
    config = Configuration.objects.first()
    interval = config.slot_interval if config else 30

    # Generate all possible slots from all schedule entries for this day
    all_slots = set()
    for schedule in schedules:
        current = datetime.combine(visit_date, schedule.from_time)
        end     = datetime.combine(visit_date, schedule.to_time)
        while current < end:
            all_slots.add(current.time())
            current += timedelta(minutes=interval)

    # Get already booked slots
    booked = set(
        Reservation.objects.filter(
            doctor__user__pk=doctor_id,
            branch_id=branch_id,
            date_of_visit=visit_date,
            slot__isnull=False,
        ).values_list('slot', flat=True)
    )

    slots = [
        {
            'time': t.strftime('%H:%M'),
            'available': t not in booked,
        }
        for t in sorted(all_slots)
    ]

    return Response({
        'date': date_str,
        'slot_interval': interval,
        'slots': slots,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def api_public_book_reservation(request):
    """
    POST /api/public/reservations
    Creates a reservation. Creates patient if mobile_number is new, otherwise reuses existing patient.
    """
    serializer = PublicReservationCreateSerializer(data=request.data)
    if serializer.is_valid():
        reservation = serializer.save()
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_public_availability(request):
    """
    GET /api/public/availability
        ?date=2026-04-25          → all branches with their doctors and slots
        ?date=&branch_id=1        → doctors in that branch with slots
        ?date=&branch_id=1&doctor_id=8 → slots for that doctor on that branch
    date defaults to today.
    """
    from datetime import date as date_cls
    from branches.models import Branch, UserBranchAssignment
    from accounts.models import Doctor, Configuration

    date_str  = request.query_params.get('date', '').strip()
    branch_id = request.query_params.get('branch_id', '').strip()
    doctor_id = request.query_params.get('doctor_id', '').strip()

    if date_str:
        try:
            visit_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        visit_date = date_cls.today()

    config   = Configuration.objects.first()
    interval = config.slot_interval if config else 30
    date_out = visit_date.strftime('%Y-%m-%d')

    # ── Case 3: date + branch + doctor → just slots ───────────────────────────
    if branch_id and doctor_id:
        slots = _get_slots_for_doctor(doctor_id, branch_id, visit_date, interval)
        return Response({
            'date':         date_out,
            'slot_interval': interval,
            'slots':        slots,
        })

    # ── Case 2: date + branch → doctors with slots ────────────────────────────
    if branch_id:
        try:
            branch = Branch.objects.get(pk=branch_id, is_active=True)
        except Branch.DoesNotExist:
            return Response({'error': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

        doctor_ids = UserBranchAssignment.objects.filter(
            branch=branch, user__is_active=True, user__role='doctor'
        ).values_list('user_id', flat=True)

        doctors_data = []
        for doc in Doctor.objects.filter(user_id__in=doctor_ids).select_related('user'):
            slots = _get_slots_for_doctor(doc.user.pk, branch_id, visit_date, interval)
            if slots:
                doctors_data.append({
                    'id':       doc.user.pk,
                    'name':     doc.user.name,
                    'specialty': doc.specialty,
                    'slots':    slots,
                })

        return Response({
            'date':   date_out,
            'branch': {'id': branch.pk, 'name': branch.name},
            'doctors': doctors_data,
        })

    # ── Case 1: date only → all branches with doctors and slots ──────────────
    branches_data = []
    for branch in Branch.objects.filter(is_active=True):
        doctor_ids = UserBranchAssignment.objects.filter(
            branch=branch, user__is_active=True, user__role='doctor'
        ).values_list('user_id', flat=True)

        doctors_data = []
        for doc in Doctor.objects.filter(user_id__in=doctor_ids).select_related('user'):
            slots = _get_slots_for_doctor(doc.user.pk, branch.pk, visit_date, interval)
            if slots:
                doctors_data.append({
                    'id':        doc.user.pk,
                    'name':      doc.user.name,
                    'specialty': doc.specialty,
                    'slots':     slots,
                })

        branches_data.append({
            'id':      branch.pk,
            'name':    branch.name,
            'doctors': doctors_data,
        })

    return Response({
        'date':     date_out,
        'branches': branches_data,
    })


# ─── Reservation Attachments ──────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_reservation_attachments(request, pk):
    try:
        reservation = Reservation.objects.get(pk=pk)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        attachments = reservation.attachments.all()
        return Response(ReservationAttachmentSerializer(attachments, many=True, context={'request': request}).data)

    if 'file' not in request.FILES:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    if request.FILES['file'].size > 10 * 1024 * 1024:
        return Response({'error': 'File size must not exceed 10 MB.'}, status=status.HTTP_400_BAD_REQUEST)

    attachment = ReservationAttachment.objects.create(
        reservation=reservation,
        file=request.FILES['file'],
        uploaded_by=request.user,
    )
    return Response(
        ReservationAttachmentSerializer(attachment, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_reservation_attachment_detail(request, pk):
    try:
        attachment = ReservationAttachment.objects.get(pk=pk)
    except ReservationAttachment.DoesNotExist:
        return Response({'error': 'Attachment not found.'}, status=status.HTTP_404_NOT_FOUND)

    attachment.file.delete(save=False)
    attachment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Prescription PDF ─────────────────────────────────────────────────────────

def _generate_invoice_pdf(doctor_name, patient_name, items, subtotal, discount, total, clinic_name, logo_url):
    from io import BytesIO
    from datetime import date
    from decimal import Decimal
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    PRIMARY = HexColor('#2563EB')
    GRAY    = HexColor('#6B7280')
    LIGHT   = HexColor('#F3F4F6')
    BORDER  = HexColor('#E5E7EB')
    GREEN   = HexColor('#16A34A')

    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=2.5*cm, leftMargin=2.5*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    # ── Logo ──────────────────────────────────────────────────────────────────
    if logo_url:
        try:
            import urllib.request
            from reportlab.platypus import Image as RLImage
            img_bytes = BytesIO(urllib.request.urlopen(logo_url, timeout=5).read())
            logo = RLImage(img_bytes, width=5*cm, height=2.5*cm, kind='proportional')
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 0.3*cm))
        except Exception:
            pass

    # ── Header ─────────────────────────────────────────────────────────────────
    if clinic_name:
        story.append(Paragraph(clinic_name, ParagraphStyle(
            'Clinic', fontSize=15, textColor=GRAY, fontName='Helvetica-Bold',
            alignment=TA_CENTER, spaceAfter=4,
        )))
    story.append(Paragraph('Invoice', ParagraphStyle(
        'Title', fontSize=20, textColor=PRIMARY, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=6,
    )))
    story.append(HRFlowable(width='100%', thickness=2, color=PRIMARY, spaceAfter=12))

    # ── Info ───────────────────────────────────────────────────────────────────
    today = date.today().strftime('%d %B %Y')
    L = ParagraphStyle('L', parent=styles['Normal'], fontSize=11, alignment=TA_LEFT)
    R = ParagraphStyle('R', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT)
    info = Table([
        [Paragraph(f'<b>Doctor:</b>  {doctor_name}', L),  Paragraph(f'<b>Date:</b>  {today}', R)],
        [Paragraph(f'<b>Patient:</b>  {patient_name}', L), Paragraph('', R)],
    ], colWidths=[9*cm, 8.5*cm])
    info.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), LIGHT),
        ('BOX',           (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID',     (0,0), (-1,-1), 0.25, BORDER),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('RIGHTPADDING',  (0,0), (-1,-1), 10),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(info)
    story.append(Spacer(1, 0.6*cm))

    # ── Services table ─────────────────────────────────────────────────────────
    story.append(Paragraph('Services', ParagraphStyle(
        'Sec', fontSize=14, textColor=PRIMARY, fontName='Helvetica-Bold', spaceAfter=8,
    )))

    HDR = ParagraphStyle('HDR', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=HexColor('#FFFFFF'))
    CEL = ParagraphStyle('CEL', parent=styles['Normal'], fontSize=10)
    RCEL = ParagraphStyle('RCEL', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)

    rows = [[
        Paragraph('Service / Item', HDR),
        Paragraph('Detail',         HDR),
        Paragraph('Unit Price',     HDR),
        Paragraph('Total',          HDR),
    ]]
    for item in items:
        rows.append([
            Paragraph(item.get('name', ''), CEL),
            Paragraph(item.get('detail', ''), CEL),
            Paragraph(item.get('unit_price', ''), RCEL),
            Paragraph(item.get('total', ''), RCEL),
        ])

    tbl = Table(rows, colWidths=[7*cm, 3.5*cm, 3*cm, 3*cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  PRIMARY),
        ('BACKGROUND',    (0,1), (-1,-1), HexColor('#FFFFFF')),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [HexColor('#FFFFFF'), LIGHT]),
        ('BOX',           (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID',     (0,0), (-1,-1), 0.25, BORDER),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Totals ─────────────────────────────────────────────────────────────────
    totals_data = [[Paragraph('<b>Subtotal</b>', L), Paragraph(f'{subtotal}', RCEL)]]
    if discount:
        totals_data.append([Paragraph('<b>Discount</b>', ParagraphStyle('D', parent=styles['Normal'], fontSize=11, textColor=GREEN)), Paragraph(f'- {discount}', ParagraphStyle('DR', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT, textColor=GREEN))])
    totals_data.append([Paragraph('<b>Total</b>', ParagraphStyle('T', parent=styles['Normal'], fontSize=13, fontName='Helvetica-Bold', textColor=PRIMARY)), Paragraph(f'<b>{total}</b>', ParagraphStyle('TR', parent=styles['Normal'], fontSize=13, fontName='Helvetica-Bold', alignment=TA_RIGHT, textColor=PRIMARY))])

    totals_tbl = Table(totals_data, colWidths=[13*cm, 3.5*cm])
    totals_tbl.setStyle(TableStyle([
        ('ALIGN',         (1,0), (1,-1), 'RIGHT'),
        ('LINEABOVE',     (0,-1), (-1,-1), 1, PRIMARY),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(totals_tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _generate_prescription_pdf(doctor_name, patient_name, medicines, clinic_name, logo_url):
    from io import BytesIO
    from datetime import date
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    PRIMARY = HexColor('#2563EB')
    GRAY    = HexColor('#6B7280')
    LIGHT   = HexColor('#F3F4F6')
    BORDER  = HexColor('#E5E7EB')

    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2.5*cm, leftMargin=2.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    story  = []

    # ── Logo ──────────────────────────────────────────────────────────────────
    if logo_url:
        try:
            import urllib.request
            from reportlab.platypus import Image as RLImage
            img_bytes = BytesIO(urllib.request.urlopen(logo_url, timeout=5).read())
            logo = RLImage(img_bytes, width=5*cm, height=2.5*cm, kind='proportional')
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 0.3*cm))
        except Exception:
            pass

    # ── Brand header ──────────────────────────────────────────────────────────
    if clinic_name:
        story.append(Paragraph(clinic_name, ParagraphStyle(
            'Sub', fontSize=15, textColor=GRAY, fontName='Helvetica-Bold',
            alignment=TA_CENTER, spaceAfter=6,
        )))
    story.append(HRFlowable(width='100%', thickness=2, color=PRIMARY, spaceAfter=14))

    # ── Info table ────────────────────────────────────────────────────────────
    today      = date.today().strftime('%d %B %Y')
    L = ParagraphStyle('L', parent=styles['Normal'], fontSize=11, alignment=TA_LEFT)
    R = ParagraphStyle('R', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT)
    info = Table([
        [Paragraph(f'<b>Doctor:</b>  {doctor_name}',  L), Paragraph(f'<b>Date:</b>  {today}', R)],
        [Paragraph(f'<b>Patient:</b>  {patient_name}', L), Paragraph('', R)],
    ], colWidths=[9*cm, 8.5*cm])
    info.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), LIGHT),
        ('BOX',          (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID',    (0,0), (-1,-1), 0.25, BORDER),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING',   (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
    ]))
    story.append(info)
    story.append(Spacer(1, 0.6*cm))

    # ── Prescription title ────────────────────────────────────────────────────
    story.append(Paragraph('&#8478;  Prescription', ParagraphStyle(
        'Rx', fontSize=17, textColor=PRIMARY,
        fontName='Helvetica-Bold', spaceAfter=12,
    )))

    # ── Medicines ─────────────────────────────────────────────────────────────
    med_style = ParagraphStyle('Med', parent=styles['Normal'], fontSize=12, leftIndent=8, spaceAfter=10)
    for i, med in enumerate(medicines, 1):
        story.append(Paragraph(f'<b>{i}.</b>  {med.get("description", "")}', med_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _upload_pdf_to_cloudinary(pdf_bytes, folder, public_id):
    import cloudinary.uploader, tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        result = cloudinary.uploader.upload(
            tmp_path,
            resource_type='raw',
            folder=folder,
            public_id=public_id,
            type='upload',
            access_mode='public',
        )
        return result['secure_url']
    finally:
        os.unlink(tmp_path)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_reservation_prescription(request, pk):
    from accounts.models import Doctor, Configuration, GeneralService
    from datetime import datetime
    from decimal import Decimal

    try:
        reservation = Reservation.objects.select_related('patient', 'branch').get(pk=pk)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    doctor_id           = request.data.get('doctor_id')
    patient_id          = request.data.get('patient_id')
    discount            = request.data.get('discount')
    medicines           = request.data.get('medicines', [])
    general_service_ids = request.data.get('general_service_ids', [])

    try:
        doctor = Doctor.objects.select_related('user').get(user__pk=doctor_id)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    # ── Set reservation to finished ───────────────────────────────────────────
    if discount is not None:
        reservation.discount = discount
    reservation.status = Reservation.Status.FINISHED
    reservation.save(update_fields=['discount', 'status'])
    if general_service_ids:
        reservation.general_services.set(general_service_ids)

    # ── Collect pricing items ─────────────────────────────────────────────────
    pricing_items = []
    for mapping in DermaFaceMapping.objects.filter(reservation_id=pk):
        pricing_items.extend(_collect_mapping_items(mapping, 'face_mapping'))
    for mapping in DermaBodyMapping.objects.filter(reservation_id=pk):
        pricing_items.extend(_collect_mapping_items(mapping, 'body_mapping'))
    if general_service_ids:
        for gs in GeneralService.objects.filter(pk__in=general_service_ids):
            pricing_items.append({
                'source': 'general_service', 'zone_label': None, 'service_name': None,
                'line_type': 'general_service', 'name': gs.name,
                'detail': '1 service', 'unit_price': str(gs.price), 'total': str(gs.price),
            })

    subtotal = sum(Decimal(i['total']) for i in pricing_items)
    discount_pct = Decimal(str(discount)) if discount else None
    discount_val = (subtotal * discount_pct / Decimal('100')).quantize(Decimal('0.01')) if discount_pct else None
    total = subtotal - discount_val if discount_val else subtotal

    # ── Create or update invoice ──────────────────────────────────────────────
    invoice, _ = Invoice.objects.update_or_create(
        reservation=reservation,
        defaults={'subtotal': subtotal, 'discount': discount_val, 'total': total},
    )

    # ── Fetch clinic config ───────────────────────────────────────────────────
    config      = Configuration.objects.first()
    clinic_name = config.clinic_name if config else ''
    logo_url    = None
    if config and config.logo:
        try:
            logo_url = config.logo.url
        except Exception:
            pass

    timestamp   = datetime.now().strftime('%Y-%m-%d')
    doctor_name = doctor.user.name
    patient_name = patient.full_name

    # ── Generate & upload invoice PDF ─────────────────────────────────────────
    invoice_pdf = _generate_invoice_pdf(
        doctor_name=doctor_name,
        patient_name=patient_name,
        items=pricing_items,
        subtotal=str(subtotal),
        discount=str(discount_val) if discount_val else None,
        total=str(total),
        clinic_name=clinic_name,
        logo_url=logo_url,
    )
    invoice_url = None
    try:
        invoice_url = _upload_pdf_to_cloudinary(
            invoice_pdf, 'invoices', f'invoice_{pk}_{timestamp}.pdf'
        )
        ReservationAttachment.objects.create(
            reservation=reservation, uploaded_by=request.user,
            url=invoice_url, name=f'Invoice_{timestamp}',
        )
    except Exception:
        pass

    # ── Generate & upload prescription PDF (only if medicines provided) ───────
    prescription_url = None
    if medicines:
        prescription_pdf = _generate_prescription_pdf(
            doctor_name=doctor_name,
            patient_name=patient_name,
            medicines=medicines,
            clinic_name=clinic_name,
            logo_url=logo_url,
        )
        try:
            prescription_url = _upload_pdf_to_cloudinary(
                prescription_pdf, 'prescriptions', f'prescription_{pk}_{timestamp}.pdf'
            )
            ReservationAttachment.objects.create(
                reservation=reservation, uploaded_by=request.user,
                url=prescription_url, name=f'Prescription_{timestamp}',
            )
        except Exception:
            pass

    return Response({
        'invoice_id':          invoice.id,
        'invoice_status':      invoice.status,
        'subtotal':            str(subtotal),
        'discount_percentage': str(discount_pct) if discount_pct else None,
        'discount_amount':     str(discount_val) if discount_val else None,
        'total':               str(total),
        'invoice_url':         invoice_url,
        'prescription_url':    prescription_url,
    }, status=status.HTTP_201_CREATED)


# ─── Invoice Pay ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_invoice_pay(request, pk):
    try:
        invoice = Invoice.objects.select_related('reservation').get(pk=pk)
    except Invoice.DoesNotExist:
        return Response({'error': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

    if invoice.status == Invoice.Status.PAID:
        return Response({'error': 'Invoice is already paid.'}, status=status.HTTP_400_BAD_REQUEST)

    invoice.status = Invoice.Status.PAID
    invoice.save(update_fields=['status'])

    reservation_id = invoice.reservation_id
    for mapping in DermaFaceMapping.objects.filter(reservation_id=reservation_id):
        for zone in mapping.zones.prefetch_related('zone_services__lines__product'):
            for zs in zone.zone_services.all():
                for line in zs.lines.all():
                    if line.line_type == 'product' or (line.line_type == 'machine' and line.machine_type == 'injectables'):
                        _decrement_product(line)
    for mapping in DermaBodyMapping.objects.filter(reservation_id=reservation_id):
        for zone in mapping.zones.prefetch_related('zone_services__lines__product'):
            for zs in zone.zone_services.all():
                for line in zs.lines.all():
                    if line.line_type == 'product' or (line.line_type == 'machine' and line.machine_type == 'injectables'):
                        _decrement_product(line)

    return Response({'invoice_id': invoice.id, 'invoice_status': invoice.status})


# ─── Reservation Summary ──────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_reservation_summary(request):
    from datetime import date
    patient_id     = request.query_params.get('patient_id', '').strip()
    reservation_id = request.query_params.get('reservation_id', '').strip()

    if not patient_id or not reservation_id:
        return Response({'error': 'patient_id and reservation_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        reservation = Reservation.objects.select_related('branch', 'doctor__user').get(pk=reservation_id, patient=patient)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    today = date.today()
    dob   = patient.date_of_birth
    age   = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    attachments = reservation.attachments.all()

    return Response({
        'patient': {
            'id':            patient.id,
            'name':          patient.full_name,
            'age':           age,
            'mobile':        patient.mobile_number,
            'medical_notes': patient.medical_notes or None,
        },
        'reservation': {
            'id':                  reservation.id,
            'status':              reservation.status,
            'date_of_visit':       reservation.date_of_visit,
            'slot':                reservation.slot.strftime('%H:%M') if reservation.slot else None,
            'doctor_name':         reservation.doctor.user.name if reservation.doctor else None,
            'branch_name':         reservation.branch.name,
            'discount':            reservation.discount,
            'general_service_ids': list(reservation.general_services.values_list('id', flat=True)),
            'invoice_status':      reservation.invoices.values_list('status', flat=True).first(),
        },
        'attachments': ReservationAttachmentSerializer(attachments, many=True, context={'request': request}).data,
    })


# ─── Patient Profile ──────────────────────────────────────────────────────────


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_patient_profile(request):
    from datetime import date
    patient_id = request.query_params.get('patient_id', '').strip()

    if not patient_id:
        return Response({'error': 'patient_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    today = date.today()
    dob   = patient.date_of_birth
    age   = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # All attachments across all reservations of this patient
    attachments = ReservationAttachment.objects.filter(
        reservation__patient=patient
    ).order_by('-created_at')

    return Response({
        'patient': {
            'id':            patient.id,
            'name':          patient.full_name,
            'age':           age,
            'mobile':        patient.mobile_number,
            'medical_notes': patient.medical_notes or None,
        },
        'attachments': ReservationAttachmentSerializer(attachments, many=True, context={'request': request}).data,
    })


# ─── Derma Face Mapping ───────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_derma_face_mappings(request):
    if request.method == 'GET':
        reservation_id = request.query_params.get('reservation_id', '').strip()
        if not reservation_id:
            return Response({'error': 'reservation_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        mappings = DermaFaceMapping.objects.filter(
            reservation_id=reservation_id
        ).prefetch_related(
            'zones__zone_services__lines__product',
            'zones__zone_services__lines__machine',
            'zones__zone_services__service',
        )
        return Response(DermaFaceMappingSerializer(mappings, many=True).data)

    # POST — one zone per request, multiple services each with lines
    data           = request.data
    reservation_id = data.get('reservation_id')
    patient_id     = data.get('patient_id')
    mapping_type   = data.get('mapping_type', 'face')
    zone_id        = data.get('zone_id')
    zone_label     = data.get('zone_label', '')
    services_data  = data.get('services', [])

    if not reservation_id or not patient_id:
        return Response({'error': 'reservation_id and patient_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        reservation = Reservation.objects.get(pk=reservation_id)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.models import Service

    with transaction.atomic():
        mapping, _ = DermaFaceMapping.objects.get_or_create(
            reservation=reservation,
            patient=patient,
            mapping_type=mapping_type,
        )

        # If zone_id not provided, auto-generate one beyond existing max
        if not zone_id:
            from django.db.models import Max
            max_id = DermaFaceMappingZone.objects.filter(mapping=mapping).aggregate(Max('zone_id'))['zone_id__max'] or 0
            zone_id = max_id + 1

        # Upsert zone — delete existing zone_services (cascades to lines) then recreate
        existing_zone = DermaFaceMappingZone.objects.filter(mapping=mapping, zone_id=zone_id).first()
        if existing_zone:
            existing_zone.zone_services.all().delete()
            existing_zone.zone_label = zone_label
            existing_zone.save()
            zone = existing_zone
        else:
            zone = DermaFaceMappingZone.objects.create(
                mapping=mapping,
                zone_id=zone_id,
                zone_label=zone_label,
            )

        for svc_data in services_data:
            service_id  = svc_data.get('id')
            service     = Service.objects.filter(pk=service_id).first() if service_id else None
            zone_service = DermaFaceMappingZoneService.objects.create(zone=zone, service=service)

            for line_data in svc_data.get('lines', []):
                DermaFaceMappingLine.objects.create(
                    zone_service=zone_service,
                    line_type=line_data.get('line_type', ''),
                    product_id=line_data.get('product_id'),
                    product_type=line_data.get('product_type', ''),
                    quantity=line_data.get('quantity'),
                    volume_ml=line_data.get('volume_ml'),
                    machine_id=line_data.get('machine_id'),
                    machine_type=line_data.get('machine_type', ''),
                    minutes=line_data.get('minutes'),
                    pulses=line_data.get('pulses'),
                )

    result = DermaFaceMapping.objects.prefetch_related(
        'zones__zone_services__lines__product',
        'zones__zone_services__lines__machine',
        'zones__zone_services__service',
    ).get(pk=mapping.pk)
    return Response(DermaFaceMappingSerializer(result).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_derma_face_mapping_detail(request, pk):
    try:
        mapping = DermaFaceMapping.objects.prefetch_related(
            'zones__zone_services__lines__product',
            'zones__zone_services__lines__machine',
            'zones__zone_services__service',
        ).get(pk=pk)
    except DermaFaceMapping.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(DermaFaceMappingSerializer(mapping).data)

    mapping.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_derma_face_mapping_line_detail(request, pk):
    try:
        line = DermaFaceMappingLine.objects.get(pk=pk)
    except DermaFaceMappingLine.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    line.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_zone_definitions(request):
    zones = ZoneDefinition.objects.all()
    return Response([{'zone_id': z.zone_id, 'zone_label': z.zone_label} for z in zones])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_body_zone_definitions(request):
    zones = BodyZoneDefinition.objects.all()
    return Response([{'zone_id': z.zone_id, 'zone_label': z.zone_label} for z in zones])


# ─── Derma Body Mapping ───────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_derma_body_mappings(request):
    if request.method == 'GET':
        reservation_id = request.query_params.get('reservation_id', '').strip()
        if not reservation_id:
            return Response({'error': 'reservation_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        mappings = DermaBodyMapping.objects.filter(
            reservation_id=reservation_id
        ).prefetch_related(
            'zones__zone_services__lines__product',
            'zones__zone_services__lines__machine',
            'zones__zone_services__service',
        )
        return Response(DermaBodyMappingSerializer(mappings, many=True).data)

    # POST — one zone per request, multiple services each with lines
    data           = request.data
    reservation_id = data.get('reservation_id')
    patient_id     = data.get('patient_id')
    mapping_type   = data.get('mapping_type', 'body')
    zone_id        = data.get('zone_id')
    zone_label     = data.get('zone_label', '')
    services_data  = data.get('services', [])

    if not reservation_id or not patient_id:
        return Response({'error': 'reservation_id and patient_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        reservation = Reservation.objects.get(pk=reservation_id)
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.models import Service
    from django.db.models import Max

    with transaction.atomic():
        mapping, _ = DermaBodyMapping.objects.get_or_create(
            reservation=reservation,
            patient=patient,
            mapping_type=mapping_type,
        )

        if zone_id is None or (isinstance(zone_id, int) and zone_id < 0):
            max_id = DermaBodyMappingZone.objects.filter(mapping=mapping).aggregate(Max('zone_id'))['zone_id__max'] or 0
            zone_id = max(max_id, 5) + 1  # body has 5 standard zones

        existing_zone = DermaBodyMappingZone.objects.filter(mapping=mapping, zone_id=zone_id).first()
        if existing_zone:
            existing_zone.zone_services.all().delete()
            existing_zone.zone_label = zone_label
            existing_zone.save()
            zone = existing_zone
        else:
            zone = DermaBodyMappingZone.objects.create(
                mapping=mapping,
                zone_id=zone_id,
                zone_label=zone_label,
            )

        for svc_data in services_data:
            service_id   = svc_data.get('id')
            service      = Service.objects.filter(pk=service_id).first() if service_id else None
            zone_service = DermaBodyMappingZoneService.objects.create(zone=zone, service=service)

            for line_data in svc_data.get('lines', []):
                DermaBodyMappingLine.objects.create(
                    zone_service=zone_service,
                    line_type=line_data.get('line_type', ''),
                    product_id=line_data.get('product_id'),
                    product_type=line_data.get('product_type', ''),
                    quantity=line_data.get('quantity'),
                    volume_ml=line_data.get('volume_ml'),
                    machine_id=line_data.get('machine_id'),
                    machine_type=line_data.get('machine_type', ''),
                    minutes=line_data.get('minutes'),
                    pulses=line_data.get('pulses'),
                )

    result = DermaBodyMapping.objects.prefetch_related(
        'zones__zone_services__lines__product',
        'zones__zone_services__lines__machine',
        'zones__zone_services__service',
    ).get(pk=mapping.pk)
    return Response(DermaBodyMappingSerializer(result).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_derma_body_mapping_detail(request, pk):
    try:
        mapping = DermaBodyMapping.objects.prefetch_related(
            'zones__zone_services__lines__product',
            'zones__zone_services__lines__machine',
            'zones__zone_services__service',
        ).get(pk=pk)
    except DermaBodyMapping.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(DermaBodyMappingSerializer(mapping).data)

    mapping.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_derma_body_mapping_line_detail(request, pk):
    try:
        line = DermaBodyMappingLine.objects.get(pk=pk)
    except DermaBodyMappingLine.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    line.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Reservation Pricing ──────────────────────────────────────────────────────

def _decrement_product(line):
    import math
    from decimal import Decimal

    product = line.product
    if not product:
        return

    if line.product_type == 'syringe':
        qty = line.quantity or 1
        product.quantity = max(0, product.quantity - qty)
        product.save(update_fields=['quantity'])

    elif line.product_type == 'veil':
        if not product.volume or product.volume == 0:
            return
        used_ml    = Decimal(str(line.volume_ml or 0))
        remainder  = product.remainder_ml or Decimal('0')
        vol_per_vial = Decimal(str(product.volume))

        if used_ml <= remainder:
            product.remainder_ml = remainder - used_ml
            product.save(update_fields=['remainder_ml'])
        else:
            still_needed  = used_ml - remainder
            vials_needed  = math.ceil(float(still_needed) / float(vol_per_vial))
            new_remainder = Decimal(str(vials_needed)) * vol_per_vial - still_needed
            product.quantity     = max(0, product.quantity - vials_needed)
            product.remainder_ml = new_remainder
            product.save(update_fields=['quantity', 'remainder_ml'])


def _price_line(line):
    from decimal import Decimal, ROUND_HALF_UP

    def dec(v):
        return Decimal(str(v or 0))

    if line.line_type == 'product' or (line.line_type == 'machine' and line.machine_type == 'injectables'):
        product = line.product
        if not product:
            return None
        if line.product_type == 'veil':
            vol   = dec(line.volume_ml)
            total = (product.price * vol).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return {'detail': f'{line.volume_ml} ml', 'unit_price': str(product.price), 'total': str(total)}
        elif line.product_type == 'syringe':
            qty   = dec(line.quantity or 1)
            total = (product.price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return {'detail': f'{line.quantity} syringe(s)', 'unit_price': str(product.price), 'total': str(total)}

    elif line.line_type == 'machine':
        machine = line.machine
        if not machine:
            return None
        if line.machine_type == 'pulses':
            pulses = dec(line.pulses)
            total  = (machine.price * pulses).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return {'detail': f'{line.pulses} pulses', 'unit_price': str(machine.price), 'total': str(total)}
        elif line.machine_type == 'duration':
            mins  = dec(line.minutes)
            total = (machine.price * mins).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return {'detail': f'{line.minutes} minutes', 'unit_price': str(machine.price), 'total': str(total)}
        elif line.machine_type == 'sessions':
            return {'detail': '1 session', 'unit_price': str(machine.price), 'total': str(machine.price)}

    return None


def _collect_mapping_items(mapping, source):
    items = []
    for zone in mapping.zones.prefetch_related(
        'zone_services__lines__product',
        'zone_services__lines__machine',
        'zone_services__service',
    ).all():
        for zone_service in zone.zone_services.all():
            for line in zone_service.lines.all():
                pricing = _price_line(line)
                if not pricing:
                    continue
                name = (
                    line.product.name if line.product_id else
                    line.machine.name if line.machine_id else ''
                )
                items.append({
                    'source':       source,
                    'zone_label':   zone.zone_label,
                    'service_name': zone_service.service.name if zone_service.service_id else None,
                    'line_type':    line.line_type,
                    'name':         name,
                    **pricing,
                })
    return items


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_reservation_pricing(request):
    from decimal import Decimal
    from accounts.models import GeneralService

    reservation_id       = request.data.get('reservation_id')
    general_service_ids  = request.data.get('general_service_ids', [])

    if not reservation_id:
        return Response({'error': 'reservation_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    items = []

    # Face mapping lines
    for mapping in DermaFaceMapping.objects.filter(reservation_id=reservation_id):
        items.extend(_collect_mapping_items(mapping, 'face_mapping'))

    # Body mapping lines
    for mapping in DermaBodyMapping.objects.filter(reservation_id=reservation_id):
        items.extend(_collect_mapping_items(mapping, 'body_mapping'))

    # Selected general services
    if general_service_ids:
        for gs in GeneralService.objects.filter(pk__in=general_service_ids):
            items.append({
                'source':     'general_service',
                'zone_label': None,
                'service_name': None,
                'line_type':  'general_service',
                'name':       gs.name,
                'detail':     '1 service',
                'unit_price': str(gs.price),
                'total':      str(gs.price),
            })

    grand_total = sum(Decimal(i['total']) for i in items)

    return Response({
        'items':       items,
        'grand_total': str(grand_total.quantize(Decimal('0.01'))),
    })
