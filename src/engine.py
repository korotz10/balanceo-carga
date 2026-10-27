"""
Motor de simulación de balanceo de carga con reloj simulado.

Simula la asignación y procesamiento de tareas en un sistema distribuido
con múltiples servidores. Usa un reloj discreto (sin time.sleep real)
que avanza tick a tick.

FLUJO DE LA SIMULACIÓN (cada tick del reloj):
1. Se recogen las tareas que llegan en este instante.
2. El ASIGNADOR (algoritmo de balanceo) elige a qué servidor va cada tarea.
3. Cada servidor PLANIFICA su cola en orden FIFO y procesa trabajo
   según su capacidad.
4. Se registran eventos para análisis posterior.

DIFERENCIA CLAVE:
- ASIGNACIÓN: decide A QUÉ servidor va la tarea (balanceo de carga).
  Esto lo hace el módulo algorithms.py.
- PLANIFICACIÓN: decide EN QUÉ ORDEN el servidor procesa sus tareas (FIFO).
  Esto lo gestiona la cola de cada Servidor en models.py.

El motor es independiente de la estrategia de asignación: recibe cualquier
objeto que implemente EstrategiaAsignacion.
"""

import copy
import logging
from dataclasses import dataclass, field

from src.models import Tarea, Servidor, EstadoServidor
from src.algorithms import EstrategiaAsignacion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estructuras de datos para registrar la simulación
# ---------------------------------------------------------------------------

@dataclass
class Evento:
    """
    Registro de un evento ocurrido durante la simulación.

    Los eventos permiten reconstruir lo que sucedió paso a paso,
    útil para depuración, análisis y generación de logs.

    Tipos de evento:
    - ASIGNACION: tarea asignada a un servidor.
    - INICIO_PROCESO: un servidor empieza a procesar una tarea.
    - FIN_TAREA: un servidor completa una tarea.
    - SOBRECARGA: un servidor excede el umbral de carga.
    - RECUPERACION: un servidor baja del umbral y vuelve a ACTIVO.
    - CAIDA: un servidor falla (escenario C).
    - REASIGNACION: tarea movida de un servidor caído a la cola de espera.
    - ESPERA: tarea no pudo ser asignada (todos los servidores ocupados).
    """
    tiempo: int
    tipo: str
    tarea_id: int
    servidor_id: int
    detalle: str


@dataclass
class RegistroTarea:
    """
    Registro completo del procesamiento de una tarea.
    Contiene toda la información temporal necesaria para calcular métricas.

    Attributes:
        tarea_id: Identificador de la tarea.
        duracion: Duración original de la tarea.
        tiempo_llegada: Cuándo llegó la tarea al sistema.
        servidor_id: Servidor que completó la tarea.
        tiempo_asignacion: Cuándo fue asignada al servidor final.
        tiempo_inicio_proceso: Cuándo empezó a ser procesada (frente de la cola).
        tiempo_fin: Cuándo se completó.
        reasignada: True si la tarea fue reasignada tras la caída de un servidor.
    """
    tarea_id: int
    duracion: int
    tiempo_llegada: int
    servidor_id: int
    tiempo_asignacion: int
    tiempo_inicio_proceso: int
    tiempo_fin: int
    reasignada: bool = False
    tiempo_espera_disponibilidad: int = 0


@dataclass
class ConfiguracionFalla:
    """
    Configuración para simular la caída de un servidor (Escenario C).

    Attributes:
        tarea_trigger: Número de tareas asignadas tras el cual ocurre la falla.
        servidor_id: ID del servidor que falla.
    """
    tarea_trigger: int
    servidor_id: int


@dataclass
class ResultadoSimulacion:
    """
    Resultado completo de una ejecución de la simulación.

    Contiene todos los datos necesarios para calcular métricas
    y generar reportes.
    """
    eventos: list[Evento]
    registros: list[RegistroTarea]
    servidores: list[Servidor]        # Estado final de los servidores (copia)
    makespan: int                      # Tiempo del último evento FIN_TAREA
    nombre_estrategia: str
    nombre_escenario: str
    tareas_reasignadas: int = 0


# ---------------------------------------------------------------------------
# Motor de simulación
# ---------------------------------------------------------------------------

