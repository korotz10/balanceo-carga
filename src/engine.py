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
    """
    Ejecuta la simulación completa de asignación y procesamiento de tareas.

    El motor avanza un reloj discreto tick a tick. En cada tick:
    1. Se asignan las tareas que han llegado (y las que esperaban).
    2. Cada servidor activo procesa trabajo según su capacidad.
    3. Se verifican cambios de estado (sobrecarga, recuperación).

    La simulación termina cuando todas las tareas han sido procesadas
    y no quedan tareas pendientes de llegar ni en espera.

    Args:
        tareas: Lista de tareas a procesar (con tiempos de llegada).
        servidores: Lista de servidores disponibles.
        estrategia: Estrategia de asignación a utilizar.
        umbral_sobrecarga: Carga máxima antes de marcar como SOBRECARGADO.
        config_falla: Configuración de falla de servidor (opcional).
        nombre_escenario: Nombre del escenario para el registro.

    Returns:
        ResultadoSimulacion con todos los eventos, registros y métricas.
    """
    # --- Inicialización ---
    eventos: list[Evento] = []
    registros: list[RegistroTarea] = []

    # Tareas pendientes de llegar, ordenadas por tiempo de llegada
    pendientes = sorted(list(tareas), key=lambda t: t.tiempo_llegada)

    # Tareas que llegaron pero no pudieron ser asignadas
    en_espera: list[Tarea] = []

    # Trabajo restante para tareas reasignadas (tarea_id -> trabajo_restante)
    # Cuando un servidor cae, sus tareas parcialmente procesadas conservan
    # el trabajo restante en lugar de reiniciar desde cero.
    trabajo_restante_override: dict[int, float] = {}

    # Cuándo empieza a procesarse cada tarea (tarea_id -> tick)
    inicio_proceso: dict[int, int] = {}

    # Info de asignación: tarea_id -> (servidor_id, tiempo_asignacion, reasignada)
    asignacion_info: dict[int, tuple[int, int, bool]] = {}

    total_asignadas = 0
    tareas_reasignadas_count = 0
    falla_ejecutada = False
    reloj = 0

    nombre_estrategia = estrategia.nombre

    logger.info(
        f"Iniciando simulación: escenario='{nombre_escenario}', "
        f"estrategia='{nombre_estrategia}', "
        f"tareas={len(tareas)}, servidores={len(servidores)}"
    )

    # --- Bucle principal de simulación ---
    # Continúa mientras haya tareas por llegar, tareas en espera,
    # o servidores con trabajo pendiente.
    while (pendientes or en_espera or
           any(s.cola for s in servidores if s.estado != EstadoServidor.CAIDO)):
        if (en_espera or pendientes) and not any(
            servidor.estado != EstadoServidor.CAIDO for servidor in servidores
        ):
            raise RuntimeError(
                "La simulación no puede continuar: no quedan servidores "
                "disponibles y hay tareas pendientes."
            )

        # ── Paso 1: Recoger tareas que llegan en este tick ──
        nuevas: list[Tarea] = []
        while pendientes and pendientes[0].tiempo_llegada <= reloj:
            nuevas.append(pendientes.pop(0))

        # Combinar con tareas en espera (las que no pudieron asignarse antes)
        por_asignar = en_espera + nuevas
        en_espera = []

        # ── Paso 2: Asignar tareas a servidores ──
        for tarea in por_asignar:
            disponibles = [s for s in servidores if s.esta_disponible()]

            if disponibles:
                servidor = estrategia.asignar(tarea, disponibles)

                # Si la tarea fue reasignada, usar el trabajo restante
                # en vez de la duración original (no pierde progreso).
                if tarea.id in trabajo_restante_override:
                    restante = trabajo_restante_override.pop(tarea.id)
                    servidor.cola.append((tarea, restante))
                    servidor.total_tareas_recibidas += 1
                else:
                    servidor.agregar_tarea(tarea)

                total_asignadas += 1

                # Si la cola tenía solo esta tarea, empieza a procesarse ahora
                if len(servidor.cola) == 1:
                    inicio_proceso[tarea.id] = reloj

                # Registrar info de asignación
                es_reasignada = tarea.id in asignacion_info
                asignacion_info[tarea.id] = (servidor.id, reloj, es_reasignada)

                eventos.append(Evento(
                    tiempo=reloj,
                    tipo="REASIGNACION" if es_reasignada else "ASIGNACION",
                    tarea_id=tarea.id,
                    servidor_id=servidor.id,
                    detalle=(
                        f"Tarea {tarea.id} (dur={tarea.duracion}) → "
                        f"Servidor {servidor.id} (carga={servidor.carga:.1f})"
                    ),
                ))

                # Verificar sobrecarga tras agregar la tarea
                if (servidor.carga > umbral_sobrecarga and
                        servidor.estado == EstadoServidor.ACTIVO):
                    servidor.estado = EstadoServidor.SOBRECARGADO
                    eventos.append(Evento(
                        tiempo=reloj,
                        tipo="SOBRECARGA",
                        tarea_id=tarea.id,
                        servidor_id=servidor.id,
                        detalle=(
                            f"Servidor {servidor.id} SOBRECARGADO "
                            f"(carga={servidor.carga:.1f} > umbral={umbral_sobrecarga})"
                        ),
                    ))
                    logger.info(
                        f"[t={reloj}] Servidor {servidor.id} SOBRECARGADO "
                        f"(carga={servidor.carga:.1f})"
                    )

                # ── Verificar si hay que provocar una falla (Escenario C) ──
                if (config_falla and not falla_ejecutada and
                        total_asignadas >= config_falla.tarea_trigger):
                    falla_ejecutada = True
                    srv_falla = next(
                        (s for s in servidores if s.id == config_falla.servidor_id),
                        None,
                    )
                    if srv_falla and srv_falla.estado != EstadoServidor.CAIDO:
                        _ejecutar_falla_servidor(
                            srv_falla, reloj, total_asignadas,
                            en_espera, trabajo_restante_override,
                            inicio_proceso, eventos,
                        )
                        tareas_reasignadas_count += len(
                            [e for e in eventos if e.tipo == "PENDIENTE_REASIGNACION"
                             and e.tiempo == reloj]
                        )
            else:
                # No hay servidores disponibles; la tarea espera
                en_espera.append(tarea)

        # ── Paso 3: Procesar trabajo en cada servidor ──
        for servidor in servidores:
            if servidor.estado == EstadoServidor.CAIDO or not servidor.cola:
                continue

            tarea_actual, restante = servidor.cola[0]

            # Registrar inicio de procesamiento si es la primera vez
            if tarea_actual.id not in inicio_proceso:
                inicio_proceso[tarea_actual.id] = reloj

            # El servidor procesa según su capacidad
            restante -= servidor.capacidad

            if restante <= 1e-9:
                # ── Tarea completada ──
                servidor.cola.pop(0)
                servidor.tareas_completadas.append(tarea_actual.id)

                # Obtener info de asignación
                srv_id, t_asig, reasig = asignacion_info.get(
                    tarea_actual.id, (servidor.id, 0, False)
                )

                registros.append(RegistroTarea(
                    tarea_id=tarea_actual.id,
                    duracion=tarea_actual.duracion,
                    tiempo_llegada=tarea_actual.tiempo_llegada,
                    servidor_id=servidor.id,
                    tiempo_asignacion=t_asig,
                    tiempo_inicio_proceso=inicio_proceso.get(tarea_actual.id, 0),
                    tiempo_fin=reloj,
                    reasignada=reasig,
                ))

                eventos.append(Evento(
                    tiempo=reloj,
                    tipo="FIN_TAREA",
                    tarea_id=tarea_actual.id,
                    servidor_id=servidor.id,
                    detalle=f"Tarea {tarea_actual.id} completada en Servidor {servidor.id}",
                ))

                # Si hay más tareas en cola, la siguiente empieza en el próximo tick
                if servidor.cola:
                    sig_tarea = servidor.cola[0][0]
                    if sig_tarea.id not in inicio_proceso:
                        inicio_proceso[sig_tarea.id] = reloj + 1

                # Verificar recuperación de sobrecarga
                if (servidor.estado == EstadoServidor.SOBRECARGADO and
                        servidor.carga <= umbral_sobrecarga):
                    servidor.estado = EstadoServidor.ACTIVO
                    eventos.append(Evento(
                        tiempo=reloj,
                        tipo="RECUPERACION",
                        tarea_id=-1,
                        servidor_id=servidor.id,
                        detalle=(
                            f"Servidor {servidor.id} recuperado "
                            f"(carga={servidor.carga:.1f})"
                        ),
                    ))
                    logger.info(
                        f"[t={reloj}] Servidor {servidor.id} RECUPERADO "
                        f"(carga={servidor.carga:.1f})"
                    )
            else:
                servidor.cola[0] = (tarea_actual, restante)

        reloj += 1

        # Límite de seguridad para evitar bucles infinitos
        if reloj > 100_000:
            raise RuntimeError(
                "La simulación excedió el límite de 100,000 ticks; "
                "no se generará un resultado incompleto."
            )

    # ── Calcular makespan ──
    makespan = max((r.tiempo_fin + 1 for r in registros), default=0)

    # Contar tareas reasignadas desde los registros
    tareas_reasignadas_count = sum(1 for r in registros if r.reasignada)

    logger.info(
        f"Simulación completada: makespan={makespan}, "
        f"tareas_procesadas={len(registros)}, "
        f"tareas_reasignadas={tareas_reasignadas_count}"
    )

    return ResultadoSimulacion(
        eventos=eventos,
        registros=registros,
        servidores=copy.deepcopy(servidores),
        makespan=makespan,
        nombre_estrategia=nombre_estrategia,
        nombre_escenario=nombre_escenario,
        tareas_reasignadas=tareas_reasignadas_count,
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
