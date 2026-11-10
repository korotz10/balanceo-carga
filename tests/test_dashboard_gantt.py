from src.algorithms import RoundRobin
from src.dashboard import _crear_figura_gantt
from src.engine import ejecutar_simulacion
from src.models import Servidor, Tarea


def test_gantt_uses_numeric_simulation_ticks_and_visible_task_intervals():
    resultado = ejecutar_simulacion(
        [Tarea(0, 3), Tarea(1, 2)],
        [Servidor(0)],
        RoundRobin(),
    )

    figura = _crear_figura_gantt(resultado)

    assert figura is not None
    assert figura.layout.xaxis.type == "linear"
    assert figura.layout.xaxis.title.text == "Tiempo simulado (ticks)"
    barras = [traza for traza in figura.data if traza.type == "bar"]
    assert len(barras) == 2
    assert list(barras[0].x) == [3]
    assert list(barras[0].base) == [0]
    assert list(barras[1].x) == [2]
    assert list(barras[1].base) == [3]


def test_gantt_is_empty_when_execution_has_no_completed_tasks():
    resultado = ejecutar_simulacion([], [Servidor(0)], RoundRobin())

    assert _crear_figura_gantt(resultado) is None
