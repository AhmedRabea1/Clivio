from .models import Configuration


def clinic_config(request):
    config = None
    logo_b64 = None
    hero_b64 = None

    if request.user.is_authenticated and request.user.clinic_id:
        try:
            config = Configuration.objects.get(clinic_id=request.user.clinic_id)
            if config.logo:
                logo_b64 = config.logo.url
            if config.hero_image:
                hero_b64 = config.hero_image.url
        except Configuration.DoesNotExist:
            pass

    return {
        'clinic_config': config,
        'logo_b64': logo_b64,
        'hero_b64': hero_b64,
    }
