"""Generación de una bitácora explicativa a partir de eventos de simulación."""

from __future__ import annotations

from src.engine import ResultadoSimulacion
from src.visual import icono_evento

_DESCRIPCIONES: dict[str, str] = {
    "ASIGNACION": "asignación",
    "REASIGNACION": "reasignación",
    "INICIO_PROCESO": "inicio de procesamiento",
    "FIN_TAREA": "tarea completada",
    "SOBRECARGA": "sobrecarga",
    "RECUPERACION": "recuperación de sobrecarga",
    "RECUPERACION_SERVIDOR": "recuperación del servidor",
    "CAIDA": "caída del servidor",
    "PENDIENTE_REASIGNACION": "trabajo pendiente por reasignar",
    "ESPERA": "tarea en espera",
    "FIN_ESPERA": "fin de espera",
    "DEGRADACION": "degradación de capacidad",
    "RESTAURACION": "restauración de capacidad",
}


def generar_bitacora(resultado: ResultadoSimulacion) -> list[str]:
    """Explica cronológicamente los eventos reales de una ejecución."""
    return [
        f"t={evento.tiempo} · {icono_evento(evento.tipo)} "
        f"{_DESCRIPCIONES.get(evento.tipo, evento.tipo.lower())}: {evento.detalle}"
        for evento in resultado.eventos
    ]
