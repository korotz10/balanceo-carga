import pytest

from src.algorithms import MenorCarga, RoundRobin
from src.engine import ConfiguracionFalla, ejecutar_simulacion
from src.metrics import calcular_metricas
from src.models import Servidor, Tarea


def test_engine_completes_every_task_and_reports_elapsed_time():
    tareas = [Tarea(id=0, duracion=1), Tarea(id=1, duracion=1)]
    resultado = ejecutar_simulacion(
        tareas,
        [Servidor(id=0)],
        RoundRobin(),
        nombre_escenario="prueba",
    )

    assert len(resultado.registros) == 2
    assert resultado.makespan == 2
    assert {registro.tarea_id for registro in resultado.registros} == {0, 1}


def test_failure_reassigns_tasks_without_losing_completions():
    tareas = [Tarea(id=id_, duracion=4, tiempo_llegada=id_) for id_ in range(12)]
    resultado = ejecutar_simulacion(
        tareas,
        [Servidor(id=id_) for id_ in range(3)],
        RoundRobin(),
        umbral_sobrecarga=100,
        config_falla=ConfiguracionFalla(tarea_trigger=3, servidor_id=1),
        nombre_escenario="C - Falla",
    )

    assert len(resultado.registros) == len(tareas)
    assert resultado.tareas_reasignadas > 0
    assert len({registro.tarea_id for registro in resultado.registros}) == len(tareas)
    assert any(evento.tipo == "CAIDA" for evento in resultado.eventos)


def test_engine_raises_instead_of_returning_partial_results_without_servers():
    with pytest.raises(RuntimeError, match="no quedan servidores"):
        ejecutar_simulacion(
            [Tarea(id=0, duracion=2)],
            [Servidor(id=0)],
            RoundRobin(),
            config_falla=ConfiguracionFalla(tarea_trigger=1, servidor_id=0),
        )


def test_metrics_match_manual_values_for_small_simulation():
    tareas = [Tarea(id=0, duracion=2), Tarea(id=1, duracion=1)]
    resultado = ejecutar_simulacion(
        tareas,
        [Servidor(id=0), Servidor(id=1)],
        MenorCarga(),
        nombre_escenario="prueba",
    )
    metricas = calcular_metricas(resultado)

    assert metricas["tareas_completadas"] == 2
    assert metricas["tareas_por_servidor"] == {0: 1, 1: 1}
    assert metricas["carga_por_servidor"] == {0: 2, 1: 1}
    assert metricas["desviacion_estandar_carga"] == 0.5
    assert metricas["tiempo_espera_promedio"] == 0
