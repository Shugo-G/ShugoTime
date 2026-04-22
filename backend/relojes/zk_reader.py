# -*- coding: utf-8 -*-
"""
Modulo de lectura de relojes ZK.
Adaptado de leer_relojes.py para funcionar con modelos Django y
registrar logs en la base de datos en lugar de imprimir en consola.
"""
import os
import threading
from datetime import datetime

import psycopg2
from django.conf import settings
from django.utils import timezone

from zk import ZK

# Mapeo de tipo de fichada ZK -> idtctrlper de base de datos
PUNCH_MAP = {
    0: 1,   # Check In      -> Entrada
    1: 2,   # Check Out     -> Salida
    4: 3,   # Overtime In   -> Almuerzo
    5: 4,   # Overtime Out  -> Regreso Almuerzo
}

COL_IDPER      = 11
COL_HORA       = 23
COL_IDADM      = 6
COL_IDTCTRLPER = 12
COL_IP         = 24
COL_NOMBRE     = 30


def punch_to_idtctrlper(punch):
    return PUNCH_MAP.get(punch, 99)


def _log(ciclo, nombre, operacion, detalle, advertencia=False):
    """Crea un LogEntry en la base de datos."""
    from .models import LogEntry
    LogEntry.objects.create(
        ciclo=ciclo,
        reloj_nombre=nombre,
        operacion=operacion,
        detalle=detalle,
        advertencia=advertencia,
        timestamp=timezone.now(),
    )


