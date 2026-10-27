"""
Módulo de configuración.

Lee los parámetros de simulación desde el archivo .env y los expone
como constantes tipadas con valores por defecto.

En sistemas distribuidos, la configuración centralizada permite
ajustar el comportamiento del sistema sin modificar el código fuente.
"""

import os
import logging
from src.parameters import ParametrosSimulacion
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


def crear_parametros_por_defecto() -> ParametrosSimulacion:
    """Construye parámetros iniciales desde `.env` o los valores predeterminados.

    Se eligen INTERVALO_LLEGADA = 2 y UMBRAL_SOBRECARGA = 12 para equilibrar
    la intensidad de carga con la capacidad disponible:

        duracion_media ≈ (1 + 10) / 2 = 5.5
        utilizacion_A ≈ 5.5 / (4 * 2) = 0.6875 ≈ 68.75%
        utilizacion_C ≈ 5.5 / (3 * 2) = 0.9167 ≈ 91.67%
        utilizacion_B ≈ 5.5 / (3.5 * 2) = 0.7857 ≈ 78.57%

    La idea es mantener el escenario A en el rango 60-70 % y acercar B/C a 80-90 %
    sin saturar permanentemente el sistema. El umbral de sobrecarga se fija en 12,
    que equivale aproximadamente a dos tareas promedio por servidor, suficiente para
    detectar congestión sin bloquear cada nodo indefinidamente.
    """
    parametros = ParametrosSimulacion(
        num_tareas=_leer_int("NUM_TAREAS", 100),
        num_servidores=_leer_int("NUM_SERVIDORES", 4),
        duracion_min=_leer_int("DURACION_MIN", 1),
        duracion_max=_leer_int("DURACION_MAX", 10),
        intervalo_llegada=_leer_int("INTERVALO_LLEGADA", 2),
        umbral_sobrecarga=_leer_float("UMBRAL_SOBRECARGA", 12.0),
        tarea_falla=_leer_int("TAREA_FALLA", 50),
        servidor_falla=_leer_int("SERVIDOR_FALLA", 2),
        servidor_lento=_leer_int("SERVIDOR_LENTO", 2),
        capacidad_reducida=_leer_float("CAPACIDAD_REDUCIDA", 0.5),
        semilla=_leer_int("SEMILLA", 42),
        repeticiones=_leer_int("REPETICIONES", 30),
    )
    parametros.validar()
    return parametros


PARAMETROS_POR_DEFECTO = crear_parametros_por_defecto()
