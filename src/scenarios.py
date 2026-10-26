"""
Escenarios de simulación para comparar estrategias de balanceo de carga.

Define tres escenarios que ilustran situaciones típicas en sistemas
distribuidos:

- Escenario A (Normal): todos los servidores funcionan correctamente
  con la misma capacidad. Es la línea base para comparar.

- Escenario B (Sobrecarga): un servidor tiene capacidad reducida,
  lo que causa que se sobrecargue. Permite observar cómo reacciona
  cada estrategia ante recursos heterogéneos.

- Escenario C (Falla): un servidor cae tras cierto número de
  asignaciones. Las tareas pendientes se reasignan. Permite evaluar
  la tolerancia a fallos de cada estrategia.
"""

import copy
import logging
from src.models import Servidor, Tarea
from src.algorithms import (
    EstrategiaAsignacion, RoundRobin, MenorCarga, Aleatoria, crear_estrategia,
)
from src.engine import (
    ejecutar_simulacion, ConfiguracionFalla, ResultadoSimulacion,
)
from src.task_generator import generar_tareas
from src import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Creación de servidores para cada escenario
# ---------------------------------------------------------------------------

def crear_servidores_normales(n: int = 4) -> list[Servidor]:
    """Crea n servidores idénticos con capacidad 1.0 (Escenario A y C)."""
    return [Servidor(id=i, capacidad=1.0) for i in range(n)]


def crear_servidores_sobrecarga(
    n: int = 4,
    servidor_lento: int = 2,
    capacidad_reducida: float = 0.5,
) -> list[Servidor]:
    """
    Crea n servidores donde uno tiene capacidad reducida (Escenario B).

    El servidor con capacidad reducida simula un nodo con menos recursos
    (por ejemplo, menos CPU o memoria). Esto permite observar cómo
    las distintas estrategias manejan la heterogeneidad.

    Args:
        n: Número de servidores.
        servidor_lento: ID del servidor con capacidad reducida.
        capacidad_reducida: Capacidad del servidor lento (0 < valor < 1).
    """
    servidores = [Servidor(id=i, capacidad=1.0) for i in range(n)]
    if 0 <= servidor_lento < n:
        servidores[servidor_lento].capacidad = capacidad_reducida
    return servidores


# ---------------------------------------------------------------------------
# Ejecución de escenarios individuales
# ---------------------------------------------------------------------------

def ejecutar_escenario_a(
    tareas: list[Tarea],
    estrategia: EstrategiaAsignacion,
    umbral: float,
) -> ResultadoSimulacion:
    """
    Escenario A — Operación normal.

    4 servidores iguales, sin fallas ni sobrecarga artificial.
    Es la línea base para comparar las estrategias.
    """
    servidores = crear_servidores_normales(config.NUM_SERVIDORES)
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=umbral,
        nombre_escenario="A - Normal",
    )


def ejecutar_escenario_b(
    tareas: list[Tarea],
    estrategia: EstrategiaAsignacion,
    umbral: float,
) -> ResultadoSimulacion:
    """
    Escenario B — Sobrecarga por capacidad reducida.

    Un servidor tiene capacidad reducida (por defecto 0.5), lo que
    simula un nodo más lento. El mecanismo de sobrecarga se activa:
    cuando la carga del servidor excede el umbral, deja de recibir
    tareas hasta que su cola baje.

    Observaciones esperadas:
    - Round Robin: envía tareas al servidor lento por turno, causando
      sobrecarga recurrente.
    - Menor Carga: evita naturalmente el servidor lento porque su
      carga estimada es mayor.
    - Aleatoria: envía ~25% de tareas al servidor lento, causando
      sobrecarga intermitente.
    """
    servidores = crear_servidores_sobrecarga(
        n=config.NUM_SERVIDORES,
        servidor_lento=config.SERVIDOR_FALLA,
        capacidad_reducida=config.CAPACIDAD_REDUCIDA,
    )
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=umbral,
        nombre_escenario="B - Sobrecarga",
    )


