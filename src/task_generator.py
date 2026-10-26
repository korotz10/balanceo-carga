"""
Generador de tareas para la simulación.

Crea un conjunto de tareas con duración aleatoria y tiempos de llegada
escalonados, usando una semilla fija para reproducibilidad.

En un sistema distribuido real, las tareas llegarían desde clientes
en momentos impredecibles. En nuestra simulación, las generamos
de antemano con un intervalo configurable entre llegadas, lo que
permite simular el reloj avanzando y que las estrategias dinámicas
(como Menor Carga) vean la carga real al momento de cada asignación.
"""

import random
import logging
from src.models import Tarea

logger = logging.getLogger(__name__)


def generar_tareas(
    cantidad: int = 100,
    duracion_min: int = 1,
    duracion_max: int = 10,
    semilla: int = 42,
    intervalo_llegada: int = 2,
) -> list[Tarea]:
    """
    Genera una lista de tareas con duración aleatoria y llegada escalonada.

    La semilla fija garantiza que siempre se generen las mismas tareas,
    lo cual es esencial para comparar estrategias de forma justa:
    todas reciben exactamente el mismo conjunto de trabajo.

    Args:
        cantidad: Número de tareas a generar.
        duracion_min: Duración mínima de una tarea (unidades de tiempo).
        duracion_max: Duración máxima de una tarea (unidades de tiempo).
        semilla: Semilla del generador aleatorio para reproducibilidad.
        intervalo_llegada: Unidades de tiempo entre llegadas sucesivas.

    Returns:
        Lista de tareas ordenadas por tiempo de llegada.
    """
    if cantidad <= 0:
        raise ValueError("cantidad debe ser mayor que 0")
    if duracion_min <= 0 or duracion_max < duracion_min:
        raise ValueError("El rango de duración debe cumplir 0 < mínimo <= máximo")
    if intervalo_llegada <= 0:
        raise ValueError("intervalo_llegada debe ser mayor que 0")

    rng = random.Random(semilla)
    tareas: list[Tarea] = []

    for i in range(cantidad):
        duracion = rng.randint(duracion_min, duracion_max)
        tiempo_llegada = i * intervalo_llegada
        tareas.append(Tarea(id=i, duracion=duracion, tiempo_llegada=tiempo_llegada))

    duracion_total = sum(t.duracion for t in tareas)
    duracion_promedio = duracion_total / cantidad if cantidad > 0 else 0
    logger.info(
        f"Generadas {cantidad} tareas: duración total={duracion_total}, "
        f"promedio={duracion_promedio:.1f}, rango=[{duracion_min}, {duracion_max}], "
        f"semilla={semilla}, intervalo_llegada={intervalo_llegada}"
    )

    return tareas
