from twilio.rest import Client
from django.conf import settings


def send_sms(to: str, message: str):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        messaging_service_sid=settings.TWILIO_MESSAGING_SERVICE_SID,
        to=to,
    )
