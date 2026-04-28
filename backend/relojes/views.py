import os

import psycopg2
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Reloj, CicloLectura, LogEntry, TareaProgramada
from .serializers import RelojSerializer, CicloLecturaSerializer, LogEntrySerializer, TareaProgramadaSerializer
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
    """Consulta y filtra fichadas desde la tabla ingresopersonal (PostgreSQL)."""

    _TIPO_MAP = {1: 'Entrada', 2: 'Salida', 3: 'Almuerzo', 4: 'Regreso'}
    _LIMITE = 500

    def list(self, request):
        reloj_filtro  = request.query_params.get('reloj', '').strip()
        legajo_raw    = request.query_params.get('legajo', '').strip()
        nombre_filtro = request.query_params.get('nombre', '').strip()
        fecha_desde   = request.query_params.get('fecha_desde', '').strip()
        fecha_hasta   = request.query_params.get('fecha_hasta', '').strip()

        legajo_filtro = ''
        if legajo_raw:
            try:
                legajo_filtro = str(int(legajo_raw)).zfill(11)
            except ValueError:
                legajo_filtro = legajo_raw.zfill(11)

        # ip → nombre del reloj (desde Django SQLite)
        ip_to_nombre = {r.ip: r.nombre for r in Reloj.objects.all()}
        relojes_disponibles = sorted(ip_to_nombre.values())

        conditions = []
        params = []

        if legajo_filtro:
            conditions.append("i.idper = %s")
            params.append(legajo_filtro)

        if fecha_desde:
            conditions.append("i.hora::date >= %s")
            params.append(fecha_desde)

        if fecha_hasta:
            conditions.append("i.hora::date <= %s")
            params.append(fecha_hasta)

        if nombre_filtro:
            conditions.append(
                "TRIM(COALESCE(p.nombre,'') || ' ' || COALESCE(p.apellido,'')) ILIKE %s"
            )
            params.append(f"%{nombre_filtro}%")

        if reloj_filtro:
            ips = [ip for ip, nombre in ip_to_nombre.items() if nombre == reloj_filtro]
            if not ips:
                return Response({
                    'total': 0, 'mostrados': 0,
                    'relojes_disponibles': relojes_disponibles,
                    'registros': [],
                })
            placeholders = ','.join(['%s'] * len(ips))
            conditions.append(f"i.ip IN ({placeholders})")
            params.extend(ips)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        db_conf = settings.FICHADAS_DB
        try:
            pg = psycopg2.connect(
                host=db_conf["host"], port=db_conf["port"],
                dbname=db_conf["dbname"], user=db_conf["user"],
                password=db_conf["password"], options=db_conf.get("options", ""),
            )
            with pg:
                with pg.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM public.ingresopersonal i "
                        f"LEFT JOIN public.persons p ON p.idper = i.idper "
                        f"{where}",
                        params,
                    )
                    total = cur.fetchone()[0]

                    cur.execute(
                        f"SELECT i.idper, i.hora, i.idtctrlper, i.ip, "
                        f"TRIM(COALESCE(p.nombre,'')) || ' ' || TRIM(COALESCE(p.apellido,'')) "
                        f"FROM public.ingresopersonal i "
                        f"LEFT JOIN public.persons p ON p.idper = i.idper "
                        f"{where} "
                        f"ORDER BY i.hora DESC LIMIT %s",
                        params + [self._LIMITE],
                    )
                    rows = cur.fetchall()
            pg.close()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        registros = [
            {
                'legajo': (idper or '').strip(),
                'nombre': (nombre or '').strip(),
                'hora':   hora.strftime('%Y-%m-%d %H:%M:%S.000') if hora else '',
                'tipo':   self._TIPO_MAP.get(idtctrlper, str(idtctrlper)),
                'reloj':  ip_to_nombre.get(ip, ip),
            }
            for idper, hora, idtctrlper, ip, nombre in rows
        ]

        return Response({
            'total':               total,
            'mostrados':           len(registros),
            'relojes_disponibles': relojes_disponibles,
            'registros':           registros,
        })


class TareaProgramadaViewSet(viewsets.ModelViewSet):
    queryset = TareaProgramada.objects.all().prefetch_related("relojes")
    serializer_class = TareaProgramadaSerializer

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        tarea = self.get_object()
        tarea.activo = not tarea.activo
        tarea.save(update_fields=["activo", "fecha_modificacion"])
        return Response({"activo": tarea.activo})


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
