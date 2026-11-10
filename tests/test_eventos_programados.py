"""Cálculo manual: una tarea de 3 unidades falla tras 1 tick,
espera hasta la recuperación en t=2 y termina en t=5.
"""

import pytest

from src.algorithms import RoundRobin
from src.bitacora import generar_bitacora
from src.engine import (
    EventoProgramado,
    SistemaCaidoError,
    ejecutar_simulacion,
)
from src.models import EstadoServidor, Servidor, Tarea


def _correr(
    tareas: list[Tarea],
    servidores: list[Servidor],
    eventos: list[EventoProgramado],
    *,
    historial: bool = False,
    umbral: float = 100.0,
):
    return ejecutar_simulacion(
        tareas,
        servidores,
        RoundRobin(),
        umbral_sobrecarga=umbral,
        eventos_programados=eventos,
        registrar_historial=historial,
    )


def test_historial_no_cambia_resultados_ni_eventos():
    tareas = [Tarea(0, 5), Tarea(1, 2, 1)]
    eventos = [EventoProgramado(1, 0, "DEGRADACION", 0.5)]
    sin_historial = _correr(tareas, [Servidor(0)], eventos)
    con_historial = _correr(tareas, [Servidor(0)], eventos, historial=True)

    assert sin_historial.eventos == con_historial.eventos
    assert sin_historial.registros == con_historial.registros
    assert sin_historial.historial is None
    assert con_historial.historial


def test_caidas_en_ticks_distintos_conservan_y_completan_todas_las_tareas():
    tareas = [Tarea(id_, 6) for id_ in range(9)]
    resultado = _correr(
        tareas,
        [Servidor(id_) for id_ in range(3)],
        [
            EventoProgramado(0, 0, "CAIDA"),
            EventoProgramado(2, 1, "CAIDA"),
        ],
    )

    assert len(resultado.registros) == len(tareas)
    assert len({registro.tarea_id for registro in resultado.registros}) == len(tareas)
    assert [evento.tiempo for evento in resultado.eventos if evento.tipo == "CAIDA"] == [0, 2]
    assert resultado.tareas_reasignadas >= 2


def test_caidas_simultaneas_preservan_trabajo_restante():
    resultado = _correr(
        [Tarea(id_, 5) for id_ in range(6)],
        [Servidor(id_) for id_ in range(3)],
        [
            EventoProgramado(0, 0, "CAIDA"),
            EventoProgramado(0, 1, "CAIDA"),
        ],
    )
    reasignaciones = [
        evento
        for evento in resultado.eventos
        if evento.tipo == "PENDIENTE_REASIGNACION"
    ]

    assert len(resultado.registros) == 6
    assert len(reasignaciones) >= 2
    trabajos_restantes = {evento.detalle.rsplit("con ", 1)[1] for evento in reasignaciones}
    assert "4.0 unidades restantes" in trabajos_restantes
    assert "5.0 unidades restantes" in trabajos_restantes


def test_servidor_recuperado_recibe_tareas_pendientes():
    resultado = _correr(
        [Tarea(0, 3), Tarea(1, 1, 1), Tarea(2, 1, 2)],
        [Servidor(0)],
        [
            EventoProgramado(0, 0, "CAIDA"),
            EventoProgramado(2, 0, "RECUPERACION"),
        ],
    )

    assert len(resultado.registros) == 3
    assert any(evento.tipo == "RECUPERACION_SERVIDOR" for evento in resultado.eventos)
    reasignacion = next(
        evento for evento in resultado.eventos
        if evento.tipo == "REASIGNACION" and evento.tarea_id == 0
    )
    assert reasignacion.tiempo == 3
    assert resultado.makespan == 7


def test_todas_las_caidas_esperan_hasta_recuperacion_del_tick_actual():
    resultado = _correr(
        [Tarea(0, 1), Tarea(1, 1, 1)],
        [Servidor(0)],
        [
            EventoProgramado(0, 0, "CAIDA"),
            EventoProgramado(1, 0, "RECUPERACION"),
        ],
        historial=True,
    )

    assert len(resultado.registros) == 2
    assert resultado.historial is not None
    tick_recuperacion = next(
        entrada for entrada in resultado.historial if entrada.tick == 1
    )
    assert tick_recuperacion.servidores[0].estado == EstadoServidor.ACTIVO.value


def test_sistema_caido_incluye_estado_parcial_si_no_hay_recuperacion():
    with pytest.raises(SistemaCaidoError, match="no quedan servidores") as captura:
        _correr(
            [Tarea(0, 3), Tarea(1, 1, 1)],
            [Servidor(0)],
            [EventoProgramado(0, 0, "CAIDA")],
        )

    assert captura.value.tick == 1
    assert captura.value.tareas_pendientes == [0, 1]
    assert any(evento.tipo == "CAIDA" for evento in captura.value.eventos)


def test_degradacion_modifica_duracion_y_marca_sobrecarga():
    resultado = _correr(
        [Tarea(0, 4)],
        [Servidor(0)],
        [EventoProgramado(0, 0, "DEGRADACION", 0.5)],
        umbral=5,
    )

    assert resultado.makespan == 7
    assert any(evento.tipo == "DEGRADACION" for evento in resultado.eventos)
    assert any(evento.tipo == "SOBRECARGA" for evento in resultado.eventos)


@pytest.mark.parametrize(
    "evento",
    [
        EventoProgramado(-1, 0, "CAIDA"),
        EventoProgramado(0, 4, "CAIDA"),
        EventoProgramado(0, 0, "DESCONOCIDO"),
        EventoProgramado(0, 0, "DEGRADACION"),
        EventoProgramado(0, 0, "DEGRADACION", 0),
        EventoProgramado(0, 0, "DEGRADACION", 1),
    ],
)
def test_eventos_invalidos_lanzan_value_error(evento):
    with pytest.raises(ValueError):
        _correr([Tarea(0, 1)], [Servidor(0)], [evento])


def test_bitacora_narra_eventos_reales_en_formato_espanol():
    resultado = _correr(
        [Tarea(0, 1)],
        [Servidor(0)],
        [EventoProgramado(0, 0, "DEGRADACION", 0.5)],
    )

    bitacora = generar_bitacora(resultado)
    assert bitacora
    assert all(linea.startswith("t=") and " · " in linea for linea in bitacora)
    assert any("degradación de capacidad" in linea for linea in bitacora)
