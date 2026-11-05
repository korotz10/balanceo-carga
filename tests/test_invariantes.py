"""Invariantes que deben cumplirse siempre, en todos los escenarios y estrategias."""
import math

import pytest

from src.scenarios import ejecutar_todos
from tests.conftest import parametros_base

CONFIGURACIONES = {
    "base": dict(repeticiones=5),
    "umbral15": dict(repeticiones=5, umbral_sobrecarga=15),
    "intervalo1": dict(repeticiones=5, intervalo_llegada=1),
    "umbral5": dict(repeticiones=5, umbral_sobrecarga=5),
    "sin_proteccion_falla20": dict(
        repeticiones=5, umbral_sobrecarga=1000, intervalo_llegada=1, tarea_falla=20
    ),
}


@pytest.fixture(scope="module", params=list(CONFIGURACIONES))
def corridas(request):
    """Devuelve (parametros, lista de (escenario, estrategia, resultado))."""
    parametros = parametros_base(**CONFIGURACIONES[request.param])
    todas = []
    for (escenario, estrategia), ejecuciones in ejecutar_todos(parametros).items():
        for resultado in ejecuciones:
            todas.append((escenario, estrategia, resultado))
    return parametros, todas


def test_todas_las_tareas_se_completan_una_sola_vez(corridas):
    parametros, todas = corridas
    for _, _, res in todas:
        ids = sorted(r.tarea_id for r in res.registros)
        assert ids == list(range(parametros.num_tareas))


def test_ninguna_tarea_empieza_antes_de_llegar(corridas):
    _, todas = corridas
    for _, _, res in todas:
        for r in res.registros:
            assert r.tiempo_inicio_proceso >= r.tiempo_llegada
            assert r.tiempo_fin > r.tiempo_inicio_proceso


def test_duracion_en_servidor_es_duracion_sobre_capacidad(corridas):
    """Sin reasignación: fin - inicio == ceil(duración / capacidad)."""
    _, todas = corridas
    for _, _, res in todas:
        capacidad = {s.id: s.capacidad for s in res.servidores}
        for r in res.registros:
            if not r.reasignada:
                esperado = math.ceil(r.duracion / capacidad[r.servidor_id] - 1e-9)
                assert r.tiempo_fin - r.tiempo_inicio_proceso == esperado


def test_inicio_de_tareas_reasignadas_no_es_anterior_a_su_reasignacion(corridas):
    """Detecta el error del inicio_proceso obsoleto tras la caída de un servidor."""
    _, todas = corridas
    for _, _, res in todas:
        for r in res.registros:
            if r.reasignada:
                assert r.tiempo_inicio_proceso >= r.tiempo_asignacion


def test_un_servidor_no_procesa_dos_tareas_a_la_vez(corridas):
    _, todas = corridas
    for _, _, res in todas:
        por_servidor = {}
        for r in res.registros:
            if not r.reasignada:
                por_servidor.setdefault(r.servidor_id, []).append(r)
        for registros in por_servidor.values():
            registros.sort(key=lambda r: r.tiempo_inicio_proceso)
            for anterior, siguiente in zip(registros, registros[1:]):
                assert siguiente.tiempo_inicio_proceso >= anterior.tiempo_fin


def test_nunca_se_asigna_a_servidor_sobrecargado_o_caido(corridas):
    _, todas = corridas
    for _, _, res in todas:
        estado = {s.id: "ACTIVO" for s in res.servidores}
        for e in res.eventos:
            if e.tipo == "SOBRECARGA":
                estado[e.servidor_id] = "SOBRECARGADO"
            elif e.tipo == "RECUPERACION":
                estado[e.servidor_id] = "ACTIVO"
            elif e.tipo == "CAIDA":
                estado[e.servidor_id] = "CAIDO"
            elif e.tipo in ("ASIGNACION", "REASIGNACION"):
                assert estado[e.servidor_id] == "ACTIVO"


def test_solo_el_escenario_c_tiene_reasignaciones(corridas):
    _, todas = corridas
    for escenario, _, res in todas:
        if escenario != "C - Falla":
            assert res.tareas_reasignadas == 0
        assert res.tareas_reasignadas == sum(r.reasignada for r in res.registros)


def test_conservacion_real_del_trabajo(corridas):
    """La suma del trabajo procesado por los servidores es el trabajo total (incluye C)."""
    _, todas = corridas
    for _, _, res in todas:
        procesado = sum(s.trabajo_procesado for s in res.servidores)
        total = sum(r.duracion for r in res.registros)
        assert procesado == pytest.approx(total, rel=1e-9)