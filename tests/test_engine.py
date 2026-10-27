import pytest

from src.algorithms import MenorCarga, RoundRobin
from src.engine import ConfiguracionFalla, ejecutar_simulacion
from src.metrics import calcular_metricas
from src.models import Servidor, Tarea
from src.parameters import ParametrosSimulacion
from src.scenarios import ejecutar_escenario_a, ejecutar_todos


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


def test_metrics_count_overload_and_time_waiting_for_available_server():
    resultado = ejecutar_simulacion(
        [Tarea(id=0, duracion=1), Tarea(id=1, duracion=1)],
        [Servidor(id=0)],
        RoundRobin(),
        umbral_sobrecarga=0.5,
    )
    metricas = calcular_metricas(resultado)

    assert metricas["sobrecargas_por_servidor"] == {0: 2}
    assert metricas["sobrecargas_total"] == 2
    assert metricas["tiempo_espera_cola_promedio"] == 0.5
    assert metricas["tiempo_espera_cola_maximo"] == 1


def test_server_recovers_below_threshold_before_finishing_its_task():
    resultado = ejecutar_simulacion(
        [Tarea(id=0, duracion=4), Tarea(id=1, duracion=1, tiempo_llegada=2)],
        [Servidor(id=0)],
        RoundRobin(),
        umbral_sobrecarga=2.5,
    )

    recuperacion = next(
        evento for evento in resultado.eventos if evento.tipo == "RECUPERACION"
    )
    assert recuperacion.tiempo == 1
    assert any(
        evento.tipo == "ASIGNACION"
        and evento.tarea_id == 1
        and evento.tiempo == 2
        for evento in resultado.eventos
    )


def test_every_strategy_completes_every_task_in_all_scenarios():
    parametros = ParametrosSimulacion(
        num_tareas=15,
        num_servidores=4,
        duracion_min=1,
        duracion_max=4,
        intervalo_llegada=2,
        umbral_sobrecarga=12,
        tarea_falla=5,
        servidor_falla=2,
        servidor_lento=2,
        capacidad_reducida=0.5,
        semilla=24,
        repeticiones=2,
    )
    resultados = ejecutar_todos(parametros)

    assert len(resultados) == 9
    for ejecuciones in resultados.values():
        assert isinstance(ejecuciones, list)
        assert len(ejecuciones) == parametros.repeticiones
        for resultado in ejecuciones:
            assert len(resultado.registros) == parametros.num_tareas
            assert len({registro.tarea_id for registro in resultado.registros}) == (
                parametros.num_tareas
            )
            if resultado.nombre_escenario == "C - Falla":
                assert resultado.tareas_reasignadas == sum(
                    registro.reasignada for registro in resultado.registros
                )


def test_scenario_runs_with_explicit_parameters_without_environment_config():
    parametros = ParametrosSimulacion(
        num_tareas=2,
        num_servidores=2,
        duracion_min=1,
        duracion_max=2,
        intervalo_llegada=2,
        umbral_sobrecarga=10,
        tarea_falla=1,
        servidor_falla=1,
        servidor_lento=0,
        capacidad_reducida=0.5,
        semilla=7,
        repeticiones=1,
    )
    resultado = ejecutar_escenario_a(
        [Tarea(id=0, duracion=1), Tarea(id=1, duracion=1)],
        RoundRobin(),
        parametros,
    )

    assert len(resultado.registros) == 2


def test_ejecutar_todos_accepts_dashboard_scenario_label():
    parametros = ParametrosSimulacion(
        num_tareas=3,
        num_servidores=2,
        duracion_min=1,
        duracion_max=2,
        intervalo_llegada=2,
        umbral_sobrecarga=10,
        tarea_falla=1,
        servidor_falla=1,
        servidor_lento=0,
        capacidad_reducida=0.5,
        semilla=7,
        repeticiones=1,
    )

    resultados = ejecutar_todos(
        parametros,
        escenarios_solicitados=["A - Normal"],
        estrategias_solicitadas=["round_robin"],
    )

    assert list(resultados) == [("A - Normal", "round_robin")]
    assert len(resultados[("A - Normal", "round_robin")][0].registros) == 3
