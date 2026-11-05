"""Distribución de las 100 tareas y regresión contra las tablas del README."""
import pytest

from src.metrics import calcular_metricas
from src.scenarios import ejecutar_todos
from tests.conftest import parametros_base

A, B, C = "A - Normal", "B - Sobrecarga", "C - Falla"
ESTRATEGIAS = ("round_robin", "menor_carga", "aleatoria")


def promedios(parametros):
    """{(escenario, estrategia): {metrica: promedio de las repeticiones}}"""
    salida = {}
    for clave, ejecuciones in ejecutar_todos(parametros).items():
        ms = [calcular_metricas(r) for r in ejecuciones]
        salida[clave] = {k: sum(m[k] for m in ms) / len(ms) for k in
                         ("tiempo_espera_promedio", "sobrecargas_total", "makespan", "tareas_reasignadas",
                          "desviacion_estandar_carga", "desviacion_ocupacion")}
    return salida


@pytest.fixture(scope="module")
def base():
    return promedios(parametros_base())


@pytest.fixture(scope="module")
def sin_proteccion():
    return promedios(parametros_base(umbral_sobrecarga=1000))


# ---------- distribución de tareas (100 tareas, 1 repetición, sin protección) ----------
@pytest.fixture(scope="module")
def una_corrida():
    parametros = parametros_base(umbral_sobrecarga=1000, repeticiones=1)
    return {k: calcular_metricas(v[0]) for k, v in ejecutar_todos(parametros).items()}


@pytest.mark.parametrize("escenario, estrategia, esperado", [
    (A, "round_robin", {0: 25, 1: 25, 2: 25, 3: 25}),
    (A, "menor_carga", {0: 26, 1: 26, 2: 25, 3: 23}),
    (A, "aleatoria", {0: 20, 1: 33, 2: 23, 3: 24}),
    (B, "round_robin", {0: 25, 1: 25, 2: 25, 3: 25}),
    (B, "menor_carga", {0: 29, 1: 28, 2: 15, 3: 28}),
])
def test_tareas_por_servidor(una_corrida, escenario, estrategia, esperado):
    assert una_corrida[(escenario, estrategia)]["tareas_por_servidor"] == esperado


def test_suma_de_duraciones_semilla_42(una_corrida):
    assert sum(una_corrida[(A, "round_robin")]["carga_por_servidor"].values()) == 509


# ---------- regresión contra el README (umbral 12, 30 repeticiones) ----------
README = {  # (espera, sobrecargas, makespan)
    (A, "round_robin"): (0.456, 0.90, 204.97), (A, "menor_carga"): (0.048, 0.00, 204.47), (A, "aleatoria"): (3.008, 19.57, 210.30),
    (B, "round_robin"): (2.109, 16.73, 212.70), (B, "menor_carga"): (0.277, 6.70, 205.87), (B, "aleatoria"): (3.974, 31.13, 211.73),
}


@pytest.mark.parametrize("clave", list(README))
def test_regresion_a_y_b(base, clave):
    espera, sobrecargas, makespan = README[clave]
    v = base[clave]
    assert v["tiempo_espera_promedio"] == pytest.approx(espera, abs=0.002)
    assert v["sobrecargas_total"] == pytest.approx(sobrecargas, abs=0.006)
    assert v["makespan"] == pytest.approx(makespan, abs=0.006)


@pytest.mark.parametrize("estrategia, sobrecargas, makespan, reasignadas, espera_antigua", [
    ("round_robin", 10.90, 210.03, 1.17, 1.923),
    ("menor_carga", 3.43, 206.17, 1.00, 0.841),
    ("aleatoria", 30.73, 211.93, 2.20, 4.365),
])
def test_regresion_c(base, estrategia, sobrecargas, makespan, reasignadas, espera_antigua):
    v = base[(C, estrategia)]
    assert v["sobrecargas_total"] == pytest.approx(sobrecargas, abs=0.006)
    assert v["makespan"] == pytest.approx(makespan, abs=0.006)
    assert v["tareas_reasignadas"] == pytest.approx(reasignadas, abs=0.006)
    # tras corregir el inicio obsoleto la espera sube ligeramente (en mi réplica: +0.007 a +0.053)
    assert espera_antigua - 0.002 <= v["tiempo_espera_promedio"] <= espera_antigua + 0.1


@pytest.mark.parametrize("escenario, estrategia, esperado", [
    (A, "round_robin", 11.270), (A, "menor_carga", 7.596), (A, "aleatoria", 16.412),
    (B, "round_robin", 27.342), (B, "menor_carga", 13.201), (B, "aleatoria", 22.872),
    (C, "round_robin", 10.694), (C, "menor_carga", 5.740), (C, "aleatoria", 13.434),
])
def test_desviacion_ocupacion(base, escenario, estrategia, esperado):
    assert base[(escenario, estrategia)]["desviacion_ocupacion"] == pytest.approx(esperado, abs=0.01)


def test_en_a_las_dos_desviaciones_coinciden(base):
    for estrategia in ESTRATEGIAS:
        v = base[(A, estrategia)]
        assert v["desviacion_ocupacion"] == pytest.approx(v["desviacion_estandar_carga"])


# ---------- sin protección de sobrecarga (umbral 1000) ----------
@pytest.mark.parametrize("escenario, estrategia, espera", [
    (A, "round_robin", 0.456), (A, "menor_carga", 0.048), (A, "aleatoria", 4.650),
    (B, "round_robin", 9.931), (B, "menor_carga", 0.277), (B, "aleatoria", 15.753),
])
def test_sin_proteccion_espera(sin_proteccion, escenario, estrategia, espera):
    v = sin_proteccion[(escenario, estrategia)]
    assert v["tiempo_espera_promedio"] == pytest.approx(espera, abs=0.002)
    assert v["sobrecargas_total"] == 0


@pytest.mark.parametrize("estrategia, makespan", [("round_robin", 281.5), ("menor_carga", 205.9), ("aleatoria", 294.1)])
def test_sin_proteccion_makespan_en_b(sin_proteccion, estrategia, makespan):
    assert sin_proteccion[(B, estrategia)]["makespan"] == pytest.approx(makespan, abs=0.06)


def test_menor_carga_es_la_mas_equilibrada_en_b_medido_por_ocupacion(sin_proteccion):
    ocupacion = {e: sin_proteccion[(B, e)]["desviacion_ocupacion"] for e in ESTRATEGIAS}
    assert ocupacion["menor_carga"] < ocupacion["round_robin"] < ocupacion["aleatoria"]