def ejecutar_escenario_c(
    tareas: list[Tarea],
    estrategia: EstrategiaAsignacion,
    umbral: float,
) -> ResultadoSimulacion:
    """
    Escenario C — Falla de un servidor.

    Después de asignar TAREA_FALLA tareas, el servidor SERVIDOR_FALLA
    pasa a estado CAIDO. Sus tareas pendientes (con su trabajo restante,
    no la duración original) se reasignan a los servidores activos.

    Verificaciones clave:
    - Ninguna tarea se pierde: la suma de completadas debe ser igual
      al total de tareas.
    - Las tareas parcialmente procesadas conservan su progreso.
    """
    servidores = crear_servidores_normales(config.NUM_SERVIDORES)
    config_falla = ConfiguracionFalla(
        tarea_trigger=config.TAREA_FALLA,
        servidor_id=config.SERVIDOR_FALLA,
    )
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=umbral,
        config_falla=config_falla,
        nombre_escenario="C - Falla",
    )


# ---------------------------------------------------------------------------
# Ejecución completa de todos los escenarios y estrategias
# ---------------------------------------------------------------------------

# Tipo para los resultados: clave = (escenario, estrategia)
# El valor es un ResultadoSimulacion o una lista de ellos (para aleatoria).
ResultadosPorCombinacion = dict[
    tuple[str, str],
    ResultadoSimulacion | list[ResultadoSimulacion]
]


def ejecutar_todos(
    semilla: int | None = None,
    repeticiones_aleatoria: int | None = None,
) -> ResultadosPorCombinacion:
    """
    Ejecuta todas las combinaciones de escenarios y estrategias.

    Para las estrategias deterministas (Round Robin, Menor Carga),
    se ejecuta una sola vez con la semilla de tareas configurada.

    Para la estrategia Aleatoria, se ejecuta REPETICIONES_ALEATORIA
    veces con semillas distintas (semilla_base + i) y se guarda
    la lista completa de resultados para calcular promedio y
    desviación estándar.

    Returns:
        Diccionario con clave (nombre_escenario, nombre_estrategia)
        y valor ResultadoSimulacion o list[ResultadoSimulacion].
    """
    semilla = config.SEMILLA if semilla is None else semilla
    repeticiones = (
        config.REPETICIONES_ALEATORIA
        if repeticiones_aleatoria is None
        else repeticiones_aleatoria
    )
    if repeticiones <= 0:
        raise ValueError("repeticiones_aleatoria debe ser mayor que 0")
    umbral = config.UMBRAL_SOBRECARGA

    # Generar las tareas una sola vez (misma semilla para todas las estrategias)
    tareas_base = generar_tareas(
        cantidad=config.NUM_TAREAS,
        duracion_min=config.DURACION_MIN,
        duracion_max=config.DURACION_MAX,
        semilla=semilla,
        intervalo_llegada=config.INTERVALO_LLEGADA,
    )

    # Funciones de escenario
    escenarios = {
        "A - Normal": ejecutar_escenario_a,
        "B - Sobrecarga": ejecutar_escenario_b,
        "C - Falla": ejecutar_escenario_c,
    }

    resultados: ResultadosPorCombinacion = {}

    for nombre_escenario, func_escenario in escenarios.items():
        logger.info(f"{'='*60}")
        logger.info(f"Escenario: {nombre_escenario}")
        logger.info(f"{'='*60}")

        # ── Estrategias deterministas ──
        for nombre_est in ["round_robin", "menor_carga"]:
            estrategia = crear_estrategia(nombre_est, semilla=semilla)
            # Copiar tareas para que cada ejecución sea independiente
            tareas_copia = copy.deepcopy(tareas_base)
            resultado = func_escenario(tareas_copia, estrategia, umbral)
            clave = (nombre_escenario, resultado.nombre_estrategia)
            resultados[clave] = resultado
            logger.info(
                f"  {resultado.nombre_estrategia}: "
                f"makespan={resultado.makespan}, "
                f"completadas={len(resultado.registros)}"
            )

        # ── Estrategia aleatoria: múltiples ejecuciones ──
        resultados_aleatoria: list[ResultadoSimulacion] = []
        for i in range(repeticiones):
            semilla_i = semilla + i
            estrategia = Aleatoria(semilla=semilla_i)
            tareas_copia = copy.deepcopy(tareas_base)
            resultado = func_escenario(tareas_copia, estrategia, umbral)
            resultados_aleatoria.append(resultado)

        clave = (nombre_escenario, "Aleatoria")
        resultados[clave] = resultados_aleatoria
        makespans = [r.makespan for r in resultados_aleatoria]
        promedio = sum(makespans) / len(makespans)
        logger.info(
            f"  Aleatoria ({repeticiones} ejecuciones): "
            f"makespan promedio={promedio:.1f}"
        )

    return resultados
