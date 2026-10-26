import pytest

from src.algorithms import (
    Aleatoria,
    MenorCarga,
    NoServidoresDisponiblesError,
    RoundRobin,
)
from src.models import Servidor, Tarea


def test_round_robin_keeps_turn_when_available_server_set_changes():
    estrategia = RoundRobin()
    servidores = [Servidor(id=id_) for id_ in range(3)]
    tarea = Tarea(id=0, duracion=1)

    assert estrategia.asignar(tarea, servidores).id == 0
    assert estrategia.asignar(tarea, servidores).id == 1
    assert estrategia.asignar(tarea, [servidores[0], servidores[2]]).id == 2
    assert estrategia.asignar(tarea, [servidores[0], servidores[2]]).id == 0


def test_menor_carga_chooses_lowest_load_then_lowest_id():
    servidores = [Servidor(id=1), Servidor(id=0)]
    servidores[0].agregar_tarea(Tarea(id=1, duracion=3))
    servidores[1].agregar_tarea(Tarea(id=2, duracion=3))

    assert MenorCarga().asignar(Tarea(id=3, duracion=1), servidores).id == 0


def test_random_strategy_is_reproducible():
    servidores = [Servidor(id=id_) for id_ in range(4)]
    tareas = [Tarea(id=id_, duracion=1) for id_ in range(20)]
    primera = Aleatoria(42)
    segunda = Aleatoria(42)

    asignaciones_1 = [primera.asignar(tarea, servidores).id for tarea in tareas]
    asignaciones_2 = [segunda.asignar(tarea, servidores).id for tarea in tareas]

    assert asignaciones_1 == asignaciones_2


def test_algorithms_raise_when_no_servers_are_available():
    with pytest.raises(NoServidoresDisponiblesError):
        RoundRobin().asignar(Tarea(id=0, duracion=1), [])