def ejecutar_simulacion(
    tareas: list[Tarea],
    servidores: list[Servidor],
    estrategia: EstrategiaAsignacion,
    umbral_sobrecarga: float = 15.0,
    config_falla: ConfiguracionFalla | None = None,
    nombre_escenario: str = "",
) -> ResultadoSimulacion:
    """Ejecuta una corrida de la simulación con reloj discreto."""
    eventos: list[Evento] = []
    registros: list[RegistroTarea] = []
    pendientes = sorted(list(tareas), key=lambda tarea: tarea.tiempo_llegada)
    en_espera: list[Tarea] = []
    trabajo_restante_override: dict[int, float] = {}
    inicio_proceso: dict[int, int] = {}
    asignacion_info: dict[int, tuple[int, int, bool]] = {}
    inicio_espera: dict[int, int] = {}
    espera_total: dict[int, int] = {}
    total_asignadas = 0
    falla_ejecutada = False
    reloj = 0

    nombre_estrategia = estrategia.nombre

    while pendientes or en_espera or any(
        servidor.cola for servidor in servidores if servidor.estado != EstadoServidor.CAIDO
    ):
        if (pendientes or en_espera) and not any(
            servidor.estado != EstadoServidor.CAIDO for servidor in servidores
        ):
            raise RuntimeError(
                "La simulación no puede continuar: no quedan servidores disponibles "
                "y hay tareas pendientes."
            )

        nuevas: list[Tarea] = []
        while pendientes and pendientes[0].tiempo_llegada <= reloj:
            nuevas.append(pendientes.pop(0))

        por_asignar = en_espera + nuevas
        en_espera = []

        for tarea in por_asignar:
            disponibles = [servidor for servidor in servidores if servidor.esta_disponible()]
            if not disponibles:
                en_espera.append(tarea)
                if tarea.id not in inicio_espera:
                    inicio_espera[tarea.id] = reloj
                    eventos.append(
                        Evento(
                            tiempo=reloj,
                            tipo="ESPERA",
                            tarea_id=tarea.id,
                            servidor_id=-1,
                            detalle=(
                                f"Tarea {tarea.id} espera porque no hay servidores disponibles"
                            ),
                        )
                    )
                continue

            if tarea.id in inicio_espera:
                espera = reloj - inicio_espera.pop(tarea.id)
                espera_total[tarea.id] = espera_total.get(tarea.id, 0) + espera
                eventos.append(
                    Evento(
                        tiempo=reloj,
                        tipo="FIN_ESPERA",
                        tarea_id=tarea.id,
                        servidor_id=-1,
                        detalle=(
                            f"Tarea {tarea.id} salió de la cola de espera tras {espera} ticks"
                        ),
                    )
                )

            servidor = estrategia.asignar(tarea, disponibles)
            if tarea.id in trabajo_restante_override:
                restante = trabajo_restante_override.pop(tarea.id)
                servidor.cola.append((tarea, restante))
            else:
                servidor.agregar_tarea(tarea)

            total_asignadas += 1
            es_reasignada = tarea.id in asignacion_info
            asignacion_info[tarea.id] = (servidor.id, reloj, es_reasignada)

            if len(servidor.cola) == 1:
                inicio_proceso[tarea.id] = reloj

            eventos.append(
                Evento(
                    tiempo=reloj,
                    tipo="REASIGNACION" if es_reasignada else "ASIGNACION",
                    tarea_id=tarea.id,
                    servidor_id=servidor.id,
                    detalle=(
                        f"Tarea {tarea.id} -> Servidor {servidor.id} "
                        f"(carga={servidor.carga:.1f})"
                    ),
                )
            )

            if servidor.carga > umbral_sobrecarga and servidor.estado == EstadoServidor.ACTIVO:
                servidor.estado = EstadoServidor.SOBRECARGADO
                eventos.append(
                    Evento(
                        tiempo=reloj,
                        tipo="SOBRECARGA",
                        tarea_id=tarea.id,
                        servidor_id=servidor.id,
                        detalle=(
                            f"Servidor {servidor.id} SOBRECARGADO "
                            f"(carga={servidor.carga:.1f} > umbral={umbral_sobrecarga})"
                        ),
                    )
                )

            if (
                config_falla
                and not falla_ejecutada
                and total_asignadas >= config_falla.tarea_trigger
            ):
                falla_ejecutada = True
                srv_falla = next(
                    (servidor_actual for servidor_actual in servidores if servidor_actual.id == config_falla.servidor_id),
                    None,
                )
                if srv_falla and srv_falla.estado != EstadoServidor.CAIDO:
                    srv_falla.estado = EstadoServidor.CAIDO
                    eventos.append(
                        Evento(
                            tiempo=reloj,
                            tipo="CAIDA",
                            tarea_id=-1,
                            servidor_id=srv_falla.id,
                            detalle=(
                                f"Servidor {srv_falla.id} cayó tras asignar la tarea #{total_asignadas}"
                            ),
                        )
                    )
                    for tarea_pendiente, trabajo_restante in list(srv_falla.cola):
                        srv_falla.cola.remove((tarea_pendiente, trabajo_restante))
                        trabajo_restante_override[tarea_pendiente.id] = trabajo_restante
                        en_espera.append(tarea_pendiente)
                        eventos.append(
                            Evento(
                                tiempo=reloj,
                                tipo="PENDIENTE_REASIGNACION",
                                tarea_id=tarea_pendiente.id,
                                servidor_id=srv_falla.id,
                                detalle=(
                                    f"Tarea {tarea_pendiente.id} reasignada con {trabajo_restante:.1f} "
                                    "unidades restantes"
                                ),
                            )
                        )
                    srv_falla.cola.clear()

        for servidor in servidores:
            if servidor.estado == EstadoServidor.CAIDO or not servidor.cola:
                continue
            tarea_actual, trabajo_restante = servidor.cola[0]
            if tarea_actual.id not in inicio_proceso:
                inicio_proceso[tarea_actual.id] = reloj
            nuevo_restante = trabajo_restante - servidor.capacidad
            if nuevo_restante <= 1e-9:
                servidor.cola.pop(0)
                servidor.tareas_completadas.append(tarea_actual.id)
                _, tiempo_asignacion, reasignada = asignacion_info.get(
                    tarea_actual.id, (servidor.id, 0, False)
                )
                registros.append(
                    RegistroTarea(
                        tarea_id=tarea_actual.id,
                        duracion=tarea_actual.duracion,
                        tiempo_llegada=tarea_actual.tiempo_llegada,
                        servidor_id=servidor.id,
                        tiempo_asignacion=tiempo_asignacion,
                        tiempo_inicio_proceso=inicio_proceso.get(tarea_actual.id, 0),
                        tiempo_fin=reloj + 1,
                        reasignada=reasignada,
                        tiempo_espera_disponibilidad=espera_total.get(tarea_actual.id, 0),
                    )
                )
                eventos.append(
                    Evento(
                        tiempo=reloj + 1,
                        tipo="FIN_TAREA",
                        tarea_id=tarea_actual.id,
                        servidor_id=servidor.id,
                        detalle=(
                            f"Tarea {tarea_actual.id} completada en Servidor {servidor.id}"
                        ),
                    )
                )
                if servidor.cola:
                    siguiente = servidor.cola[0][0]
                    if siguiente.id not in inicio_proceso:
                        inicio_proceso[siguiente.id] = reloj + 1
            else:
                servidor.cola[0] = (tarea_actual, nuevo_restante)

        for servidor in servidores:
            if (
                servidor.estado == EstadoServidor.SOBRECARGADO
                and servidor.carga <= umbral_sobrecarga
            ):
                servidor.estado = EstadoServidor.ACTIVO
                eventos.append(
                    Evento(
                        tiempo=reloj,
                        tipo="RECUPERACION",
                        tarea_id=-1,
                        servidor_id=servidor.id,
                        detalle=(
                            f"Servidor {servidor.id} recuperado (carga={servidor.carga:.1f})"
                        ),
                    )
                )

        reloj += 1
        if reloj > 100_000:
            raise RuntimeError(
                "La simulación excedió el límite de 100,000 ticks; "
                "no se generará un resultado incompleto."
            )

    makespan = max((registro.tiempo_fin for registro in registros), default=0)
    tareas_reasignadas = sum(1 for registro in registros if registro.reasignada)

    return ResultadoSimulacion(
        eventos=eventos,
        registros=registros,
        servidores=copy.deepcopy(servidores),
        makespan=makespan,
        nombre_estrategia=nombre_estrategia,
        nombre_escenario=nombre_escenario,
        tareas_reasignadas=tareas_reasignadas,
    )


