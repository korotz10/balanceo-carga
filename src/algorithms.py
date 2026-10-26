"""
Algoritmos de asignación de tareas a servidores (balanceo de carga).

Este módulo implementa tres estrategias clásicas de balanceo de carga,
independientes del motor de simulación, para poder reutilizarlas en
una implementación real con servidores HTTP.

ASIGNACIÓN vs PLANIFICACIÓN:
- La ASIGNACIÓN (este módulo) decide A QUÉ servidor va cada tarea.
  Es responsabilidad del balanceador de carga.
- La PLANIFICACIÓN decide EN QUÉ ORDEN un servidor procesa sus tareas.
  Es responsabilidad de cada servidor (en nuestra simulación, FIFO).

ESTRATEGIAS ESTÁTICAS vs DINÁMICAS:
- Estática: no considera el estado actual de los servidores para decidir.
  Ejemplo: Round Robin (solo sigue el turno), Aleatoria (elige al azar).
- Dinámica: consulta el estado (carga) de los servidores para decidir.
  Ejemplo: Menor Carga (elige el servidor menos cargado).
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from src.models import Tarea, Servidor


class NoServidoresDisponiblesError(Exception):
    """
    Se lanza cuando no hay servidores disponibles para asignar una tarea.

    En un sistema distribuido real, esto equivale a una situación donde
    todos los nodos están caídos o sobrecargados. El sistema debería
    encolar la tarea y reintentar, o rechazarla con un error 503.
    """
    pass


class EstrategiaAsignacion(ABC):
    """
    Interfaz común para todas las estrategias de asignación.

    Todas las estrategias implementan el método asignar(), que recibe
    una tarea y una lista de servidores disponibles, y devuelve el
    servidor elegido. Esto permite que el motor de simulación (y en
    el futuro, un balanceador real) use cualquier estrategia de forma
    intercambiable.
    """

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre descriptivo de la estrategia."""
        ...

    @abstractmethod
    def asignar(self, tarea: Tarea, servidores: list[Servidor]) -> Servidor:
        """
        Asigna una tarea a uno de los servidores disponibles.

        Args:
            tarea: La tarea a asignar.
            servidores: Lista de servidores DISPONIBLES (ya filtrados).
                        Se garantiza que len(servidores) >= 1.

        Returns:
            El servidor elegido para procesar la tarea.

        Raises:
            NoServidoresDisponiblesError: Si la lista está vacía.
        """
        ...

    def _validar_servidores(self, servidores: list[Servidor]) -> None:
        """Valida que haya al menos un servidor disponible."""
        if not servidores:
            raise NoServidoresDisponiblesError(
                "No hay servidores disponibles para asignar la tarea. "
                "Todos los servidores están caídos o sobrecargados."
            )


class RoundRobin(EstrategiaAsignacion):
    """
    Estrategia Round Robin (por turnos) — ESTÁTICA.

    Asigna las tareas en orden circular entre los servidores disponibles.
    No considera la carga actual de los servidores; solo sigue el turno.
    Si un servidor está caído o sobrecargado, lo salta.

    Ventajas:
    - Simple de implementar y entender.
    - Distribución equitativa cuando las tareas tienen duración similar.

    Limitaciones:
    - No se adapta a servidores con distinta capacidad.
    - No se adapta a tareas con distinta duración.
    - Puede sobrecargar servidores lentos.
    """

    def __init__(self) -> None:
        self._ultimo_servidor_id: int | None = None

    @property
    def nombre(self) -> str:
        return "Round Robin"

    def asignar(self, tarea: Tarea, servidores: list[Servidor]) -> Servidor:
        self._validar_servidores(servidores)
        ordenados = sorted(servidores, key=lambda servidor: servidor.id)
        servidor = next(
            (
                candidato
                for candidato in ordenados
                if self._ultimo_servidor_id is None
                or candidato.id > self._ultimo_servidor_id
            ),
            ordenados[0],
        )
        self._ultimo_servidor_id = servidor.id
        return servidor


class MenorCarga(EstrategiaAsignacion):
    """
    Estrategia de Menor Carga (Least Loaded) — DINÁMICA.

    Elige el servidor con menor carga estimada en el momento de la
    asignación. La carga se define como:

        carga = trabajo_pendiente / capacidad

    Esto representa cuánto tiempo tardará el servidor en procesar
    todas sus tareas pendientes.

    Criterio de desempate: si dos servidores tienen la misma carga,
    se elige el de menor ID. Esto garantiza determinismo.

    Ventajas:
    - Se adapta automáticamente a servidores con distinta capacidad.
    - Se adapta a tareas con distinta duración.
    - Tiende a producir la distribución más equilibrada.

    Limitaciones:
    - Necesita consultar el estado de todos los servidores (overhead).
    - En un sistema real, la información de carga puede estar
      desactualizada (problema de consistencia).
    """

    @property
    def nombre(self) -> str:
        return "Menor Carga"

    def asignar(self, tarea: Tarea, servidores: list[Servidor]) -> Servidor:
        self._validar_servidores(servidores)
        # min() con clave compuesta: menor carga, luego menor ID (desempate)
        return min(servidores, key=lambda s: (s.carga, s.id))


class Aleatoria(EstrategiaAsignacion):
    """
    Estrategia Aleatoria (Random) — ESTÁTICA.

    Elige un servidor al azar entre los disponibles, usando un generador
    de números aleatorios con semilla configurable para reproducibilidad.

    Al ser estática, no consulta la carga de los servidores. Esto la
    hace simple pero impredecible. Para obtener resultados estadísticos
    significativos, se ejecuta múltiples veces con semillas distintas
    y se reporta el promedio y la desviación estándar.

    Ventajas:
    - Muy simple de implementar.
    - No requiere información del estado de los servidores.
    - En promedio, distribuye equitativamente con muchas tareas.

    Limitaciones:
    - Puede generar desbalance por azar (varianza alta).
    - No se adapta a servidores con distinta capacidad.
    """

    def __init__(self, semilla: int = 42) -> None:
        self._rng: random.Random = random.Random(semilla)

    @property
    def nombre(self) -> str:
        return "Aleatoria"

    def asignar(self, tarea: Tarea, servidores: list[Servidor]) -> Servidor:
        self._validar_servidores(servidores)
        return self._rng.choice(servidores)


def crear_estrategia(nombre: str, semilla: int = 42) -> EstrategiaAsignacion:
    """
    Factoría simple para crear estrategias por nombre.

    Args:
        nombre: "round_robin", "menor_carga" o "aleatoria".
        semilla: Semilla para la estrategia aleatoria.

    Returns:
        Instancia de la estrategia solicitada.

    Raises:
        ValueError: Si el nombre no es válido.
    """
    estrategias: dict[str, Callable[[], EstrategiaAsignacion]] = {
        "round_robin": lambda: RoundRobin(),
        "menor_carga": lambda: MenorCarga(),
        "aleatoria": lambda: Aleatoria(semilla),
    }
    if nombre not in estrategias:
        nombres_validos = ", ".join(estrategias.keys())
        raise ValueError(
            f"Estrategia '{nombre}' no reconocida. "
            f"Opciones válidas: {nombres_validos}"
        )
    return estrategias[nombre]()
