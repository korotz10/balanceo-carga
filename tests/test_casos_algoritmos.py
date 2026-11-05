"""Casos de prueba de los algoritmos de asignación (calculados a mano)."""
from types import SimpleNamespace

import pytest

from src.algorithms import (
    Aleatoria,
    EstrategiaAsignacion,
    MenorCarga,
    NoServidoresDisponiblesError,
    RoundRobin,
    crear_estrategia,
)


def srv(i, carga=0.0):
    """Servidor de mentira: los algoritmos solo leen .id y .carga."""
    return SimpleNamespace(id=i, carga=carga)


def ids(estrategia, servidores, n):
    """Pide n asignaciones seguidas (n tareas, una por llamada) y devuelve los ids elegidos."""
    return [estrategia.asignar(None, servidores).id for _ in range(n)]


# ---------------- Round Robin ----------------
def test_rr_orden_circular():
    assert ids(RoundRobin(), [srv(0), srv(1), srv(2), srv(3)], 8) == [0, 1, 2, 3, 0, 1, 2, 3]

def test_rr_salta_servidor_caido():
    assert ids(RoundRobin(), [srv(0), srv(1), srv(3)], 6) == [0, 1, 3, 0, 1, 3]

def test_rr_ultimo_elegido_deja_de_estar_disponible():
    rr = RoundRobin()
    assert ids(rr, [srv(0), srv(1), srv(2), srv(3)], 3) == [0, 1, 2]
    assert ids(rr, [srv(0), srv(1), srv(3)], 2) == [3, 0]

def test_rr_vuelve_al_inicio_si_no_hay_id_mayor():
    rr = RoundRobin()
    ids(rr, [srv(0), srv(1), srv(2), srv(3)], 4)  # el último elegido es el 3
    assert ids(rr, [srv(0), srv(1), srv(2)], 1) == [0]

def test_rr_lista_desordenada():
    assert ids(RoundRobin(), [srv(3), srv(1), srv(0), srv(2)], 8) == [0, 1, 2, 3, 0, 1, 2, 3]

def test_rr_un_solo_servidor():
    assert ids(RoundRobin(), [srv(2)], 5) == [2, 2, 2, 2, 2]

def test_rr_no_mira_la_carga():
    assert ids(RoundRobin(), [srv(0, 1000), srv(1), srv(2), srv(3)], 1) == [0]

def test_rr_instancias_independientes():
    servidores = [srv(0), srv(1), srv(2)]
    assert ids(RoundRobin(), servidores, 1) == ids(RoundRobin(), servidores, 1) == [0]

def test_rr_lista_vacia():
    with pytest.raises(NoServidoresDisponiblesError):
        RoundRobin().asignar(None, [])


# ---------------- Menor Carga ----------------
def test_mc_minimo_unico():
    assert ids(MenorCarga(), [srv(0, 5), srv(1, 2), srv(2, 7), srv(3, 3)], 1) == [1]

def test_mc_empate_total_rota():
    assert ids(MenorCarga(), [srv(0), srv(1), srv(2), srv(3)], 5) == [0, 1, 2, 3, 0]

def test_mc_empate_parcial():
    assert ids(MenorCarga(), [srv(0, 5), srv(1, 2), srv(2, 7), srv(3, 2)], 3) == [1, 3, 1]

def test_mc_rotacion_continua_desde_el_ultimo_elegido():
    mc = MenorCarga()
    assert ids(mc, [srv(0, 5), srv(1, 2), srv(2, 7), srv(3, 3)], 1) == [1]
    assert ids(mc, [srv(0, 1), srv(1, 1), srv(2, 1), srv(3, 1)], 1) == [2]

def test_mc_considera_la_carga_ya_dividida_por_capacidad():
    # carga = pendiente / capacidad. A: 6 / 1.0 = 6.  B: 4 / 0.5 = 8  -> gana A
    assert ids(MenorCarga(), [srv(0, 6.0), srv(1, 8.0)], 1) == [0]
    # A: 6.  B: 2 / 0.5 = 4  -> gana B
    assert ids(MenorCarga(), [srv(0, 6.0), srv(1, 4.0)], 1) == [1]

def test_mc_lista_vacia():
    with pytest.raises(NoServidoresDisponiblesError):
        MenorCarga().asignar(None, [])


# ---------------- Aleatoria ----------------
def test_aleatoria_reproducible_con_misma_semilla():
    s = [srv(0), srv(1), srv(2), srv(3)]
    assert ids(Aleatoria(42), s, 20) == ids(Aleatoria(42), s, 20)

def test_aleatoria_semillas_distintas_dan_secuencias_distintas():
    s = [srv(0), srv(1), srv(2), srv(3)]
    assert ids(Aleatoria(1), s, 20) != ids(Aleatoria(2), s, 20)

def test_aleatoria_respeta_los_disponibles():
    assert set(ids(Aleatoria(42), [srv(1), srv(3)], 200)) <= {1, 3}

def test_aleatoria_aproximadamente_uniforme():
    elegidos = ids(Aleatoria(42), [srv(0), srv(1), srv(2), srv(3)], 4000)
    for i in range(4):
        assert 900 <= elegidos.count(i) <= 1100

def test_aleatoria_no_mira_la_carga():
    assert 0 in ids(Aleatoria(42), [srv(0, 1000), srv(1), srv(2), srv(3)], 400)

def test_aleatoria_lista_vacia():
    with pytest.raises(NoServidoresDisponiblesError):
        Aleatoria(42).asignar(None, [])


# ---------------- Fábrica e interfaz ----------------
def test_fabrica_y_nombres():
    assert isinstance(crear_estrategia("round_robin"), RoundRobin)
    assert isinstance(crear_estrategia("menor_carga"), MenorCarga)
    assert isinstance(crear_estrategia("aleatoria"), Aleatoria)
    assert crear_estrategia("round_robin").nombre == "Round Robin"
    assert crear_estrategia("menor_carga").nombre == "Menor Carga"
    assert crear_estrategia("aleatoria").nombre == "Aleatoria"

def test_fabrica_nombre_invalido():
    with pytest.raises(ValueError):
        crear_estrategia("xyz")

def test_fabrica_aleatoria_con_semilla():
    s = [srv(0), srv(1), srv(2), srv(3)]
    assert ids(crear_estrategia("aleatoria", 7), s, 20) == ids(crear_estrategia("aleatoria", 7), s, 20)

def test_interfaz_es_abstracta():
    with pytest.raises(TypeError):
        EstrategiaAsignacion()


# ---------------- Mini caso: 2 servidores, tareas de duración 5, 3, 2, 4 ----------------
def repartir(estrategia, duraciones, n_servidores=2):
    """Imita al motor: asigna y suma la duración a la carga del servidor elegido."""
    servidores = [srv(i) for i in range(n_servidores)]
    for d in duraciones:
        estrategia.asignar(None, servidores).carga += d
    return [s.carga for s in servidores]

def test_minicaso_round_robin():
    assert repartir(RoundRobin(), [5, 3, 2, 4]) == [7, 7]

def test_minicaso_menor_carga():
    # T1->S0, T2->S1, T3->S1 (3<5), T4->S0 (empate 5 y 5, rota a S0): S0=5+4, S1=3+2
    assert repartir(MenorCarga(), [5, 3, 2, 4]) == [9, 5]