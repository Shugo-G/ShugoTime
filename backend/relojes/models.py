from django.db import models
from django.utils import timezone


class Reloj(models.Model):
    ESTADO_OK = "ok"
    ESTADO_ERROR = "error"
    ESTADO_PENDIENTE = "pendiente"
    ESTADOS = [
        (ESTADO_OK, "OK"),
        (ESTADO_ERROR, "Error"),
        (ESTADO_PENDIENTE, "Pendiente"),
    ]

    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    ip = models.CharField(max_length=45, verbose_name="Direccion IP")
    puerto = models.IntegerField(default=4370, verbose_name="Puerto")
    password = models.IntegerField(default=0, verbose_name="Password")
    idadm = models.IntegerField(default=0, verbose_name="ID Administracion")
    es_lector = models.BooleanField(default=False, verbose_name="Es solo lector")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    # Estado calculado tras la ultima lectura
    ultimo_ciclo = models.DateTimeField(null=True, blank=True, verbose_name="Ultimo ciclo")
    ultimo_estado = models.CharField(
        max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE, verbose_name="Ultimo estado"
    )
    ultimo_error = models.TextField(blank=True, verbose_name="Ultimo error")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reloj"
        verbose_name_plural = "Relojes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class CicloLectura(models.Model):
    ESTADO_EN_PROGRESO = "en_progreso"
    ESTADO_EXITOSO = "exitoso"
    ESTADO_ERROR = "error"
    ESTADOS = [
        (ESTADO_EN_PROGRESO, "En progreso"),
        (ESTADO_EXITOSO, "Exitoso"),
        (ESTADO_ERROR, "Error"),
    ]

    relojes = models.ManyToManyField(Reloj, blank=True, verbose_name="Relojes")
    inicio = models.DateTimeField(auto_now_add=True, verbose_name="Inicio")
    fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin")
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default=ESTADO_EN_PROGRESO, verbose_name="Estado"
    )
    total_fichadas = models.IntegerField(default=0, verbose_name="Total fichadas")

    class Meta:
        verbose_name = "Ciclo de lectura"
        verbose_name_plural = "Ciclos de lectura"
        ordering = ["-inicio"]

    def __str__(self):
        return f"Ciclo {self.id} - {self.inicio.strftime('%d/%m/%Y %H:%M')} ({self.estado})"

    @property
    def duracion_segundos(self):
        if self.fin:
            return int((self.fin - self.inicio).total_seconds())
        return None


class LogEntry(models.Model):
    ciclo = models.ForeignKey(
        CicloLectura, on_delete=models.CASCADE, related_name="logs", verbose_name="Ciclo"
    )
    reloj_nombre = models.CharField(max_length=100, verbose_name="Reloj")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Fecha/Hora")
    operacion = models.CharField(max_length=100, verbose_name="Operacion")
    detalle = models.TextField(verbose_name="Detalle")
    advertencia = models.BooleanField(default=False, verbose_name="Advertencia")

    class Meta:
        verbose_name = "Entrada de log"
        verbose_name_plural = "Entradas de log"
        ordering = ["id"]

    def __str__(self):
        return f"[{self.timestamp.strftime('%d/%m/%Y %H:%M:%S')}] {self.reloj_nombre} - {self.operacion}"
