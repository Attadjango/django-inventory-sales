from django.conf import settings


def demo_mode(request):
    """Expose demo settings to templates."""
    user = getattr(request, 'user', None)
    restricted = bool(
        settings.DEMO_MODE and user is not None and user.is_authenticated and not user.is_staff
    )
    context = {'demo_mode': settings.DEMO_MODE, 'demo_restricted': restricted}
    if settings.DEMO_MODE:
        context['demo_username'] = settings.DEMO_USERNAME
        context['demo_password'] = settings.DEMO_PASSWORD
    return context
