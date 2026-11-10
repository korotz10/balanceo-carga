from src.algorithms import RoundRobin
from src.engine import EventoProgramado, ejecutar_simulacion
from src.models import Servidor, Tarea


def test_historial_registra_tick_servidores_espera_y_llegadas():
    resultado = ejecutar_simulacion(
        [Tarea(0, 3), Tarea(1, 1, 1)],
        [Servidor(0)],
        RoundRobin(),
        eventos_programados=[
            EventoProgramado(0, 0, "CAIDA"),
            EventoProgramado(2, 0, "RECUPERACION"),
        ],
        registrar_historial=True,
    )

    historial = resultado.historial
    assert historial is not None
    assert [registro.tick for registro in historial] == list(range(resultado.makespan))
    assert historial[0].servidores[0].estado == "CAIDO"
    assert historial[0].cola_espera == [0]
    assert historial[1].llegadas == [1]
    assert historial[1].cola_espera == [0, 1]
    assert historial[2].servidores[0].estado == "ACTIVO"


def test_historial_es_opcional_y_no_se_expone_si_no_se_solicita():
    resultado = ejecutar_simulacion(
        [Tarea(0, 2)],
        [Servidor(0)],
        RoundRobin(),
    )

    assert resultado.historial is None
