from django.conf import settings


def send_sms(to: str, message: str):
    from vonage import Auth, Vonage
    from vonage_messages import Sms

    client = Vonage(Auth(
        api_key=settings.VONAGE_API_KEY,
        api_secret=settings.VONAGE_API_SECRET,
    ))
    client.messages.send(
        Sms(
            to=to,
            from_='Clivio',
            text=message,
        )
    )
