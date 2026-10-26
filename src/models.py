"""
Modelos de datos para la simulación de balanceo de carga.

Define las entidades fundamentales de un sistema distribuido simplificado:
- Tarea: unidad de trabajo que debe ser procesada por un servidor.
- Servidor: nodo de procesamiento con capacidad limitada y cola FIFO.

En un sistema distribuido real, las tareas llegan desde clientes
y son asignadas a servidores (nodos de procesamiento). Cada servidor
tiene recursos limitados y procesa las tareas en un orden determinado
(en este caso, FIFO: First In, First Out).

DIFERENCIA CLAVE entre asignación y planificación:
- La PLANIFICACIÓN local (scheduling) determina en qué orden un servidor
  procesa sus tareas (aquí usamos FIFO).
- La ASIGNACIÓN (allocation) determina a qué servidor va cada tarea
  (esto lo decide el algoritmo de balanceo de carga en algorithms.py).
"""

from dataclasses import dataclass, field
from enum import Enum


class EstadoServidor(Enum):
    """
    Estados posibles de un servidor en el sistema distribuido.

    - ACTIVO: funcionando normalmente, puede recibir nuevas tareas.
    - SOBRECARGADO: su carga estimada supera el umbral. Sigue procesando
      su cola pero NO recibe tareas nuevas hasta que la carga baje.
    - CAIDO: fuera de servicio. No procesa ni recibe tareas.
    """
    ACTIVO = "ACTIVO"
    SOBRECARGADO = "SOBRECARGADO"
    CAIDO = "CAIDO"


@dataclass
class Tarea:
    """
    Representa una tarea (proceso) que debe ser ejecutada por un servidor.

    En sistemas distribuidos, una tarea es la unidad mínima de trabajo
    que se asigna a un procesador. Tiene una duración (costo computacional)
    y un tiempo de llegada al sistema.

    Attributes:
        id: Identificador único de la tarea.
        duracion: Tiempo de procesamiento requerido (en unidades de tiempo).
        tiempo_llegada: Momento en que la tarea llega al sistema y puede
                        ser asignada a un servidor.
    """
    id: int
    duracion: int
    tiempo_llegada: int = 0


@dataclass
class Servidor:
    """
    Representa un servidor (nodo de procesamiento) en el sistema distribuido.

    Cada servidor tiene una capacidad de procesamiento y mantiene una cola
    FIFO de tareas pendientes. La carga se define como el tiempo estimado
    para terminar todas las tareas en cola:

        carga = trabajo_pendiente / capacidad

    Esta definición es más realista que simplemente contar tareas, porque
    considera tanto la cantidad de trabajo restante como la velocidad
    del servidor. Un servidor con capacidad 0.5 reportará el doble de
    carga que uno con capacidad 1.0 para la misma cola de tareas.

    Attributes:
        id: Identificador único del servidor.
        capacidad: Velocidad de procesamiento (unidades de trabajo por
                   unidad de tiempo). Un servidor con capacidad 0.5
                   tarda el doble en procesar cada tarea.
        cola: Lista de tuplas (tarea, trabajo_restante) en orden FIFO.
              Esto representa la PLANIFICACIÓN local del servidor.
        tareas_completadas: Lista de IDs de tareas ya procesadas.
        estado: Estado actual del servidor (ACTIVO, SOBRECARGADO, CAIDO).
        total_tareas_recibidas: Contador total de tareas asignadas.
    """
    id: int
    capacidad: float = 1.0
    cola: list = field(default_factory=list)
    tareas_completadas: list = field(default_factory=list)
    estado: EstadoServidor = field(default=EstadoServidor.ACTIVO)
    total_tareas_recibidas: int = 0

    @property
    def trabajo_pendiente(self) -> float:
        """Suma del trabajo restante en la cola (en unidades de trabajo)."""
        return sum(restante for _, restante in self.cola)

    @property
    def carga(self) -> float:
        """
        Carga del servidor = trabajo_pendiente / capacidad.

        Representa el tiempo estimado (en unidades de tiempo) para
        terminar todas las tareas en cola. Un valor de 10 significa
        que el servidor necesita aproximadamente 10 unidades de tiempo
        para vaciar su cola.

        Este es el criterio que usa la estrategia de menor carga
        para elegir el servidor menos ocupado.
        """
        if self.capacidad <= 0:
            return float('inf')
        return self.trabajo_pendiente / self.capacidad

    def esta_disponible(self) -> bool:
        """
        Un servidor está disponible solo si está ACTIVO.

        Los servidores SOBRECARGADOS siguen procesando su cola pero
        no reciben tareas nuevas hasta que su carga baje del umbral.
        Los servidores CAIDOS no hacen nada.
        """
        return self.estado == EstadoServidor.ACTIVO

    def agregar_tarea(self, tarea: Tarea) -> None:
        """Agrega una tarea al final de la cola FIFO del servidor."""
        self.cola.append((tarea, float(tarea.duracion)))
        self.total_tareas_recibidas += 1
