# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime

import psycopg2
import colorama
from colorama import Fore, Back, Style

colorama.init(autoreset=True)

CWD = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.dirname(CWD)
sys.path.append(ROOT_DIR)

FICHADAS_DIR = os.path.join(CWD, "fichadas")

# --- Configuracion base de datos ---
DB_CONFIG = {
    "host":     "192.168.0.150",
    "port":     6003,
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "postgres",
    "options":  "-c search_path=public",
}

from zk import ZK, const

# --- Configuracion de relojes ---
#RELOJES = [
#    {"nombre": "COB-MORA-USH", "ip": "179.62.73.126", "puerto": 4370, "password": 0,  "es_lector": False},
#    {"nombre": "PP4-USH",      "ip": "179.62.73.126", "puerto": 4370, "password": 0,  "es_lector": False},
#    {"nombre": "PP2-PLTA-USH", "ip": "118.118.69.217","puerto": 4370, "password": 0,  "es_lector": False},
#]
RELOJES = [
    {"nombre": "PRUEBAS-IT", "ip": "192.168.0.22", "puerto": 4370, "password": 1884, "idadm": 137, "es_lector": False},
]

# Mapeo de tipo de fichada ZK -> idtctrlper de base de datos
PUNCH_MAP = {
    0: 1,   # Check In      -> Entrada
    1: 2,   # Check Out     -> Salida
    4: 3,   # Overtime In   -> Almuerzo
    5: 4,   # Overtime Out  -> Regreso Almuerzo
}

def punch_to_idtctrlper(punch):
    return PUNCH_MAP.get(punch, 99)  # default -> Simple marca


COL_FECHA    = 19
COL_EQUIPO   = 16
COL_OPER     = 16
COL_DETALLE  = 55


def encabezado():
    sep = "-" * (COL_FECHA + COL_EQUIPO + COL_OPER + COL_DETALLE + 5)
    print(sep)
    print(
        f"{'Fecha':<{COL_FECHA}} "
        f"{'Equipo':<{COL_EQUIPO}} "
        f"{'Operacion':<{COL_OPER}} "
        f"{'Detalle':<{COL_DETALLE}}"
    )
    print(sep)


def log(equipo, operacion, detalle, advertencia=False):
    now = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
    linea = (
        f"{now:<{COL_FECHA}} "
        f"{equipo:<{COL_EQUIPO}} "
        f"{operacion:<{COL_OPER}} "
        f"{detalle:<{COL_DETALLE}}"
    )
    if advertencia:
        print(Back.YELLOW + Fore.BLACK + linea)
    else:
        print(linea)


COL_IDPER      = 11
COL_HORA       = 23
COL_IDADM      = 6
COL_IDTCTRLPER = 12
COL_IP         = 24

def print_fichadas(attendances, idadm, ip_reloj):
    sep = "-" * (COL_IDPER + COL_HORA + COL_IDADM + COL_IDTCTRLPER + COL_IP + 7)
    print(sep)
    print(
        f"{'idper':<{COL_IDPER}} "
        f"{'hora':<{COL_HORA}} "
        f"{'idadm':<{COL_IDADM}} "
        f"{'idtctrlper':<{COL_IDTCTRLPER}} "
        f"{'ip':<{COL_IP}}"
    )
    print(sep)
    for a in attendances:
        idper      = str(a.user_id).zfill(COL_IDPER)
        hora       = a.timestamp.strftime("%Y-%m-%d %H:%M:%S.000")
        idtctrlper = punch_to_idtctrlper(a.punch)
        print(
            f"{idper:<{COL_IDPER}} "
            f"{hora:<{COL_HORA}} "
            f"{idadm:<{COL_IDADM}} "
            f"{idtctrlper:<{COL_IDTCTRLPER}} "
            f"{ip_reloj:<{COL_IP}}"
        )
    print(sep)


def guardar_fichadas(attendances, idadm, ip_reloj, nombre_reloj):
    os.makedirs(FICHADAS_DIR, exist_ok=True)
    filepath = os.path.join(FICHADAS_DIR, f"{nombre_reloj}.txt")
    ordenadas = sorted(attendances, key=lambda a: a.timestamp, reverse=True)

    contenido_existente = ""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            contenido_existente = f.read()

    nuevas_lineas = f"# Lectura: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {len(ordenadas)} fichadas\n"
    for a in ordenadas:
        idper      = str(a.user_id).zfill(COL_IDPER)
        hora       = a.timestamp.strftime("%Y-%m-%d %H:%M:%S.000")
        idtctrlper = punch_to_idtctrlper(a.punch)
        nuevas_lineas += (
            f"{idper:<{COL_IDPER}} "
            f"{hora:<{COL_HORA}} "
            f"{idadm:<{COL_IDADM}} "
            f"{idtctrlper:<{COL_IDTCTRLPER}} "
            f"{ip_reloj:<{COL_IP}}\n"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(nuevas_lineas + contenido_existente)
    return filepath


def insertar_fichadas(attendances, idadm, ip_reloj, nombre):
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
    conn_db = psycopg2.connect(**DB_CONFIG)
    try:
        with conn_db:
            with conn_db.cursor() as cur:
                cur.executemany(SQL, registros)
        log(nombre, "Base de datos", f"Insertados {len(registros)} registros OK")
    finally:
        conn_db.close()


def procesar_reloj(reloj):
    nombre   = reloj["nombre"]
    ip       = reloj["ip"]
    puerto   = reloj["puerto"]
    password = reloj["password"]
    es_lector = reloj["es_lector"]

    log(nombre, "Comienzo", f"Mod: ZK - TFT - IP: {ip} - esLector: {es_lector}")

    conn = None
    try:
        zk = ZK(ip, port=puerto, timeout=5, password=password,
                force_udp=False, ommit_ping=False)

        log(nombre, "Conectando", "Conectando...")
        conn = zk.connect()
        log(nombre, "Conectando", "Conectado con exito")

        log(nombre, "Inicializando", "Leyendo registros...")
        attendances = conn.get_attendance()
        cantidad = len(attendances)
        log(nombre, "Inicializando", f"Cantidad de fichadas: {cantidad}")

        if cantidad == 0:
            log(nombre, "Inicializando", "Equipo sin registraciones", advertencia=True)
        else:
            idadm = reloj.get("idadm", 0)
            print_fichadas(attendances, idadm, ip)

            filepath = guardar_fichadas(attendances, idadm, ip, nombre)
            log(nombre, "Guardando", f"Fichadas guardadas en: {filepath}")

            insertar_fichadas(attendances, idadm, ip, nombre)

            log(nombre, "Limpiando", "Borrando registros del reloj...")
            conn.disable_device()
            conn.clear_attendance()
            conn.enable_device()
            log(nombre, "Limpiando", "Registros borrados con exito")

    except Exception as e:
        log(nombre, "Error", str(e), advertencia=True)
    finally:
        if conn:
            conn.disconnect()


def main():
    encabezado()
    for reloj in RELOJES:
        procesar_reloj(reloj)

    proxima = datetime.now().strftime("%H:%M:%S")
    log("---", "---", f"Fin ciclo lectura. Proxima ejecucion: {proxima}")


if __name__ == "__main__":
    main()
