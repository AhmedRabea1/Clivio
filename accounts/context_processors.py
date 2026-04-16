import base64
from .models import Configuration


def clinic_config(request):
    """
    Injects clinic configuration into every template context.
    logo_b64 and hero_b64 are ready-to-use data URIs: data:image/...;base64,...
    """
    config = None
    logo_b64 = None
    hero_b64 = None

    if request.user.is_authenticated and request.user.clinic_id:
        try:
            config = Configuration.objects.get(clinic_id=request.user.clinic_id)
            if config.logo:
                logo_b64 = 'data:image/png;base64,' + base64.b64encode(bytes(config.logo)).decode('utf-8')
            if config.hero_image:
                hero_b64 = 'data:image/png;base64,' + base64.b64encode(bytes(config.hero_image)).decode('utf-8')
        except Configuration.DoesNotExist:
            pass

    return {
        'clinic_config': config,
        'logo_b64': logo_b64,
        'hero_b64': hero_b64,
    }
