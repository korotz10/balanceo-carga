"""Paleta de colores y utilidades visuales para el panel de simulación.

Centraliza los colores por estrategia y por estado de servidor para
mantener coherencia visual en todas las pestañas del dashboard.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colores por estrategia de asignación
# ---------------------------------------------------------------------------

COLOR_ESTRATEGIA: dict[str, str] = {
    "Round Robin": "#3B82F6",   # azul
    "Menor Carga": "#10B981",   # verde esmeralda
    "Aleatoria": "#F59E0B",     # ámbar
}

# ---------------------------------------------------------------------------
# Colores por estado de servidor
# ---------------------------------------------------------------------------

COLOR_ESTADO: dict[str, str] = {
    "ACTIVO": "#22C55E",        # verde
    "SOBRECARGADO": "#F59E0B",  # ámbar
    "CAIDO": "#EF4444",         # rojo
}

# Paletas base para figuras y componentes del panel.
TEMA_CLARO: dict[str, str] = {
    "fondo": "#FFFFFF",
    "superficie": "#F3F4F6",
    "texto": "#111827",
    "rejilla": "#D1D5DB",
}

TEMA_OSCURO: dict[str, str] = {
    "fondo": "#0F172A",
    "superficie": "#1E293B",
    "texto": "#E2E8F0",
    "rejilla": "#475569",
}

# ---------------------------------------------------------------------------
# Iconos por tipo de evento (para tablas y bitácora)
# ---------------------------------------------------------------------------

ICONO_EVENTO: dict[str, str] = {
    "ASIGNACION": "📥",
    "REASIGNACION": "🔄",
    "INICIO_PROCESO": "▶️",
    "FIN_TAREA": "✅",
    "SOBRECARGA": "⚠️",
    "RECUPERACION": "💚",
    "RECUPERACION_SERVIDOR": "🟢",
    "CAIDA": "🔴",
    "PENDIENTE_REASIGNACION": "📤",
    "ESPERA": "⏳",
    "FIN_ESPERA": "⏱️",
    "DEGRADACION": "📉",
    "RESTAURACION": "📈",
}

# ---------------------------------------------------------------------------
# Colores para Gantt (10 colores cíclicos para tareas)
# ---------------------------------------------------------------------------

COLORES_TAREAS: list[str] = [
    "#6366F1",  # índigo
    "#EC4899",  # rosa
    "#14B8A6",  # teal
    "#F97316",  # naranja
    "#8B5CF6",  # violeta
    "#06B6D4",  # cian
    "#EF4444",  # rojo
    "#84CC16",  # lima
    "#F59E0B",  # ámbar
    "#3B82F6",  # azul
]


def color_estrategia(nombre: str) -> str:
    """Devuelve el color asignado a una estrategia; gris si no existe."""
    return COLOR_ESTRATEGIA.get(nombre, "#6B7280")


def color_estado(estado: str) -> str:
    """Devuelve el color asignado a un estado de servidor; gris si no existe."""
    return COLOR_ESTADO.get(estado, "#6B7280")


def icono_evento(tipo: str) -> str:
    """Devuelve el icono correspondiente a un tipo de evento; punto si no existe."""
    return ICONO_EVENTO.get(tipo, "•")


def color_tarea(tarea_id: int) -> str:
    """Devuelve un color cíclico según el ID de la tarea."""
    return COLORES_TAREAS[tarea_id % len(COLORES_TAREAS)]
