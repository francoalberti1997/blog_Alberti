from django.db import models


class UsageEvent(models.Model):
    """Telemetría de uso de la aplicación. Cada evento registra una acción
    del usuario con metadata opcional."""

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_events',
    )
    company = models.ForeignKey(
        'member.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_events',
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tipo de evento: login, mask_generated, pdf_exported, etc."
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos adicionales del evento (material, tiempo de procesamiento, etc.)"
    )
    app_version = models.CharField(max_length=20, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.event_type} — {self.user}"
