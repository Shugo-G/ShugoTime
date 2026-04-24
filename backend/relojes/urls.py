from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RelojViewSet, CicloLecturaViewSet, LogEntryViewSet, EstadoView, FichadasView, TareaProgramadaViewSet

router = DefaultRouter()
router.register(r"relojes",   RelojViewSet,           basename="reloj")
router.register(r"ciclos",    CicloLecturaViewSet,    basename="ciclo")
router.register(r"logs",      LogEntryViewSet,        basename="log")
router.register(r"estado",    EstadoView,             basename="estado")
router.register(r"fichadas",  FichadasView,           basename="fichadas")
router.register(r"tareas",    TareaProgramadaViewSet, basename="tarea")

urlpatterns = [
    path("", include(router.urls)),
]
