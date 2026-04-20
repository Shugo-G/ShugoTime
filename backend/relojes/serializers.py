from rest_framework import serializers
from .models import Reloj, CicloLectura, LogEntry


class RelojSerializer(serializers.ModelSerializer):
    ultimo_ciclo_display = serializers.SerializerMethodField()

    class Meta:
        model = Reloj
        fields = [
            "id",
            "nombre",
            "ip",
            "puerto",
            "password",
            "idadm",
            "es_lector",
            "activo",
            "ultimo_ciclo",
            "ultimo_ciclo_display",
            "ultimo_estado",
            "ultimo_error",
            "fecha_creacion",
            "fecha_modificacion",
        ]
        read_only_fields = [
            "ultimo_ciclo",
            "ultimo_estado",
            "ultimo_error",
            "fecha_creacion",
            "fecha_modificacion",
        ]

    def get_ultimo_ciclo_display(self, obj):
        if obj.ultimo_ciclo:
            from django.utils import timezone
            local = timezone.localtime(obj.ultimo_ciclo)
            return local.strftime("%d/%m/%Y %H:%M:%S")
        return None


class LogEntrySerializer(serializers.ModelSerializer):
    timestamp_display = serializers.SerializerMethodField()

    class Meta:
        model = LogEntry
        fields = [
            "id",
            "ciclo_id",
            "reloj_nombre",
            "timestamp",
            "timestamp_display",
            "operacion",
            "detalle",
            "advertencia",
        ]

    def get_timestamp_display(self, obj):
        from django.utils import timezone
        local = timezone.localtime(obj.timestamp)
        return local.strftime("%d/%m/%Y %H:%M:%S")


class CicloLecturaSerializer(serializers.ModelSerializer):
    relojes_nombres = serializers.SerializerMethodField()
    duracion_segundos = serializers.ReadOnlyField()
    inicio_display = serializers.SerializerMethodField()
    fin_display = serializers.SerializerMethodField()

    class Meta:
        model = CicloLectura
        fields = [
            "id",
            "relojes",
            "relojes_nombres",
            "inicio",
            "inicio_display",
            "fin",
            "fin_display",
            "estado",
            "total_fichadas",
            "duracion_segundos",
        ]

    def get_relojes_nombres(self, obj):
        return list(obj.relojes.values_list("nombre", flat=True))

    def get_inicio_display(self, obj):
        from django.utils import timezone
        return timezone.localtime(obj.inicio).strftime("%d/%m/%Y %H:%M:%S")

    def get_fin_display(self, obj):
        if obj.fin:
            from django.utils import timezone
            return timezone.localtime(obj.fin).strftime("%d/%m/%Y %H:%M:%S")
        return None
