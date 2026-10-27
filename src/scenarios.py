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
from collections.abc import Sequence
from src.models import Servidor, Tarea
from src.algorithms import (
    EstrategiaAsignacion, RoundRobin, MenorCarga, Aleatoria,
)
from src.engine import (
    ejecutar_simulacion, ConfiguracionFalla, ResultadoSimulacion,
)
from src.task_generator import generar_tareas
from src.parameters import ParametrosSimulacion

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
    parametros: ParametrosSimulacion,
) -> ResultadoSimulacion:
    """Escenario A: operación normal con servidores homogéneos."""
    servidores = crear_servidores_normales(parametros.num_servidores)
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=parametros.umbral_sobrecarga,
        nombre_escenario="A - Normal",
    )


def ejecutar_escenario_b(
    tareas: list[Tarea],
    estrategia: EstrategiaAsignacion,
    parametros: ParametrosSimulacion,
) -> ResultadoSimulacion:
    """Escenario B: un servidor lento con capacidad reducida."""
    servidores = crear_servidores_sobrecarga(
        n=parametros.num_servidores,
        servidor_lento=parametros.servidor_lento,
        capacidad_reducida=parametros.capacidad_reducida,
    )
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=parametros.umbral_sobrecarga,
        nombre_escenario="B - Sobrecarga",
    )


def ejecutar_escenario_c(
    tareas: list[Tarea],
    estrategia: EstrategiaAsignacion,
    parametros: ParametrosSimulacion,
) -> ResultadoSimulacion:
    """Escenario C: al dispararse la falla, cae el servidor con más trabajo pendiente.

    El ID de servidor configurado se usa como desempate para que el momento
    de falla produzca una cola relevante y permita observar las reasignaciones.
    """
    servidores = crear_servidores_normales(parametros.num_servidores)
    config_falla = ConfiguracionFalla(
        tarea_trigger=parametros.tarea_falla,
        servidor_id=parametros.servidor_falla,
        elegir_mas_cargado=True,
    )
    return ejecutar_simulacion(
        tareas=tareas,
        servidores=servidores,
        estrategia=estrategia,
        umbral_sobrecarga=parametros.umbral_sobrecarga,
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
    parametros: ParametrosSimulacion,
    escenarios_solicitados: Sequence[str] | None = None,
    estrategias_solicitadas: Sequence[str] | None = None,
) -> ResultadosPorCombinacion:
    """Ejecuta cada escenario y estrategia sobre los mismos conjuntos de tareas."""
    parametros.validar()

    escenarios = {
        "A - Normal": ejecutar_escenario_a,
        "B - Sobrecarga": ejecutar_escenario_b,
        "C - Falla": ejecutar_escenario_c,
    }
    estrategias = {
        "round_robin": lambda semilla: RoundRobin(),
        "menor_carga": lambda semilla: MenorCarga(),
        "aleatoria": lambda semilla: Aleatoria(semilla=semilla),
    }
    nombres_escenario = {
        "a": "A - Normal",
        "a - normal": "A - Normal",
        "normal": "A - Normal",
        "b": "B - Sobrecarga",
        "b - sobrecarga": "B - Sobrecarga",
        "sobrecarga": "B - Sobrecarga",
        "c": "C - Falla",
        "c - falla": "C - Falla",
        "falla": "C - Falla",
    }

    escenarios_elegidos = list(escenarios)
    if escenarios_solicitados:
        escenarios_elegidos = []
        escenarios_desconocidos: list[str] = []
        for clave in escenarios_solicitados:
            normalizada = clave.strip().casefold()
            nombre = nombres_escenario.get(normalizada)
            if nombre is None:
                escenarios_desconocidos.append(clave)
            elif nombre not in escenarios_elegidos:
                escenarios_elegidos.append(nombre)
        if escenarios_desconocidos:
            opciones = ", ".join(sorted(nombres_escenario))
            raise ValueError(
                f"Escenario(s) no reconocido(s): {escenarios_desconocidos}. "
                f"Opciones válidas: {opciones}"
            )

    estrategias_elegidas = (
        list(estrategias_solicitadas)
        if estrategias_solicitadas
        else list(estrategias)
    )

    desconocidos_estrategias = set(estrategias_elegidas) - set(estrategias)
    if desconocidos_estrategias:
        raise ValueError(
            f"Estrategia(s) no reconocida(s): {sorted(desconocidos_estrategias)}. "
            f"Opciones válidas: {sorted(estrategias)}"
        )

    resultados: ResultadosPorCombinacion = {}
    for nombre_escenario in escenarios_elegidos:
        for nombre_estrategia in estrategias_elegidas:
            resultados[(nombre_escenario, nombre_estrategia)] = []

    for indice in range(parametros.repeticiones):
        semilla_tareas = parametros.semilla + indice
        tareas = generar_tareas(
            cantidad=parametros.num_tareas,
            duracion_min=parametros.duracion_min,
            duracion_max=parametros.duracion_max,
            semilla=semilla_tareas,
            intervalo_llegada=parametros.intervalo_llegada,
        )
        for nombre_escenario in escenarios_elegidos:
            func_escenario = escenarios[nombre_escenario]
            for nombre_estrategia in estrategias_elegidas:
                semilla_estrategia = parametros.semilla + indice + (1_000 if nombre_estrategia == "aleatoria" else 0)
                estrategia = estrategias[nombre_estrategia](semilla_estrategia)
                resultado = func_escenario(
                    copy.deepcopy(tareas),
                    estrategia,
                    parametros,
                )
                resultados[(nombre_escenario, nombre_estrategia)].append(resultado)

    for clave, ejecuciones in resultados.items():
        if ejecuciones:
            logger.info(
                "%s / %s (%s corridas): makespan promedio=%.1f",
                clave[0],
                clave[1],
                len(ejecuciones),
                sum(resultado.makespan for resultado in ejecuciones) / len(ejecuciones),
            )

    return resultados
