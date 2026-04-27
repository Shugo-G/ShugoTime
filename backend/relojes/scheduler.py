import atexit
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="America/Argentina/Buenos_Aires")
atexit.register(lambda: _scheduler.shutdown(wait=False) if _scheduler.running else None)

# Cron estándar: 0/7=dom, 1=lun ... 6=sáb
# APScheduler usa nombres: mon, tue, wed, thu, fri, sat, sun
_DOW = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def _normalizar_dow(dow):
    """
    Convierte el campo day_of_week de notación numérica cron estándar
    (0/7=domingo, 1=lunes) a nombres de día para APScheduler.
    Soporta: *, 1, 1-5, 1,3,5, */2
    Si ya contiene letras (mon, fri…) lo deja como está.
    """
    if any(c.isalpha() for c in dow) or dow == "*":
        return dow

    def _token(t):
        if "-" in t:
            a, b = t.split("-", 1)
            return f"{_DOW[int(a)]}-{_DOW[int(b)]}"
        if "/" in t:
            base, step = t.split("/", 1)
            return f"{'*' if base == '*' else _DOW[int(base)]}/{step}"
        return _DOW[int(t)]

    return ",".join(_token(t) for t in dow.split(","))


def _trigger_desde_cron(expresion):
    """Crea un CronTrigger correctamente desde una expresión cron de 5 campos."""
    minuto, hora, dia, mes, dow = expresion.split()
    return CronTrigger(
        minute=minuto,
        hour=hora,
        day=dia,
        month=mes,
        day_of_week=_normalizar_dow(dow),
        timezone="America/Argentina/Buenos_Aires",
    )


def _job_id(tarea_id):
    return f"tarea_{tarea_id}"


def _ejecutar_tarea(tarea_id):
    from relojes.models import TareaProgramada
    from relojes.zk_reader import iniciar_ciclo, hay_ciclo_en_progreso

    try:
        tarea = TareaProgramada.objects.get(id=tarea_id, activo=True)
    except TareaProgramada.DoesNotExist:
        return

    if hay_ciclo_en_progreso():
        logger.warning("Tarea '%s': ya hay un ciclo en progreso, se omite.", tarea.nombre)
        return

    reloj_ids = list(tarea.relojes.values_list("id", flat=True))
    ciclo_id, error = iniciar_ciclo(reloj_ids if reloj_ids else None)
    if error:
        logger.error("Tarea '%s': error al iniciar ciclo: %s", tarea.nombre, error)
    else:
        logger.info("Tarea '%s': ciclo #%s iniciado.", tarea.nombre, ciclo_id)


def agregar_o_actualizar(tarea):
    """Registra o reemplaza el job para una TareaProgramada."""
    job_id = _job_id(tarea.id)
    if not tarea.activo:
        _eliminar(job_id)
        return
    try:
        _scheduler.add_job(
            _ejecutar_tarea,
            _trigger_desde_cron(tarea.expresion_cron),
            id=job_id,
            args=[tarea.id],
            replace_existing=True,
            misfire_grace_time=60,
            coalesce=True,
        )
        logger.info("Job registrado: '%s' (%s)", tarea.nombre, tarea.expresion_cron)
    except Exception as e:
        logger.error("Error registrando job '%s': %s", tarea.nombre, e)


def eliminar(tarea_id):
    """Elimina el job de una TareaProgramada."""
    _eliminar(_job_id(tarea_id))


def _eliminar(job_id):
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        logger.info("Job eliminado: %s", job_id)


def start():
    """Carga las tareas activas de la DB e inicia el scheduler."""
    from relojes.models import TareaProgramada

    try:
        tareas = list(TareaProgramada.objects.filter(activo=True))
        for tarea in tareas:
            agregar_o_actualizar(tarea)
        _scheduler.start()
        logger.info("Scheduler iniciado con %d tarea(s) activa(s).", len(tareas))
    except Exception as e:
        logger.error("Error iniciando el scheduler: %s", e)
