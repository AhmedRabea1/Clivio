from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Reservation
from .serializers import PublicReservationCreateSerializer, ReservationSerializer


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
