import os

from django.conf import settings
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

    @action(detail=True, methods=["get"], url_path="registros")
    def registros(self, request, pk=None):
        """Lee los registros almacenados en el reloj sin modificarlo."""
        reloj = self.get_object()
        if not reloj.activo:
            return Response(
                {"error": "El reloj está inactivo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        records, error = zk_reader.leer_registros_reloj(reloj)
        if error:
            return Response({"error": error}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"registros": records, "total": len(records)})

    @action(detail=True, methods=["post"], url_path="ping")
    def ping(self, request, pk=None):
        """Verifica conectividad con el reloj sin realizar cambios."""
        reloj = self.get_object()
        if not reloj.activo:
            return Response(
                {"error": "El reloj está inactivo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, error = zk_reader.ping_reloj(reloj)
        if not success:
            return Response({"error": error}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"ok": True}, status=status.HTTP_200_OK)

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


class FichadasView(viewsets.ViewSet):
    """Lee y filtra los registros guardados en los archivos .txt de fichadas."""

    _TIPO_MAP = {'1': 'Entrada', '2': 'Salida', '3': 'Almuerzo', '4': 'Regreso'}
    _LIMITE = 500

    def list(self, request):
        fichadas_dir = settings.FICHADAS_DIR
        reloj_filtro  = request.query_params.get('reloj', '').strip()
        legajo_raw    = request.query_params.get('legajo', '').strip()
        fecha_desde   = request.query_params.get('fecha_desde', '').strip()
        fecha_hasta   = request.query_params.get('fecha_hasta', '').strip()

        legajo_filtro = ''
        if legajo_raw:
            try:
                legajo_filtro = str(int(legajo_raw)).zfill(11)
            except ValueError:
                legajo_filtro = legajo_raw.zfill(11)

        try:
            archivos = sorted(f for f in os.listdir(fichadas_dir) if f.endswith('.txt'))
        except OSError:
            archivos = []

        relojes_disponibles = [a[:-4] for a in archivos]
        registros = []
        seen = set()

        for archivo in archivos:
            reloj_nombre = archivo[:-4]
            if reloj_filtro and reloj_nombre != reloj_filtro:
                continue
            try:
                with open(os.path.join(fichadas_dir, archivo), encoding='utf-8') as f:
                    for line in f:
                        line = line.rstrip('\n')
                        if not line or line.startswith('#') or len(line) < 35:
                            continue
                        try:
                            idper      = line[0:11].strip()
                            hora       = line[12:35].strip()
                            idtctrlper = line[43:55].strip() if len(line) > 43 else ''
                            nombre     = line[81:].strip()   if len(line) > 81 else ''

                            if legajo_filtro and idper != legajo_filtro:
                                continue
                            if fecha_desde and hora[:10] < fecha_desde:
                                continue
                            if fecha_hasta and hora[:10] > fecha_hasta:
                                continue

                            key = (idper, hora, reloj_nombre)
                            if key in seen:
                                continue
                            seen.add(key)

                            registros.append({
                                'legajo': idper,
                                'nombre': nombre,
                                'hora':   hora,
                                'tipo':   self._TIPO_MAP.get(idtctrlper, idtctrlper),
                                'reloj':  reloj_nombre,
                            })
                        except (IndexError, ValueError):
                            continue
            except OSError:
                continue

        registros.sort(key=lambda r: r['hora'], reverse=True)
        total = len(registros)
        return Response({
            'total':               total,
            'mostrados':           min(total, self._LIMITE),
            'relojes_disponibles': relojes_disponibles,
            'registros':           registros[:self._LIMITE],
        })


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
