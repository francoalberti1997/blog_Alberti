"""Helpers para registrar eventos de telemetría de forma simple."""

from .models import UsageEvent


def track(event_type: str, *, user=None, company=None, metadata=None, app_version=''):
    """Registra un evento de uso. Uso:

        from analytics.track import track
        track("mask_generated", user=request.user, metadata={"material": "Acero BC"})
    """
    resolved_company = company
    if resolved_company is None and user and hasattr(user, 'member'):
        try:
            resolved_company = user.member.company
        except Exception:
            pass

    return UsageEvent.objects.create(
        event_type=event_type,
        user=user,
        company=resolved_company,
        metadata=metadata or {},
        app_version=app_version,
    )