def _guardar_fichadas(attendances, idadm, ip_reloj, nombre_reloj, usuarios=None):
    """Guarda las fichadas en un archivo de texto (backup local).

    usuarios: dict {user_id_str: nombre} obtenido de conn.get_users().
              Si se provee, se agrega el nombre de cada usuario al final de la línea.
    """
    fichadas_dir = settings.FICHADAS_DIR
    os.makedirs(fichadas_dir, exist_ok=True)
    filepath = os.path.join(fichadas_dir, f"{nombre_reloj}.txt")
    ordenadas = sorted(attendances, key=lambda a: a.timestamp, reverse=True)

    contenido_existente = ""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            contenido_existente = f.read()

    nuevas_lineas = (
        f"# Lectura: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        f" - {len(ordenadas)} fichadas\n"
    )
    for a in ordenadas:
        idper      = str(a.user_id).zfill(COL_IDPER)
        hora       = a.timestamp.strftime("%Y-%m-%d %H:%M:%S.000")
        idtctrlper = punch_to_idtctrlper(a.punch)
        nombre_usuario = (usuarios or {}).get(str(a.user_id), "")
        nuevas_lineas += (
            f"{idper:<{COL_IDPER}} "
            f"{hora:<{COL_HORA}} "
            f"{idadm:<{COL_IDADM}} "
            f"{idtctrlper:<{COL_IDTCTRLPER}} "
            f"{ip_reloj:<{COL_IP}} "
            f"{nombre_usuario:<{COL_NOMBRE}}\n"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(nuevas_lineas + contenido_existente)
    return filepath


def _insertar_fichadas(attendances, idadm, ip_reloj, ciclo, nombre):
    """Inserta las fichadas en la base de datos de personal via psycopg2."""
    SQL = """
        INSERT INTO public.ingresopersonal (idper, hora, idadm, idtctrlper, ip)
        VALUES (%s, %s, %s, %s, %s)
    """
    registros = [
        (
            str(a.user_id).zfill(COL_IDPER),
            a.timestamp,
            idadm,
            punch_to_idtctrlper(a.punch),
            ip_reloj,
        )
        for a in attendances
    ]
    db_conf = settings.FICHADAS_DB
    conn = psycopg2.connect(
        host=db_conf["host"],
        port=db_conf["port"],
        dbname=db_conf["dbname"],
        user=db_conf["user"],
        password=db_conf["password"],
        options=db_conf.get("options", ""),
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.executemany(SQL, registros)
        _log(ciclo, nombre, "Base de datos", f"Insertados {len(registros)} registros OK")
    finally:
        conn.close()


def _filtrar_nuevas_fichadas(attendances, ip_reloj, ciclo, nombre):
    """
    Devuelve solo las fichadas genuinamente nuevas:
    1. Elimina dobles fichadas: registros consecutivos del mismo usuario en menos de 60 s (conserva el primero).
    2. Elimina registros ya presentes en la DB para esta IP.
    """
    if not attendances:
        return []

    # Paso 1: eliminar dobles fichadas por usuario
    ordenadas = sorted(attendances, key=lambda a: (str(a.user_id), a.timestamp))
    sin_dobles = []
    ultima_ts = {}
    for a in ordenadas:
        uid = str(a.user_id)
        prev = ultima_ts.get(uid)
        if prev is not None and (a.timestamp - prev).total_seconds() < 60:
            continue
        ultima_ts[uid] = a.timestamp
        sin_dobles.append(a)

    omitidas_dobles = len(attendances) - len(sin_dobles)
    if omitidas_dobles:
        _log(ciclo, nombre, "Dedup",
             f"Omitidas {omitidas_dobles} dobles fichadas (mismo usuario, <1 min)")

    if not sin_dobles:
        return []

    # Paso 2: filtrar contra registros ya existentes en DB
    min_ts = min(a.timestamp for a in sin_dobles)
    max_ts = max(a.timestamp for a in sin_dobles)

    db_conf = settings.FICHADAS_DB
    pg_conn = psycopg2.connect(
        host=db_conf["host"], port=db_conf["port"], dbname=db_conf["dbname"],
        user=db_conf["user"], password=db_conf["password"],
        options=db_conf.get("options", ""),
    )
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT idper, hora FROM public.ingresopersonal "
                "WHERE ip = %s AND hora BETWEEN %s AND %s",
                (ip_reloj, min_ts, max_ts),
            )
            existentes = {(row[0].strip(), row[1]) for row in cur.fetchall()}
    finally:
        pg_conn.close()

    nuevas = [
        a for a in sin_dobles
        if (str(a.user_id).zfill(COL_IDPER), a.timestamp) not in existentes
    ]
    omitidas_db = len(sin_dobles) - len(nuevas)
    if omitidas_db:
        _log(ciclo, nombre, "Dedup",
             f"Omitidas {omitidas_db} fichadas ya presentes en DB")

    return nuevas


def _procesar_reloj(reloj_obj, ciclo):
    """
    Conecta al reloj, lee las fichadas, las persiste y limpia el reloj.
    Retorna (cantidad_fichadas, error_str_o_None).
    """
    nombre   = reloj_obj.nombre
    ip       = reloj_obj.ip
    puerto   = reloj_obj.puerto
    password = reloj_obj.password
    es_lector = reloj_obj.es_lector
    idadm    = reloj_obj.idadm

    _log(ciclo, nombre, "Comienzo",
         f"Mod: ZK - TFT - IP: {ip} - esLector: {es_lector}")

    conn = None
    fichadas_count = 0
    error = None

    try:
        zk = ZK(ip, port=puerto, timeout=5, password=password,
                 force_udp=False, ommit_ping=False)

        _log(ciclo, nombre, "Conectando", "Conectando...")
        conn = zk.connect()
        _log(ciclo, nombre, "Conectando", "Conectado con exito")

        _log(ciclo, nombre, "Inicializando", "Leyendo registros...")
        attendances = conn.get_attendance()
        cantidad = len(attendances)
        _log(ciclo, nombre, "Inicializando", f"Cantidad de fichadas: {cantidad}")

        # Obtener usuarios para enriquecer el backup txt (no se registra en log)
        try:
            users = conn.get_users()
            usuarios = {u.user_id: u.name for u in users}
        except Exception:
            usuarios = {}

        if cantidad == 0:
            _log(ciclo, nombre, "Inicializando",
                 "Equipo sin registraciones", advertencia=True)
        else:
            nuevas = _filtrar_nuevas_fichadas(attendances, ip, ciclo, nombre)
            if nuevas:
                filepath = _guardar_fichadas(nuevas, idadm, ip, nombre, usuarios)
                _log(ciclo, nombre, "Guardando", f"Fichadas guardadas en: {filepath}")
                _insertar_fichadas(nuevas, idadm, ip, ciclo, nombre)
                fichadas_count = len(nuevas)
            else:
                _log(ciclo, nombre, "Guardando",
                     f"Sin fichadas nuevas ({cantidad} registros en reloj, todos ya en DB)")

    except Exception as e:
        error = str(e)
        _log(ciclo, nombre, "Error", error, advertencia=True)
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

    return fichadas_count, error


def _run_ciclo(ciclo_id, reloj_ids=None):
    """
    Funcion que corre en un hilo separado.
    Lee todos los relojes indicados (o todos los activos si reloj_ids=None).
    """
    import django
    from .models import Reloj, CicloLectura

    ciclo = CicloLectura.objects.get(id=ciclo_id)

    if reloj_ids:
        relojes = Reloj.objects.filter(id__in=reloj_ids, activo=True)
    else:
        relojes = Reloj.objects.filter(activo=True)

    ciclo.relojes.set(relojes)

    total_fichadas = 0
    hubo_error = False

    for reloj in relojes:
        count, error = _procesar_reloj(reloj, ciclo)
        total_fichadas += count

        reloj.ultimo_ciclo = timezone.now()
        if error:
            reloj.ultimo_estado = Reloj.ESTADO_ERROR
            reloj.ultimo_error = error
            hubo_error = True
        else:
            reloj.ultimo_estado = Reloj.ESTADO_OK
            reloj.ultimo_error = ""
        reloj.save(update_fields=["ultimo_ciclo", "ultimo_estado", "ultimo_error"])

    ciclo.fin = timezone.now()
    ciclo.estado = CicloLectura.ESTADO_ERROR if hubo_error else CicloLectura.ESTADO_EXITOSO
    ciclo.total_fichadas = total_fichadas
    ciclo.save(update_fields=["fin", "estado", "total_fichadas"])

    _log(ciclo, "---", "---",
         f"Fin ciclo. {total_fichadas} fichadas totales.")


# Registro de hilos activos para evitar ejecuciones simultaneas
_lock = threading.Lock()
_hilo_activo = None


def hay_ciclo_en_progreso():
    """Devuelve True si hay un ciclo corriendo en este momento."""
    global _hilo_activo
    with _lock:
        return _hilo_activo is not None and _hilo_activo.is_alive()


def leer_registros_reloj(reloj_obj):
    """
    Lee los registros almacenados en el reloj sin modificarlo.
    Retorna (lista_de_dicts, None) o (None, mensaje_error).
    """
    PUNCH_LABELS = {1: "Entrada", 2: "Salida", 3: "Almuerzo", 4: "Regreso"}
    conn = None
    try:
        zk = ZK(reloj_obj.ip, port=reloj_obj.puerto, timeout=5,
                password=reloj_obj.password, force_udp=False, ommit_ping=False)
        conn = zk.connect()
        attendances = conn.get_attendance()
        try:
            users = conn.get_users()
            usuarios = {u.user_id: u.name for u in users}
        except Exception:
            usuarios = {}
        registros = [
            {
                "user_id": str(a.user_id).zfill(COL_IDPER),
                "nombre": usuarios.get(a.user_id, ""),
                "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "tipo": PUNCH_LABELS.get(punch_to_idtctrlper(a.punch), str(a.punch)),
            }
            for a in sorted(attendances, key=lambda x: x.timestamp, reverse=True)
        ]
        return registros, None
    except Exception as e:
        return None, str(e)
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


def ping_reloj(reloj_obj):
    """
    Verifica conectividad con el reloj sin realizar ningún cambio.
    Retorna (True, None) si responde, o (False, mensaje_error) si falla.
    """
    conn = None
    try:
        zk = ZK(reloj_obj.ip, port=reloj_obj.puerto, timeout=5,
                password=reloj_obj.password, force_udp=False, ommit_ping=False)
        conn = zk.connect()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


def reiniciar_reloj(reloj_obj):
    """
    Conecta al reloj y envía el comando de reinicio.
    Retorna (True, None) si tuvo éxito, o (False, mensaje_error) si falló.
    """
    conn = None
    try:
        zk = ZK(reloj_obj.ip, port=reloj_obj.puerto, timeout=5,
                password=reloj_obj.password, force_udp=False, ommit_ping=False)
        conn = zk.connect()
        conn.restart()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


def iniciar_ciclo(reloj_ids=None):
    """
    Inicia un ciclo de lectura en un hilo en segundo plano.
    Retorna (ciclo_id, error_str).
    Si ya hay un ciclo en progreso, retorna (None, mensaje).
    """
    global _hilo_activo

    with _lock:
        if _hilo_activo is not None and _hilo_activo.is_alive():
            return None, "Ya hay un ciclo de lectura en progreso"

        from .models import CicloLectura
        ciclo = CicloLectura.objects.create()

        hilo = threading.Thread(
            target=_run_ciclo,
            args=(ciclo.id, reloj_ids),
            daemon=True,
            name=f"ciclo-{ciclo.id}",
        )
        _hilo_activo = hilo
        hilo.start()

    return ciclo.id, None