def _ejecutar_falla_servidor(
    servidor: Servidor,
    reloj: int,
    total_asignadas: int,
    en_espera: list[Tarea],
    trabajo_restante_override: dict[int, float],
    inicio_proceso: dict[int, int],
    eventos: list[Evento],
) -> None:
    """
    Simula la caída de un servidor: lo marca como CAIDO,
    extrae sus tareas pendientes y las pone en la cola de espera
    para ser reasignadas a servidores activos.

    Las tareas parcialmente procesadas conservan su trabajo restante
    (no reinician desde cero). Las tareas ya completadas no se pierden.
    """
    servidor.estado = EstadoServidor.CAIDO
    eventos.append(Evento(
        tiempo=reloj,
        tipo="CAIDA",
        tarea_id=-1,
        servidor_id=servidor.id,
        detalle=(
            f"Servidor {servidor.id} CAIDO tras asignar tarea "
            f"#{total_asignadas}. Tareas pendientes: {len(servidor.cola)}"
        ),
    ))
    logger.info(
        f"[t={reloj}] ¡FALLA! Servidor {servidor.id} CAIDO. "
        f"Tareas pendientes en su cola: {len(servidor.cola)}"
    )

    # Reasignar tareas pendientes del servidor caído
    for tarea, restante in servidor.cola:
        trabajo_restante_override[tarea.id] = restante
        inicio_proceso.pop(tarea.id, None)  # Limpiar inicio anterior
        en_espera.append(tarea)
        eventos.append(Evento(
            tiempo=reloj,
            tipo="PENDIENTE_REASIGNACION",
            tarea_id=tarea.id,
            servidor_id=servidor.id,
            detalle=(
                f"Tarea {tarea.id} (restante={restante:.1f}) pendiente "
                f"de reasignación desde Servidor {servidor.id}"
            ),
        ))

    servidor.cola.clear()
