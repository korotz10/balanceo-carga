"""Trazas de 8 tareas calculadas a mano (duraciones con semilla 42: 2,1,5,4,4,3,2,9)."""
import pytest

from src.metrics import calcular_metricas
from src.scenarios import ejecutar_todos
from tests.conftest import parametros_base

A, B, C = "A - Normal", "B - Sobrecarga", "C - Falla"


def p8(**extra):
    valores = dict(num_tareas=8, intervalo_llegada=1, umbral_sobrecarga=1000, tarea_falla=3, repeticiones=1)
    valores.update(extra)
    return parametros_base(**valores)


def corrida(parametros, escenario, estrategia):
    return ejecutar_todos(parametros, escenarios_solicitados=[escenario], estrategias_solicitadas=[estrategia])[(escenario, estrategia)][0]


def columnas(res):
    regs = sorted(res.registros, key=lambda r: r.tarea_id)
    return ([r.servidor_id for r in regs], [r.tiempo_inicio_proceso for r in regs], [r.tiempo_fin for r in regs])


def test_duraciones_de_la_semilla_42():
    from src.task_generator import generar_tareas
    assert [t.duracion for t in generar_tareas(8, 1, 10, 42, 1)] == [2, 1, 5, 4, 4, 3, 2, 9]


@pytest.mark.parametrize("estrategia", ["round_robin", "menor_carga"])
def test_escenario_a(estrategia):
    res = corrida(p8(), A, estrategia)
    assert columnas(res) == ([0, 1, 2, 3, 0, 1, 2, 3], [0, 1, 2, 3, 4, 5, 7, 7], [2, 2, 7, 7, 8, 8, 9, 16])
    m = calcular_metricas(res)
    assert m["makespan"] == 16
    assert m["tiempo_espera_promedio"] == pytest.approx(0.125)
    assert m["tareas_por_servidor"] == {0: 2, 1: 2, 2: 2, 3: 2}


def test_escenario_a_aleatoria_semilla_1042():
    res = corrida(p8(), A, "aleatoria")
    assert columnas(res)[0] == [1, 1, 2, 0, 2, 2, 3, 3]
    m = calcular_metricas(res)
    assert m["tiempo_espera_promedio"] == pytest.approx(1.375)
    assert m["makespan"] == 17


def test_escenario_b_round_robin():
    res = corrida(p8(), B, "round_robin")
    assert columnas(res) == ([0, 1, 2, 3, 0, 1, 2, 3], [0, 1, 2, 3, 4, 5, 12, 7], [2, 2, 12, 7, 8, 8, 16, 16])
    m = calcular_metricas(res)
    assert m["makespan"] == 16
    assert m["tiempo_espera_promedio"] == pytest.approx(0.75)


def test_escenario_b_menor_carga_evita_el_servidor_lento():
    res = corrida(p8(), B, "menor_carga")
    assert columnas(res) == ([0, 1, 2, 3, 0, 1, 3, 0], [0, 1, 2, 3, 4, 5, 7, 8], [2, 2, 12, 7, 8, 8, 9, 17])
    m = calcular_metricas(res)
    assert m["makespan"] == 17
    assert m["tiempo_espera_promedio"] == pytest.approx(0.25)
    assert m["tareas_por_servidor"] == {0: 3, 1: 2, 2: 1, 3: 2}


@pytest.mark.parametrize("estrategia, servidores, inicios, fines", [
    ("round_robin", [0, 1, 3, 0, 1, 3, 0, 1], [0, 1, 3, 3, 4, 8, 7, 8], [2, 2, 8, 7, 8, 11, 9, 17]),
    ("menor_carga", [0, 1, 3, 0, 1, 0, 1, 3], [0, 1, 3, 3, 4, 7, 8, 8], [2, 2, 8, 7, 8, 10, 10, 17]),
])
def test_escenario_c_caida_y_reasignacion(estrategia, servidores, inicios, fines):
    res = corrida(p8(), C, estrategia)
    assert columnas(res) == (servidores, inicios, fines)
    m = calcular_metricas(res)
    assert m["makespan"] == 17
    assert m["tiempo_espera_promedio"] == pytest.approx(0.75)
    assert m["tareas_reasignadas"] == 1
    assert m["tareas_por_servidor"] == {0: 3, 1: 3, 2: 0, 3: 2}
    caida = next(e for e in res.eventos if e.tipo == "CAIDA")
    assert (caida.tiempo, caida.servidor_id) == (2, 2)
    pendiente = next(e for e in res.eventos if e.tipo == "PENDIENTE_REASIGNACION")
    assert pendiente.tarea_id == 2 and "5.0" in pendiente.detalle
    reasignacion = next(e for e in res.eventos if e.tipo == "REASIGNACION")
    assert (reasignacion.tiempo, reasignacion.tarea_id, reasignacion.servidor_id) == (3, 2, 3)


@pytest.mark.parametrize("estrategia", ["round_robin", "menor_carga"])
def test_configuracion_de_8_tareas_con_intervalo_2_no_discrimina(estrategia):
    parametros = p8(intervalo_llegada=2, umbral_sobrecarga=15)
    a = calcular_metricas(corrida(parametros, A, estrategia))
    assert a["tiempo_espera_promedio"] == 0 and a["makespan"] == 23
    c = calcular_metricas(corrida(parametros, C, estrategia))
    assert c["tareas_reasignadas"] == 1 and c["makespan"] == 23
    assert c["tiempo_espera_promedio"] == pytest.approx(0.125)