"""
Módulo de configuración.

Lee los parámetros de simulación desde el archivo .env y los expone
como constantes tipadas con valores por defecto.

En sistemas distribuidos, la configuración centralizada permite
ajustar el comportamiento del sistema sin modificar el código fuente.
"""

import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env (si existe)
load_dotenv()


def _leer_int(nombre: str, valor_defecto: int) -> int:
    """Lee una variable de entorno como entero, con valor por defecto."""
    valor = os.getenv(nombre)
    if valor is None:
        return valor_defecto
    try:
        return int(valor)
    except ValueError:
        logger.warning(
            f"Variable '{nombre}' tiene valor inválido '{valor}'. "
            f"Usando valor por defecto: {valor_defecto}"
        )
        return valor_defecto


def _leer_float(nombre: str, valor_defecto: float) -> float:
    """Lee una variable de entorno como flotante, con valor por defecto."""
    valor = os.getenv(nombre)
    if valor is None:
        return valor_defecto
    try:
        return float(valor)
    except ValueError:
        logger.warning(
            f"Variable '{nombre}' tiene valor inválido '{valor}'. "
            f"Usando valor por defecto: {valor_defecto}"
        )
        return valor_defecto


# --- Parámetros de la simulación ---
NUM_TAREAS: int = _leer_int("NUM_TAREAS", 100)
NUM_SERVIDORES: int = _leer_int("NUM_SERVIDORES", 4)
DURACION_MIN: int = _leer_int("DURACION_MIN", 1)
DURACION_MAX: int = _leer_int("DURACION_MAX", 10)
SEMILLA: int = _leer_int("SEMILLA", 42)
INTERVALO_LLEGADA: int = _leer_int("INTERVALO_LLEGADA", 2)
UMBRAL_SOBRECARGA: float = _leer_float("UMBRAL_SOBRECARGA", 15.0)
TAREA_FALLA: int = _leer_int("TAREA_FALLA", 50)
SERVIDOR_FALLA: int = _leer_int("SERVIDOR_FALLA", 2)
CAPACIDAD_REDUCIDA: float = _leer_float("CAPACIDAD_REDUCIDA", 0.5)
REPETICIONES_ALEATORIA: int = _leer_int("REPETICIONES_ALEATORIA", 30)


def validar_configuracion() -> None:
    """Valida que los parámetros de configuración sean coherentes."""
    errores: list[str] = []
    if NUM_TAREAS <= 0:
        errores.append("NUM_TAREAS debe ser mayor que 0")
    if NUM_SERVIDORES <= 0:
        errores.append("NUM_SERVIDORES debe ser mayor que 0")
    if DURACION_MIN <= 0:
        errores.append("DURACION_MIN debe ser mayor que 0")
    if DURACION_MAX < DURACION_MIN:
        errores.append("DURACION_MAX debe ser >= DURACION_MIN")
    if INTERVALO_LLEGADA <= 0:
        errores.append("INTERVALO_LLEGADA debe ser mayor que 0")
    if UMBRAL_SOBRECARGA <= 0:
        errores.append("UMBRAL_SOBRECARGA debe ser mayor que 0")
    if CAPACIDAD_REDUCIDA <= 0 or CAPACIDAD_REDUCIDA >= 1.0:
        errores.append("CAPACIDAD_REDUCIDA debe estar entre 0 (exclusivo) y 1 (exclusivo)")
    if REPETICIONES_ALEATORIA <= 0:
        errores.append("REPETICIONES_ALEATORIA debe ser mayor que 0")
    if SERVIDOR_FALLA < 0 or SERVIDOR_FALLA >= NUM_SERVIDORES:
        errores.append(f"SERVIDOR_FALLA debe estar entre 0 y {NUM_SERVIDORES - 1}")
    if TAREA_FALLA <= 0 or TAREA_FALLA > NUM_TAREAS:
        errores.append(f"TAREA_FALLA debe estar entre 1 y {NUM_TAREAS}")

    if errores:
        mensaje = "Errores de configuración:\n" + "\n".join(f"  - {e}" for e in errores)
        raise ValueError(mensaje)
