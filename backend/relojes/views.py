from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Reloj, CicloLectura, LogEntry
from .serializers import RelojSerializer, CicloLecturaSerializer, LogEntrySerializer
from . import zk_reader


class RelojViewSet(viewsets.ModelViewSet):
    queryset = Reloj.objects.all()
    serializer_class = RelojSerializer

    @action(detail=True, methods=["post"], url_path="leer")
    def leer(self, request, pk=None):
        """Dispara la lectura de un reloj especifico."""
        reloj = self.get_object()
        if not reloj.activo:
            return Response(
                {"error": "El reloj esta inactivo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ciclo_id, error = zk_reader.iniciar_ciclo(reloj_ids=[reloj.id])
        if error:
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)
        return Response({"ciclo_id": ciclo_id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="reiniciar")
    def reiniciar(self, request, pk=None):
        """Envía el comando de reinicio al reloj."""
        reloj = self.get_object()
        if not reloj.activo:
            return Response(
                {"error": "El reloj está inactivo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, error = zk_reader.reiniciar_reloj(reloj)
        if not success:
            return Response({"error": error}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"ok": True}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="leer-todos")
    def leer_todos(self, request):
        """Dispara la lectura de todos los relojes activos."""
        ciclo_id, error = zk_reader.iniciar_ciclo()
        if error:
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)
        return Response({"ciclo_id": ciclo_id}, status=status.HTTP_202_ACCEPTED)


class CicloLecturaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CicloLectura.objects.all().prefetch_related("relojes").order_by("-inicio")
    serializer_class = CicloLecturaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        limite = self.request.query_params.get("limite")
        if limite:
            try:
                qs = qs[: int(limite)]
            except (ValueError, TypeError):
                pass
        return qs


class LogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LogEntrySerializer

    def get_queryset(self):
        qs = LogEntry.objects.all().order_by("-id")

        ciclo_id = self.request.query_params.get("ciclo")
        if ciclo_id:
            qs = qs.filter(ciclo_id=ciclo_id)

        after_id = self.request.query_params.get("after_id")
        if after_id:
            qs = qs.filter(id__gt=int(after_id))

        reloj = self.request.query_params.get("reloj")
        if reloj:
            qs = qs.filter(reloj_nombre__icontains=reloj)

        solo_advertencias = self.request.query_params.get("advertencias")
        if solo_advertencias == "1":
            qs = qs.filter(advertencia=True)

        return qs


class EstadoView(viewsets.ViewSet):
    """Endpoint de estado general de la aplicacion."""

    def list(self, request):
        en_progreso = zk_reader.hay_ciclo_en_progreso()

        ciclo_activo = None
        if en_progreso:
            ciclo_obj = (
                CicloLectura.objects.filter(estado=CicloLectura.ESTADO_EN_PROGRESO)
                .order_by("-inicio")
                .first()
            )
            if ciclo_obj:
                ciclo_activo = CicloLecturaSerializer(ciclo_obj).data

        ultimo_ciclo = (
            CicloLectura.objects.exclude(estado=CicloLectura.ESTADO_EN_PROGRESO)
            .order_by("-inicio")
            .first()
        )

        return Response(
            {
                "en_progreso": en_progreso,
                "ciclo_activo": ciclo_activo,
                "ultimo_ciclo": CicloLecturaSerializer(ultimo_ciclo).data if ultimo_ciclo else None,
                "total_relojes": Reloj.objects.count(),
                "relojes_activos": Reloj.objects.filter(activo=True).count(),
                "relojes_con_error": Reloj.objects.filter(
                    ultimo_estado=Reloj.ESTADO_ERROR
                ).count(),
            }
        )
