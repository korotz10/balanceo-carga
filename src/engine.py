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

EVENTOS PROGRAMADOS (opcional):
Se aplican al FINAL del tick indicado, después de procesar y de revisar
las recuperaciones de sobrecarga. Por lo tanto, las tareas reasignadas
por una CAIDA programada se reasignan en el tick siguiente, igual que
en el escenario C original.

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
    - CAIDA: un servidor falla (escenario C o evento programado).
    - REASIGNACION: tarea movida de un servidor caído a la cola de espera.
    - ESPERA: tarea no pudo ser asignada (todos los servidores ocupados).
    - RECUPERACION_SERVIDOR: un servidor caído vuelve a ACTIVO por evento programado.
    - DEGRADACION: la capacidad de un servidor se reduce por evento programado.
    - RESTAURACION: la capacidad de un servidor se restaura a su valor original.
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
        servidor_id: ID preferido como desempate si se selecciona mayor carga.
        elegir_mas_cargado: Si es True, cae el servidor con más trabajo pendiente
            en el momento del disparador para que la reasignación sea visible.
    """
    tarea_trigger: int
    servidor_id: int
    elegir_mas_cargado: bool = False


@dataclass(frozen=True)
class EventoProgramado:
    """
    Evento programado para ocurrir en un tick específico de la simulación.

    Los eventos se aplican al FINAL del tick indicado (después de procesar
    tareas y de revisar recuperaciones de sobrecarga). Esto significa que
    las tareas reasignadas por una CAIDA se reasignan en el tick siguiente.

    Tipos válidos:
    - "CAIDA": el servidor pasa a CAIDO. Su cola completa (incluida la tarea
      en proceso) conserva el trabajo restante y pasa a la cola de espera.
    - "RECUPERACION": un servidor CAIDO pasa a ACTIVO con cola vacía.
      Genera evento RECUPERACION_SERVIDOR (distinto del RECUPERACION de
      sobrecarga, para no confundir métricas ni filtros).
    - "DEGRADACION": cambia la capacidad del servidor al valor indicado.
      Si tras degradar carga > umbral, pasa a SOBRECARGADO.
    - "RESTAURACION": restaura la capacidad original del servidor.

    Attributes:
        tick: Instante en que se aplica el evento (>= 0).
        servidor_id: ID del servidor afectado.
        tipo: Uno de "CAIDA", "RECUPERACION", "DEGRADACION", "RESTAURACION".
        capacidad: Nueva capacidad (solo para DEGRADACION, entre 0 y 1).
    """
    tick: int
    servidor_id: int
    tipo: str
    capacidad: float | None = None


# ---------------------------------------------------------------------------
# Snapshot para historial por tick (opcional)
# ---------------------------------------------------------------------------

@dataclass
class SnapshotServidor:
    """Instantánea del estado de un servidor en un tick dado."""
    servidor_id: int
    estado: str
    capacidad: float
    carga: float
    trabajo_pendiente: float
    tarea_en_proceso: int | None
    tareas_en_cola: list[int]


@dataclass
class RegistroTick:
    """Registro completo de un tick de simulación para reproducción."""
    tick: int
    servidores: list[SnapshotServidor]
    cola_espera: list[int]
    llegadas: list[int]


# ---------------------------------------------------------------------------
# Excepción para caída total del sistema
# ---------------------------------------------------------------------------

class SistemaCaidoError(RuntimeError):
    """
    Se lanza cuando todos los servidores están CAIDO y no quedan
    recuperaciones programadas futuras.

    Lleva el estado parcial de la simulación para que el panel
    pueda mostrar lo que ocurrió hasta el momento de la caída total.

    Attributes:
        eventos: Lista de eventos registrados hasta el error.
        registros: Lista de tareas completadas hasta el error.
        tick: Tick en el que ocurrió la caída total.
        tareas_pendientes: IDs de las tareas que no pudieron completarse.
    """

    def __init__(
        self,
        mensaje: str,
        eventos: list[Evento],
        registros: list[RegistroTarea],
        tick: int,
        tareas_pendientes: list[int],
    ) -> None:
        super().__init__(mensaje)
        self.eventos: list[Evento] = eventos
        self.registros: list[RegistroTarea] = registros
        self.tick: int = tick
        self.tareas_pendientes: list[int] = tareas_pendientes


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
    historial: list[RegistroTick] | None = None


# ---------------------------------------------------------------------------
# Validación de eventos programados
# ---------------------------------------------------------------------------

_TIPOS_EVENTO_VALIDOS: set[str] = {"CAIDA", "RECUPERACION", "DEGRADACION", "RESTAURACION"}


def _validar_eventos_programados(
    eventos: list[EventoProgramado],
    ids_servidores: set[int],
) -> None:
    """Valida los eventos programados antes de iniciar la simulación.

    Raises:
        ValueError: Si algún evento es inválido.
    """
    for evento in eventos:
        if evento.tick < 0:
            raise ValueError(
                f"EventoProgramado inválido: tick={evento.tick} debe ser >= 0."
            )
        if evento.servidor_id not in ids_servidores:
            raise ValueError(
                f"EventoProgramado inválido: servidor_id={evento.servidor_id} "
                f"no existe. IDs válidos: {sorted(ids_servidores)}."
            )
        if evento.tipo not in _TIPOS_EVENTO_VALIDOS:
            raise ValueError(
                f"EventoProgramado inválido: tipo='{evento.tipo}' no reconocido. "
                f"Tipos válidos: {sorted(_TIPOS_EVENTO_VALIDOS)}."
            )
        if evento.tipo == "DEGRADACION":
            if evento.capacidad is None:
                raise ValueError(
                    "EventoProgramado inválido: DEGRADACION requiere capacidad."
                )
            if not (0 < evento.capacidad < 1):
                raise ValueError(
                    f"EventoProgramado inválido: capacidad={evento.capacidad} "
                    "debe estar entre 0 (excl.) y 1 (excl.) en DEGRADACION."
                )


# ---------------------------------------------------------------------------
# Funciones auxiliares del motor
# ---------------------------------------------------------------------------

def _snapshot_servidores(servidores: list[Servidor]) -> list[SnapshotServidor]:
    """Captura el estado de todos los servidores en un instante."""
    snapshots: list[SnapshotServidor] = []
    for srv in servidores:
        tarea_en_proceso: int | None = None
        tareas_en_cola: list[int] = []
        for idx, (tarea, _) in enumerate(srv.cola):
            if idx == 0:
                tarea_en_proceso = tarea.id
            tareas_en_cola.append(tarea.id)
        snapshots.append(SnapshotServidor(
            servidor_id=srv.id,
            estado=srv.estado.value,
            capacidad=srv.capacidad,
            carga=srv.carga,
            trabajo_pendiente=srv.trabajo_pendiente,
            tarea_en_proceso=tarea_en_proceso,
            tareas_en_cola=tareas_en_cola,
        ))
    return snapshots


def _hay_recuperacion_futura(
    eventos_programados: list[EventoProgramado],
    tick_actual: int,
) -> bool:
    """Comprueba si hay una recuperación pendiente desde el tick actual.

    Los eventos se aplican al final del tick, así que una recuperación
    programada para el tick actual todavía puede reactivar el sistema.
    """
    return any(
        ev.tipo == "RECUPERACION" and ev.tick >= tick_actual
        for ev in eventos_programados
    )


def _aplicar_caida_servidor(
    srv: Servidor,
    reloj: int,
    eventos: list[Evento],
    en_espera: list[Tarea],
    trabajo_restante_override: dict[int, float],
    inicio_proceso: dict[int, int],
    detalle_extra: str = "",
) -> None:
    """Aplica la lógica de caída a un servidor: lo marca CAIDO, mueve
    sus tareas a la cola de espera conservando el trabajo restante."""
    srv.estado = EstadoServidor.CAIDO
    eventos.append(Evento(
        tiempo=reloj,
        tipo="CAIDA",
        tarea_id=-1,
        servidor_id=srv.id,
        detalle=f"Servidor {srv.id} cayó{detalle_extra}",
    ))
    for tarea_pendiente, trabajo_restante in list(srv.cola):
        srv.cola.remove((tarea_pendiente, trabajo_restante))
        inicio_proceso.pop(tarea_pendiente.id, None)
        trabajo_restante_override[tarea_pendiente.id] = trabajo_restante
        en_espera.append(tarea_pendiente)
        eventos.append(Evento(
            tiempo=reloj,
            tipo="PENDIENTE_REASIGNACION",
            tarea_id=tarea_pendiente.id,
            servidor_id=srv.id,
            detalle=(
                f"Tarea {tarea_pendiente.id} reasignada con "
                f"{trabajo_restante:.1f} unidades restantes"
            ),
        ))
    srv.cola.clear()


# ---------------------------------------------------------------------------
# Motor de simulación
# ---------------------------------------------------------------------------

def ejecutar_simulacion(
    tareas: list[Tarea],
    servidores: list[Servidor],
    estrategia: EstrategiaAsignacion,
    umbral_sobrecarga: float = 12.0,
    config_falla: ConfiguracionFalla | None = None,
    nombre_escenario: str = "",
    eventos_programados: list[EventoProgramado] | None = None,
    registrar_historial: bool = False,
) -> ResultadoSimulacion:
    """Ejecuta una corrida con reloj discreto.

    Las tareas de un servidor caído vuelven al proceso de asignación en el
    siguiente tick, por lo que pierden como mínimo un tick tras la caída.

    Args:
        tareas: Lista de tareas a procesar.
        servidores: Lista de servidores disponibles.
        estrategia: Estrategia de asignación a usar.
        umbral_sobrecarga: Umbral de carga para marcar sobrecarga.
        config_falla: Configuración de falla del escenario C (opcional).
        nombre_escenario: Nombre descriptivo del escenario.
        eventos_programados: Lista de eventos programados (opcional).
            Se aplican al final del tick indicado, después de procesar
            y de revisar recuperaciones de sobrecarga.
        registrar_historial: Si True, guarda un snapshot por tick en
            ResultadoSimulacion.historial. Los registros y eventos
            son idénticos con o sin historial activado.

    Returns:
        ResultadoSimulacion con todos los datos de la corrida.

    Raises:
        SistemaCaidoError: Si todos los servidores están CAIDO y no hay
            recuperaciones programadas futuras. El mensaje contiene
            "no quedan servidores".
        ValueError: Si los eventos programados son inválidos.
    """
    # --- Validación de eventos programados ---
    eventos_prog: list[EventoProgramado] = eventos_programados or []
    if eventos_prog:
        ids_servidores = {srv.id for srv in servidores}
        _validar_eventos_programados(eventos_prog, ids_servidores)

    # --- Guardar capacidades originales para RESTAURACION ---
    capacidad_original: dict[int, float] = {srv.id: srv.capacidad for srv in servidores}

    # --- Agrupar eventos programados por tick para acceso rápido ---
    eventos_por_tick: dict[int, list[EventoProgramado]] = {}
    for ev in eventos_prog:
        eventos_por_tick.setdefault(ev.tick, []).append(ev)

    # --- Estado de la simulación ---
    eventos: list[Evento] = []
    registros: list[RegistroTarea] = []
    historial: list[RegistroTick] = [] if registrar_historial else []
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
        # --- Comprobación de sistema caído ---
        if (pendientes or en_espera) and not any(
            servidor.estado != EstadoServidor.CAIDO for servidor in servidores
        ):
            # Hay tareas pendientes y todos los servidores están caídos.
            # Si hay una recuperación programada futura, las tareas esperan.
            if _hay_recuperacion_futura(eventos_prog, reloj):
                # Las tareas esperan; registrar eventos ESPERA si es necesario.
                for tarea in en_espera:
                    if tarea.id not in inicio_espera:
                        inicio_espera[tarea.id] = reloj
                        eventos.append(Evento(
                            tiempo=reloj,
                            tipo="ESPERA",
                            tarea_id=tarea.id,
                            servidor_id=-1,
                            detalle=(
                                f"Tarea {tarea.id} espera porque no hay "
                                "servidores disponibles"
                            ),
                        ))
                # Avanzar el reloj buscando el tick de la próxima recuperación
                # o la llegada de una nueva tarea.
                llegadas_en_espera: list[int] = []
                while pendientes and pendientes[0].tiempo_llegada <= reloj:
                    t = pendientes.pop(0)
                    en_espera.append(t)
                    llegadas_en_espera.append(t.id)
                    if t.id not in inicio_espera:
                        inicio_espera[t.id] = reloj
                        eventos.append(Evento(
                            tiempo=reloj,
                            tipo="ESPERA",
                            tarea_id=t.id,
                            servidor_id=-1,
                            detalle=(
                                f"Tarea {t.id} espera porque no hay "
                                "servidores disponibles"
                            ),
                        ))

                # Aplicar eventos programados de este tick
                if reloj in eventos_por_tick:
                    for ev_prog in eventos_por_tick[reloj]:
                        _aplicar_evento_programado(
                            ev_prog, servidores, reloj, eventos, en_espera,
                            trabajo_restante_override, inicio_proceso,
                            capacidad_original, umbral_sobrecarga,
                        )

                # Registrar el estado al cierre del tick, igual que en el
                # flujo normal de procesamiento.
                if registrar_historial:
                    historial.append(RegistroTick(
                        tick=reloj,
                        servidores=_snapshot_servidores(servidores),
                        cola_espera=[t.id for t in en_espera],
                        llegadas=llegadas_en_espera,
                    ))

                reloj += 1
                if reloj > 100_000:
                    raise RuntimeError(
                        "La simulación excedió el límite de 100,000 ticks; "
                        "no se generará un resultado incompleto."
                    )
                continue
            else:
                # Sin recuperación futura: caída total del sistema.
                ids_pendientes = (
                    [t.id for t in en_espera]
                    + [t.id for t in pendientes]
                )
                raise SistemaCaidoError(
                    "La simulación no puede continuar: no quedan servidores "
                    "disponibles y hay tareas pendientes.",
                    eventos=eventos,
                    registros=registros,
                    tick=reloj,
                    tareas_pendientes=ids_pendientes,
                )

        # --- Recoger llegadas del tick ---
        nuevas: list[Tarea] = []
        while pendientes and pendientes[0].tiempo_llegada <= reloj:
            nuevas.append(pendientes.pop(0))

        por_asignar = en_espera + nuevas
        en_espera = []

        # --- Asignación de tareas ---
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
                activos = [
                    servidor_actual
                    for servidor_actual in servidores
                    if servidor_actual.estado != EstadoServidor.CAIDO
                ]
                if config_falla.elegir_mas_cargado and activos:
                    # Se falla el nodo con más trabajo restante para hacer
                    # observable la recuperación sin cambiar el instante elegido.
                    srv_falla = max(
                        activos,
                        key=lambda servidor_actual: (
                            servidor_actual.trabajo_pendiente,
                            servidor_actual.id == config_falla.servidor_id,
                            -servidor_actual.id,
                        ),
                    )
                else:
                    srv_falla = next(
                        (
                            servidor_actual
                            for servidor_actual in servidores
                            if servidor_actual.id == config_falla.servidor_id
                        ),
                        None,
                    )
                if srv_falla and srv_falla.estado != EstadoServidor.CAIDO:
                    _aplicar_caida_servidor(
                        srv_falla, reloj, eventos, en_espera,
                        trabajo_restante_override, inicio_proceso,
                        detalle_extra=f" tras asignar la tarea #{total_asignadas}",
                    )

        # --- Procesamiento de tareas en servidores ---
        for servidor in servidores:
            if servidor.estado == EstadoServidor.CAIDO or not servidor.cola:
                continue
            tarea_actual, trabajo_restante = servidor.cola[0]
            if tarea_actual.id not in inicio_proceso:
                inicio_proceso[tarea_actual.id] = reloj
            trabajo_procesado = min(servidor.capacidad, trabajo_restante)
            servidor.trabajo_procesado += trabajo_procesado
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

        # --- Recuperación de sobrecarga ---
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

        # --- Aplicar eventos programados al final del tick ---
        if reloj in eventos_por_tick:
            for ev_prog in eventos_por_tick[reloj]:
                _aplicar_evento_programado(
                    ev_prog, servidores, reloj, eventos, en_espera,
                    trabajo_restante_override, inicio_proceso,
                    capacidad_original, umbral_sobrecarga,
                )

        # --- Registrar historial si está activado ---
        if registrar_historial:
            historial.append(RegistroTick(
                tick=reloj,
                servidores=_snapshot_servidores(servidores),
                cola_espera=[t.id for t in en_espera],
                llegadas=[t.id for t in nuevas],
            ))

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
        historial=historial if registrar_historial else None,
    )


# ---------------------------------------------------------------------------
# Aplicación de eventos programados
# ---------------------------------------------------------------------------

def _aplicar_evento_programado(
    ev: EventoProgramado,
    servidores: list[Servidor],
    reloj: int,
    eventos: list[Evento],
    en_espera: list[Tarea],
    trabajo_restante_override: dict[int, float],
    inicio_proceso: dict[int, int],
    capacidad_original: dict[int, float],
    umbral_sobrecarga: float,
) -> None:
    """Aplica un evento programado individual al estado de la simulación.

    Se llama al final de cada tick, después del procesamiento y de la
    recuperación de sobrecarga.
    """
    srv = next(s for s in servidores if s.id == ev.servidor_id)

    if ev.tipo == "CAIDA":
        if srv.estado == EstadoServidor.CAIDO:
            return  # ya está caído, no hacer nada
        _aplicar_caida_servidor(
            srv, reloj, eventos, en_espera,
            trabajo_restante_override, inicio_proceso,
            detalle_extra=f" (evento programado en tick {ev.tick})",
        )

    elif ev.tipo == "RECUPERACION":
        if srv.estado != EstadoServidor.CAIDO:
            return  # no está caído, no se puede recuperar
        srv.estado = EstadoServidor.ACTIVO
        srv.cola.clear()
        eventos.append(Evento(
            tiempo=reloj,
            tipo="RECUPERACION_SERVIDOR",
            tarea_id=-1,
            servidor_id=srv.id,
            detalle=(
                f"Servidor {srv.id} recuperado de caída "
                f"(evento programado en tick {ev.tick})"
            ),
        ))

    elif ev.tipo == "DEGRADACION":
        assert ev.capacidad is not None  # validado previamente
        srv.capacidad = ev.capacidad
        eventos.append(Evento(
            tiempo=reloj,
            tipo="DEGRADACION",
            tarea_id=-1,
            servidor_id=srv.id,
            detalle=(
                f"Servidor {srv.id} degradado a capacidad "
                f"{ev.capacidad:.2f} (evento programado en tick {ev.tick})"
            ),
        ))
        # Si tras degradar la carga supera el umbral, marcar sobrecarga
        if (
            srv.carga > umbral_sobrecarga
            and srv.estado == EstadoServidor.ACTIVO
        ):
            srv.estado = EstadoServidor.SOBRECARGADO
            eventos.append(Evento(
                tiempo=reloj,
                tipo="SOBRECARGA",
                tarea_id=-1,
                servidor_id=srv.id,
                detalle=(
                    f"Servidor {srv.id} SOBRECARGADO tras degradación "
                    f"(carga={srv.carga:.1f} > umbral={umbral_sobrecarga})"
                ),
            ))

    elif ev.tipo == "RESTAURACION":
        cap_orig = capacidad_original[srv.id]
        srv.capacidad = cap_orig
        eventos.append(Evento(
            tiempo=reloj,
            tipo="RESTAURACION",
            tarea_id=-1,
            servidor_id=srv.id,
            detalle=(
                f"Servidor {srv.id} restaurado a capacidad original "
                f"{cap_orig:.2f} (evento programado en tick {ev.tick})"
            ),
        ))
