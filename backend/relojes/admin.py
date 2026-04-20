from django.contrib import admin
from .models import Reloj, CicloLectura, LogEntry


@admin.register(Reloj)
class RelojAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ip", "puerto", "idadm", "activo", "ultimo_estado", "ultimo_ciclo"]
    list_filter = ["activo", "ultimo_estado"]
    search_fields = ["nombre", "ip"]


@admin.register(CicloLectura)
class CicloLecturaAdmin(admin.ModelAdmin):
    list_display = ["id", "inicio", "fin", "estado", "total_fichadas"]
    list_filter = ["estado"]


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "reloj_nombre", "operacion", "detalle", "advertencia"]
    list_filter = ["advertencia", "reloj_nombre"]
    search_fields = ["reloj_nombre", "operacion", "detalle"]
