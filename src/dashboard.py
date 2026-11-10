"""Panel Streamlit para resultados oficiales y exploración del simulador."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

RAIZ_PROYECTO = str(Path(__file__).resolve().parents[1])
if RAIZ_PROYECTO not in sys.path:
    sys.path.insert(0, RAIZ_PROYECTO)

from src.algorithms import Aleatoria, MenorCarga, RoundRobin
from src.bitacora import generar_bitacora
from src.config import crear_parametros_por_defecto
from src.engine import (
    ConfiguracionFalla,
    EventoProgramado,
    ResultadoSimulacion,
    SistemaCaidoError,
    ejecutar_simulacion,
)
from src.metrics import calcular_metricas
from src.models import Servidor, Tarea
from src.parameters import ParametrosSimulacion
from src.scenarios import (
    crear_servidores_normales,
    crear_servidores_sobrecarga,
    ejecutar_todos,
)
from src.task_generator import generar_tareas
from src.visual import color_estado, color_estrategia, color_tarea, icono_evento

_NOMBRES_ESTRATEGIA = {
    "round_robin": "Round Robin",
    "menor_carga": "Menor Carga",
    "aleatoria": "Aleatoria",
}


def _ejecuciones(valor: ResultadoSimulacion | list[ResultadoSimulacion]) -> list[ResultadoSimulacion]:
    return valor if isinstance(valor, list) else [valor]


def _resumen_por_resultado(resultados: dict) -> pd.DataFrame:
    filas: list[dict] = []
    for (escenario, estrategia), valor in resultados.items():
        metricas = [calcular_metricas(resultado) for resultado in _ejecuciones(valor)]
        filas.append({
            "escenario": escenario,
            "estrategia": estrategia,
            "ejecuciones": len(metricas),
            "tareas_completadas": min(m["tareas_completadas"] for m in metricas),
            "makespan_promedio": sum(m["makespan"] for m in metricas) / len(metricas),
            "desviacion_estandar_carga_promedio": sum(
                m["desviacion_estandar_carga"] for m in metricas
            ) / len(metricas),
            "desviacion_ocupacion": sum(
                m["desviacion_ocupacion"] for m in metricas
            ) / len(metricas),
            "tiempo_espera_promedio": sum(
                m["tiempo_espera_promedio"] for m in metricas
            ) / len(metricas),
            "tareas_reasignadas_promedio": sum(
                m["tareas_reasignadas"] for m in metricas
            ) / len(metricas),
            "sobrecargas_total_promedio": sum(
                m["sobrecargas_total"] for m in metricas
            ) / len(metricas),
            "tiempo_espera_cola_promedio": sum(
                m["tiempo_espera_cola_promedio"] for m in metricas
            ) / len(metricas),
            "tiempo_espera_cola_maximo": sum(
                m["tiempo_espera_cola_maximo"] for m in metricas
            ) / len(metricas),
        })
    return pd.DataFrame(filas)


def _estilos_mejores(tabla: pd.DataFrame) -> pd.DataFrame:
    """Devuelve estilos para resaltar el mejor valor por escenario."""
    estilos = pd.DataFrame("", index=tabla.index, columns=tabla.columns)
    metricas = (
        "makespan_promedio",
        "desviacion_estandar_carga_promedio",
        "desviacion_ocupacion",
        "tiempo_espera_promedio",
        "tareas_reasignadas_promedio",
        "sobrecargas_total_promedio",
        "tiempo_espera_cola_promedio",
    )
    for metrica in metricas:
        if metrica not in tabla.columns:
            continue
        escenarios = (
            ["C - Falla"]
            if metrica == "tareas_reasignadas_promedio"
            else tabla["escenario"].unique()
        )
        for escenario in escenarios:
            indices = tabla.index[tabla["escenario"] == escenario]
            if len(indices) == 0:
                continue
            minimo = tabla.loc[indices, metrica].min()
            ganadores = indices[
                tabla.loc[indices, metrica].map(
                    lambda valor: math.isclose(valor, minimo)
                )
            ]
            estilos.loc[ganadores, metrica] = "background-color: #5353ec"
    return estilos


def _best_by_metric(tabla: pd.DataFrame) -> dict[str, str]:
    mejores: dict[str, str] = {}
    for columna, etiqueta in (
        ("makespan_promedio", "Makespan"),
        ("desviacion_estandar_carga_promedio", "Desviación estándar de carga"),
        ("desviacion_ocupacion", "Desviación de ocupación"),
        ("tiempo_espera_promedio", "Tiempo promedio de espera"),
        ("tareas_reasignadas_promedio", "Tareas reasignadas"),
        ("sobrecargas_total_promedio", "Sobrecargas"),
        ("tiempo_espera_cola_promedio", "Tiempo medio en cola"),
    ):
        if columna not in tabla.columns:
            continue
        escenarios = (
            ["C - Falla"]
            if columna == "tareas_reasignadas_promedio"
            else tabla["escenario"].unique()
        )
        for escenario in escenarios:
            datos = tabla[tabla["escenario"] == escenario]
            if not datos.empty:
                fila = datos.loc[datos[columna].idxmin()]
                mejores[f"{etiqueta} — {escenario}"] = fila["estrategia"]
    return mejores


def _colores_estrategias(nombres: list[str]) -> dict[str, str]:
    return {
        nombre: color_estrategia(
            _NOMBRES_ESTRATEGIA.get(nombre, nombre)
        )
        for nombre in nombres
    }


def _grafica_comparativa(resultados: dict) -> None:
    tabla = _resumen_por_resultado(resultados)
    if tabla.empty:
        return
    escenarios = tabla["escenario"].drop_duplicates().tolist()
    escenario = st.selectbox("Escenario", escenarios, key="comparativa_escenario")
    subset = tabla[tabla["escenario"] == escenario]
    color_map = _colores_estrategias(subset["estrategia"].tolist())
    fig = px.bar(
        subset,
        x="estrategia",
        y="makespan_promedio",
        color="estrategia",
        color_discrete_map=color_map,
        labels={"estrategia": "Estrategia", "makespan_promedio": "Makespan promedio"},
        title=f"Tiempo total por estrategia — {escenario}",
        template="plotly_dark",
    )
    st.plotly_chart(fig, use_container_width=True)

    metrica_labels = {
        "Makespan": "makespan_promedio",
        "Desviación de carga": "desviacion_estandar_carga_promedio",
        "Desviación de ocupación": "desviacion_ocupacion",
        "Espera promedio": "tiempo_espera_promedio",
        "Sobrecargas": "sobrecargas_total_promedio",
    }
    metrica = st.selectbox("Métrica comparativa", list(metrica_labels), key="metrica_comparativa")
    fig_metricas = px.bar(
        tabla,
        x="escenario",
        y=metrica_labels[metrica],
        color="estrategia",
        barmode="group",
        color_discrete_map=_colores_estrategias(tabla["estrategia"].tolist()),
        labels={metrica_labels[metrica]: metrica},
        title=metrica,
        template="plotly_dark",
    )
    st.plotly_chart(fig_metricas, use_container_width=True)
    _grafica_carga_servidores(resultados)


def _grafica_carga_servidores(resultados: dict) -> None:
    tabla_resumen = _resumen_por_resultado(resultados)
    escenarios = tabla_resumen["escenario"].drop_duplicates().tolist()
    escenario = st.selectbox(
        "Escenario para carga por servidor",
        escenarios,
        key="carga_servidores_escenario",
    )
    filas = []
    for (nombre_escenario, estrategia), valor in resultados.items():
        if nombre_escenario != escenario:
            continue
        metricas_corridas = [
            calcular_metricas(resultado) for resultado in _ejecuciones(valor)
        ]
        servidor_ids = sorted({
            servidor_id
            for metricas in metricas_corridas
            for servidor_id in metricas["carga_por_servidor"]
        })
        for servidor_id in servidor_ids:
            filas.append({
                "servidor": f"S{servidor_id}",
                "estrategia": estrategia,
                "carga_promedio": sum(
                    metrica["carga_por_servidor"].get(servidor_id, 0)
                    for metrica in metricas_corridas
                ) / len(metricas_corridas),
            })
    if filas:
        fig = px.bar(
            pd.DataFrame(filas),
            x="servidor",
            y="carga_promedio",
            color="estrategia",
            barmode="group",
            color_discrete_map=_colores_estrategias(
                [fila["estrategia"] for fila in filas]
            ),
            title=f"Carga promedio por servidor — {escenario}",
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)


def _crear_figura_gantt(resultado: ResultadoSimulacion) -> go.Figure | None:
    """Construye la línea de tiempo usando ticks numéricos, no fechas."""
    if not resultado.registros:
        return None

    servidores = sorted({registro.servidor_id for registro in resultado.registros})
    fig = go.Figure()
    for registro in resultado.registros:
        inicio = registro.tiempo_inicio_proceso
        fin = max(registro.tiempo_fin, inicio + 0.1)
        nombre_servidor = f"S{registro.servidor_id}"
        fig.add_trace(go.Bar(
            x=[fin - inicio],
            y=[nombre_servidor],
            base=[inicio],
            orientation="h",
            name=f"Tarea {registro.tarea_id}",
            marker_color=color_tarea(registro.tarea_id),
            customdata=[[registro.tarea_id, inicio, fin, registro.duracion]],
            hovertemplate=(
                "Tarea %{customdata[0]}<br>"
                "Servidor %{y}<br>"
                "Inicio: t=%{customdata[1]}<br>"
                "Fin: t=%{customdata[2]}<br>"
                "Duración original: %{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        ))

    for evento in resultado.eventos:
        if evento.tipo not in {
            "CAIDA", "SOBRECARGA", "RECUPERACION_SERVIDOR",
            "RECUPERACION", "DEGRADACION", "RESTAURACION",
        } or evento.servidor_id < 0:
            continue
        fig.add_trace(go.Scatter(
            x=[evento.tiempo],
            y=[f"S{evento.servidor_id}"],
            mode="markers",
            name=f"{icono_evento(evento.tipo)} {evento.tipo}",
            marker={
                "size": 12,
                "color": "#EF4444" if evento.tipo == "CAIDA" else "#F59E0B",
                "symbol": "x" if evento.tipo == "CAIDA" else "diamond",
            },
            hovertext=[evento.detalle],
            hoverinfo="text",
        ))

    fin_tiempo = max(
        (registro.tiempo_fin for registro in resultado.registros),
        default=resultado.makespan,
    )
    fig.update_layout(
        title="Trabajo procesado por servidor",
        template="plotly_dark",
        barmode="overlay",
        xaxis={
            "title": "Tiempo simulado (ticks)",
            "type": "linear",
            "rangemode": "tozero",
            "range": [0, max(fin_tiempo, 1)],
            "dtick": max(1, round(fin_tiempo / 20)),
        },
        yaxis={
            "title": "Servidor",
            "categoryorder": "array",
            "categoryarray": [f"S{id_}" for id_ in reversed(servidores)],
        },
    )
    return fig


def _grafica_gantt(resultado: ResultadoSimulacion) -> None:
    fig = _crear_figura_gantt(resultado)
    if fig is None:
        st.info("La ejecución no completó tareas para mostrar en el Gantt.")
        return
    st.plotly_chart(fig, use_container_width=True)


def _graficas_historial(resultado: ResultadoSimulacion, key: str) -> None:
    historial = resultado.historial or []
    if not historial:
        st.info("No hay historial tick a tick para esta ejecución.")
        return
    filas = [
        {
            "tick": registro.tick,
            "servidor": f"S{servidor.servidor_id}",
            "carga": servidor.carga,
            "estado": servidor.estado,
        }
        for registro in historial
        for servidor in registro.servidores
    ]
    fig_carga = px.line(
        pd.DataFrame(filas),
        x="tick",
        y="carga",
        color="servidor",
        markers=True,
        title="Carga pendiente por servidor",
        template="plotly_dark",
    )
    st.plotly_chart(fig_carga, use_container_width=True, key=f"{key}_carga")

    espera = pd.DataFrame([
        {"tick": registro.tick, "tareas_en_espera": len(registro.cola_espera)}
        for registro in historial
    ])
    fig_espera = px.line(
        espera,
        x="tick",
        y="tareas_en_espera",
        markers=True,
        title="Cola de espera",
        template="plotly_dark",
    )
    st.plotly_chart(fig_espera, use_container_width=True, key=f"{key}_espera")


def _tabla_eventos(resultado: ResultadoSimulacion) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "tick": evento.tiempo,
            "tipo": evento.tipo,
            "evento": f"{icono_evento(evento.tipo)} {evento.tipo}",
            "servidor": evento.servidor_id,
            "tarea": evento.tarea_id,
            "detalle": evento.detalle,
        }
        for evento in resultado.eventos
    ])


def _mostrar_distribucion(resultados: dict) -> None:
    escenarios = list(dict.fromkeys(escenario for escenario, _ in resultados))
    escenario = st.selectbox(
        "Escenario de distribución", escenarios, key="distribucion_escenario"
    )
    estrategias = [
        estrategia for nombre_escenario, estrategia in resultados
        if nombre_escenario == escenario
    ]
    estrategia = st.selectbox(
        "Estrategia de distribución",
        estrategias,
        key="distribucion_estrategia",
    )
    ejecuciones = _ejecuciones(resultados[(escenario, estrategia)])
    corrida = st.selectbox(
        "Repetición",
        range(1, len(ejecuciones) + 1),
        key="distribucion_repeticion",
    )
    resultado = ejecuciones[corrida - 1]
    conteo_tareas = {
        servidor.id: sum(
            registro.servidor_id == servidor.id for registro in resultado.registros
        )
        for servidor in sorted(resultado.servidores, key=lambda servidor: servidor.id)
    }
    fig = px.bar(
        x=[f"S{servidor_id}" for servidor_id in conteo_tareas],
        y=list(conteo_tareas.values()),
        labels={"x": "Servidor", "y": "Tareas completadas"},
        title=f"Tareas completadas por servidor — {escenario} / {estrategia}",
        template="plotly_dark",
    )
    st.plotly_chart(fig, use_container_width=True)
    tareas = pd.DataFrame(
        [
            {
                "id": registro.tarea_id,
                "duracion": registro.duracion,
                "llegada": registro.tiempo_llegada,
                "servidor": registro.servidor_id,
                "inicio": registro.tiempo_inicio_proceso,
                "fin": registro.tiempo_fin,
                "espera": max(
                    0, registro.tiempo_inicio_proceso - registro.tiempo_llegada
                ),
                "reasignada": registro.reasignada,
            }
            for registro in sorted(resultado.registros, key=lambda registro: registro.tarea_id)
        ],
        columns=[
            "id", "duracion", "llegada", "servidor",
            "inicio", "fin", "espera", "reasignada",
        ],
    )
    st.dataframe(tareas, use_container_width=True)


def _crear_traza(
    parametros: ParametrosSimulacion,
    escenario: str,
    estrategia_id: str,
) -> ResultadoSimulacion:
    tareas = generar_tareas(
        cantidad=parametros.num_tareas,
        duracion_min=parametros.duracion_min,
        duracion_max=parametros.duracion_max,
        semilla=parametros.semilla,
        intervalo_llegada=parametros.intervalo_llegada,
    )
    if escenario == "B - Sobrecarga":
        servidores = crear_servidores_sobrecarga(
            parametros.num_servidores,
            parametros.servidor_lento,
            parametros.capacidad_reducida,
        )
    else:
        servidores = crear_servidores_normales(parametros.num_servidores)
    config_falla = None
    if escenario == "C - Falla":
        config_falla = ConfiguracionFalla(
            parametros.tarea_falla,
            parametros.servidor_falla,
            elegir_mas_cargado=True,
        )
    estrategias = {
        "round_robin": RoundRobin(),
        "menor_carga": MenorCarga(),
        "aleatoria": Aleatoria(parametros.semilla + 1_000),
    }
    return ejecutar_simulacion(
        tareas,
        servidores,
        estrategias[estrategia_id],
        umbral_sobrecarga=parametros.umbral_sobrecarga,
        config_falla=config_falla,
        nombre_escenario=escenario,
        registrar_historial=True,
    )


def _configurar_parametros() -> tuple[ParametrosSimulacion, bool, list[str], list[str]]:
    base = crear_parametros_por_defecto()
    with st.sidebar:
        st.header("Configuración")
        with st.expander("Simulación", expanded=True):
            preset = st.selectbox(
                "Preset",
                ["Personalizado", "Rápido", "Carga alta"],
                help="Punto de partida para explorar; no modifica los resultados oficiales.",
                key="preset_oficial",
            )
            if st.button("Aplicar preset", key="aplicar_preset_oficial"):
                ajustes = {
                    "Rápido": {
                        "tareas_oficiales": 12,
                        "repeticiones_oficiales": 1,
                    },
                    "Carga alta": {
                        "tareas_oficiales": 150,
                        "intervalo_oficial": 1,
                        "repeticiones_oficiales": 5,
                    },
                }.get(preset, {})
                st.session_state.update(ajustes)
            num_tareas = st.number_input(
                "Número de tareas", min_value=1, value=int(base.num_tareas), step=1,
                help="Cantidad de trabajos generados en cada repetición.",
                key="tareas_oficiales",
            )
            num_servidores = st.number_input(
                "Servidores", min_value=1, value=int(base.num_servidores), step=1,
                key="servidores_oficiales",
            )
            ejecutar = st.button(
                "Ejecutar resultados oficiales", type="primary", key="ejecutar_oficial"
            )
        with st.expander("Carga"):
            duracion_min = st.number_input(
                "Duración mínima", min_value=1, value=int(base.duracion_min), step=1,
                key="duracion_min_oficial",
            )
            duracion_max = st.number_input(
                "Duración máxima", min_value=1, value=int(base.duracion_max), step=1,
                key="duracion_max_oficial",
            )
            intervalo_llegada = st.number_input(
                "Intervalo entre llegadas",
                min_value=1,
                value=int(base.intervalo_llegada),
                step=1,
                help="Ticks entre llegadas consecutivas.",
                key="intervalo_oficial",
            )
        with st.expander("Escenarios"):
            escenarios = st.multiselect(
                "Escenarios oficiales",
                ["A - Normal", "B - Sobrecarga", "C - Falla"],
                default=["A - Normal", "B - Sobrecarga", "C - Falla"],
            )
            estrategias = st.multiselect(
                "Estrategias oficiales",
                list(_NOMBRES_ESTRATEGIA),
                default=list(_NOMBRES_ESTRATEGIA),
                format_func=lambda valor: _NOMBRES_ESTRATEGIA[valor],
            )
        with st.expander("Avanzado"):
            umbral = st.number_input(
                "Umbral de sobrecarga",
                min_value=0.1,
                value=float(base.umbral_sobrecarga),
                step=0.5,
                help="Carga máxima objetivo antes de marcar un servidor sobrecargado.",
            )
            semilla = st.number_input("Semilla", value=int(base.semilla), step=1)
            st.session_state["tarea_falla_oficial"] = min(
                int(st.session_state.get("tarea_falla_oficial", base.tarea_falla)),
                int(num_tareas),
            )
            st.session_state["servidor_falla_oficial"] = min(
                int(st.session_state.get("servidor_falla_oficial", base.servidor_falla)),
                int(num_servidores) - 1,
            )
            st.session_state["servidor_lento_oficial"] = min(
                int(st.session_state.get("servidor_lento_oficial", base.servidor_lento)),
                int(num_servidores) - 1,
            )
            repeticiones = st.number_input(
                "Repeticiones", min_value=1, value=int(base.repeticiones), step=1,
                key="repeticiones_oficiales",
            )
            tarea_falla = st.number_input(
                "Tarea que dispara la falla",
                min_value=1,
                max_value=int(num_tareas),
                value=min(int(base.tarea_falla), int(num_tareas)),
                step=1,
                key="tarea_falla_oficial",
            )
            servidor_falla = st.number_input(
                "Servidor de desempate",
                min_value=0,
                value=min(int(base.servidor_falla), int(num_servidores) - 1),
                max_value=int(num_servidores) - 1,
                step=1,
                key="servidor_falla_oficial",
            )
            servidor_lento = st.number_input(
                "Servidor lento",
                min_value=0,
                value=min(int(base.servidor_lento), int(num_servidores) - 1),
                max_value=int(num_servidores) - 1,
                step=1,
                key="servidor_lento_oficial",
            )
            capacidad_reducida = st.number_input(
                "Capacidad reducida",
                min_value=0.1,
                max_value=0.99,
                value=float(base.capacidad_reducida),
                step=0.05,
            )

    parametros = ParametrosSimulacion(
        num_tareas=int(num_tareas),
        num_servidores=int(num_servidores),
        duracion_min=int(duracion_min),
        duracion_max=int(duracion_max),
        intervalo_llegada=int(intervalo_llegada),
        umbral_sobrecarga=float(umbral),
        tarea_falla=int(tarea_falla),
        servidor_falla=int(servidor_falla),
        servidor_lento=int(servidor_lento),
        capacidad_reducida=float(capacidad_reducida),
        semilla=int(semilla),
        repeticiones=int(repeticiones),
    )
    return parametros, ejecutar, escenarios, estrategias


def _mostrar_resultados_oficiales(resultados: dict) -> None:
    tabla = _resumen_por_resultado(resultados)
    if tabla.empty:
        st.info("Ejecuta la simulación desde la barra lateral para ver resultados.")
        return
    st.dataframe(tabla.style.apply(_estilos_mejores, axis=None), use_container_width=True)
    metricas = _best_by_metric(tabla)
    columnas = st.columns(3)
    for indice, (metrica, estrategia) in enumerate(metricas.items()):
        columnas[indice % len(columnas)].metric(metrica, estrategia)
    _grafica_comparativa(resultados)
    with st.expander("Distribución por servidor y detalle de tareas"):
        _mostrar_distribucion(resultados)


def _mostrar_eventos(resultados: dict) -> None:
    opciones = [
        (escenario, estrategia, ejecuciones[0])
        for (escenario, estrategia), valor in resultados.items()
        for ejecuciones in [_ejecuciones(valor)]
        if ejecuciones
    ]
    if not opciones:
        st.info("No hay ejecuciones disponibles.")
        return
    etiqueta_a_resultado = {
        f"{escenario} / {estrategia}": resultado
        for escenario, estrategia, resultado in opciones
    }
    seleccion = st.selectbox("Ejecución", list(etiqueta_a_resultado), key="eventos_ejecucion")
    resultado = etiqueta_a_resultado[seleccion]
    _grafica_gantt(resultado)
    eventos = _tabla_eventos(resultado)
    if eventos.empty:
        st.info("Esta ejecución no registró eventos.")
    else:
        col_tipo, col_servidor, col_tarea = st.columns(3)
        tipo = col_tipo.selectbox(
            "Tipo de evento",
            ["todos"] + sorted(eventos["tipo"].unique().tolist()),
            key="filtro_tipo_evento",
        )
        servidor = col_servidor.selectbox(
            "Servidor",
            ["todos"] + sorted(eventos["servidor"].unique().tolist()),
            key="filtro_servidor_evento",
        )
        tarea = col_tarea.selectbox(
            "Tarea",
            ["todos"] + sorted(eventos["tarea"].unique().tolist()),
            key="filtro_tarea_evento",
        )
        filtro = eventos.copy()
        if tipo != "todos":
            filtro = filtro[filtro["tipo"] == tipo]
        if servidor != "todos":
            filtro = filtro[filtro["servidor"] == servidor]
        if tarea != "todos":
            filtro = filtro[filtro["tarea"] == tarea]
        st.dataframe(filtro.drop(columns=["tipo"]), use_container_width=True)
    with st.expander("Bitácora explicada"):
        for linea in generar_bitacora(resultado):
            st.write(linea)


def _mostrar_reproduccion(parametros: ParametrosSimulacion) -> None:
    st.markdown("Selecciona una ejecución y prepárala para recorrer el estado tick a tick.")
    escenarios = ["A - Normal", "B - Sobrecarga", "C - Falla"]
    escenario = st.selectbox("Escenario", escenarios, key="replay_escenario")
    estrategia = st.selectbox(
        "Estrategia",
        list(_NOMBRES_ESTRATEGIA),
        format_func=lambda valor: _NOMBRES_ESTRATEGIA[valor],
        key="replay_estrategia",
    )
    if st.button("Preparar reproducción", key="preparar_reproduccion"):
        try:
            st.session_state["resultado_reproduccion"] = _crear_traza(
                parametros, escenario, estrategia
            )
            st.session_state["tick_reproduccion"] = 0
            st.session_state["reproduccion_activa"] = False
        except SistemaCaidoError as error:
            st.error(str(error))
    resultado = st.session_state.get("resultado_reproduccion")
    if resultado is None or not resultado.historial:
        st.info("Prepara una reproducción para consultar sus ticks.")
        return

    def mostrar_frame() -> None:
        historial = resultado.historial
        max_tick = len(historial) - 1
        activa = st.session_state.get("reproduccion_activa", False)
        if activa:
            tick_actual = st.session_state.get("tick_reproduccion", 0)
            if tick_actual >= max_tick:
                st.session_state["tick_reproduccion"] = max_tick
                st.session_state["reproduccion_activa"] = False
                st.rerun()
            st.session_state["tick_reproduccion"] = min(tick_actual + 1, max_tick)

        botones = st.columns(4)
        if botones[0].button("⏸ Pausar" if activa else "▶ Reproducir", key="toggle_reproduccion"):
            st.session_state["reproduccion_activa"] = not activa
            st.rerun()
        if botones[1].button("◀ Tick anterior", key="tick_anterior"):
            st.session_state["reproduccion_activa"] = False
            st.session_state["tick_reproduccion"] = max(
                0, st.session_state.get("tick_reproduccion", 0) - 1
            )
        if botones[2].button("Siguiente tick ▶", key="tick_siguiente"):
            st.session_state["reproduccion_activa"] = False
            st.session_state["tick_reproduccion"] = min(
                max_tick, st.session_state.get("tick_reproduccion", 0) + 1
            )
        botones[3].caption("En reproducción" if activa else "En pausa")

        tick = st.slider(
            "Tick",
            min_value=0,
            max_value=max_tick,
            key="tick_reproduccion",
        )
        registro = historial[tick]
        st.subheader(f"Estado al cierre del tick {registro.tick}")
        tarjetas = st.columns(max(len(registro.servidores), 1))
        for indice, servidor in enumerate(registro.servidores):
            with tarjetas[indice]:
                st.markdown(f"**Servidor {servidor.servidor_id}**")
                st.markdown(
                    f"<span style='color:{color_estado(servidor.estado)}'>"
                    f"● {servidor.estado}</span>",
                    unsafe_allow_html=True,
                )
                st.progress(
                    min(
                        max(servidor.carga / max(parametros.umbral_sobrecarga, 1), 0),
                        1,
                    )
                )
                st.caption(
                    f"Carga {servidor.carga:.2f} · En proceso: "
                    f"{servidor.tarea_en_proceso if servidor.tarea_en_proceso is not None else '—'}"
                )
                st.caption(f"Cola: {servidor.tareas_en_cola}")
        st.write(f"Tareas esperando: {registro.cola_espera or 'ninguna'}")
        st.write(f"Llegadas del tick: {registro.llegadas or 'ninguna'}")
        _graficas_historial(resultado, "reproduccion")

    st.fragment(
        run_every=0.5 if st.session_state.get("reproduccion_activa", False) else None
    )(mostrar_frame)()


def _eventos_preset(nombre: str, numero_servidores: int) -> list[dict]:
    if nombre == "Falla y recuperación":
        return [
            {"tick": 5, "servidor_id": 0, "tipo": "CAIDA", "capacidad": None},
            {"tick": 9, "servidor_id": 0, "tipo": "RECUPERACION", "capacidad": None},
        ]
    if nombre == "Degradación y restauración":
        servidor = min(1, numero_servidores - 1)
        return [
            {"tick": 4, "servidor_id": servidor, "tipo": "DEGRADACION", "capacidad": 0.5},
            {"tick": 12, "servidor_id": servidor, "tipo": "RESTAURACION", "capacidad": None},
        ]
    return []


def _correr_laboratorio(
    tareas: list[Tarea],
    servidores: int,
    umbral: float,
    eventos: list[EventoProgramado],
    semilla: int,
) -> dict[str, ResultadoSimulacion | SistemaCaidoError]:
    estrategias = {
        "Round Robin": RoundRobin(),
        "Menor Carga": MenorCarga(),
        "Aleatoria": Aleatoria(semilla),
    }
    resultados: dict[str, ResultadoSimulacion | SistemaCaidoError] = {}
    for nombre, estrategia in estrategias.items():
        try:
            resultados[nombre] = ejecutar_simulacion(
                tareas=[Tarea(tarea.id, tarea.duracion, tarea.tiempo_llegada) for tarea in tareas],
                servidores=[Servidor(id=servidor_id) for servidor_id in range(servidores)],
                estrategia=estrategia,
                umbral_sobrecarga=umbral,
                nombre_escenario="Laboratorio",
                eventos_programados=list(eventos),
                registrar_historial=True,
            )
        except SistemaCaidoError as error:
            resultados[nombre] = error
    return resultados


def _grafica_rho(tareas: list[Tarea], servidores: int) -> None:
    por_tick: dict[int, float] = {}
    for tarea in tareas:
        por_tick[tarea.tiempo_llegada] = por_tick.get(tarea.tiempo_llegada, 0) + tarea.duracion
    trabajo_acumulado = 0.0
    filas = []
    capacidad_total = float(servidores)
    for tick in range(max(por_tick, default=0) + 1):
        trabajo_acumulado += por_tick.get(tick, 0)
        rho = trabajo_acumulado / ((tick + 1) * capacidad_total)
        filas.append({"tick": tick, "ρ": rho})
    st.plotly_chart(
        px.line(
            pd.DataFrame(filas),
            x="tick",
            y="ρ",
            markers=True,
            title="ρ aproximado en el tiempo (trabajo llegado / capacidad acumulada)",
            template="plotly_dark",
        ),
        use_container_width=True,
    )


def _mostrar_laboratorio(parametros: ParametrosSimulacion) -> None:
    st.warning("Resultados exploratorios: no forman parte de las tablas ni del CSV oficial.")
    with st.expander("Cómo reacciona cada estrategia"):
        st.markdown(
            "- **Round Robin:** rota entre servidores activos; no estima duración.\n"
            "- **Menor Carga:** escoge el servidor con menos trabajo pendiente relativo a su capacidad.\n"
            "- **Aleatoria:** elige entre servidores disponibles; la semilla permite reproducir la corrida."
        )
    columnas = st.columns(4)
    cantidad = columnas[0].number_input(
        "Tareas de laboratorio", min_value=1, max_value=500, value=30, step=1
    )
    numero_servidores = columnas[1].number_input(
        "Servidores", min_value=1, max_value=16, value=3, step=1
    )
    umbral = columnas[2].number_input(
        "Umbral", min_value=0.1, value=12.0, step=0.5
    )
    semilla = columnas[3].number_input("Semilla", value=42, step=1, key="semilla_laboratorio")

    preset = st.selectbox(
        "Preset de eventos",
        ["Sin eventos", "Falla y recuperación", "Degradación y restauración"],
        key="preset_eventos",
    )
    if st.button("Cargar preset", key="cargar_preset"):
        st.session_state["eventos_laboratorio"] = _eventos_preset(
            preset, int(numero_servidores)
        )
    st.session_state.setdefault("eventos_laboratorio", [])
    col_tick, col_srv, col_tipo, col_cap = st.columns(4)
    tick_evento = col_tick.number_input("Tick del evento", min_value=0, value=5, step=1)
    servidor_evento = col_srv.number_input(
        "Servidor afectado",
        min_value=0,
        max_value=int(numero_servidores) - 1,
        value=0,
        step=1,
    )
    tipo_evento = col_tipo.selectbox(
        "Tipo", ["CAIDA", "RECUPERACION", "DEGRADACION", "RESTAURACION"]
    )
    capacidad = col_cap.number_input(
        "Capacidad degradada",
        min_value=0.01,
        max_value=0.99,
        value=0.5,
        step=0.05,
        disabled=tipo_evento != "DEGRADACION",
    )
    acciones = st.columns(2)
    if acciones[0].button("Añadir evento", key="agregar_evento"):
        evento = {
            "tick": int(tick_evento),
            "servidor_id": int(servidor_evento),
            "tipo": tipo_evento,
            "capacidad": float(capacidad) if tipo_evento == "DEGRADACION" else None,
        }
        st.session_state["eventos_laboratorio"].append(evento)
    if acciones[1].button("Limpiar eventos", key="limpiar_eventos"):
        st.session_state["eventos_laboratorio"] = []

    eventos_dict = st.session_state["eventos_laboratorio"]
    if eventos_dict:
        st.dataframe(pd.DataFrame(eventos_dict), use_container_width=True)
    eventos = [
        EventoProgramado(**evento)
        for evento in eventos_dict
    ]
    if st.button("Ejecutar laboratorio", type="primary", key="ejecutar_laboratorio"):
        try:
            tareas = generar_tareas(
                cantidad=int(cantidad),
                duracion_min=parametros.duracion_min,
                duracion_max=parametros.duracion_max,
                semilla=int(semilla),
                intervalo_llegada=parametros.intervalo_llegada,
            )
            resultados = _correr_laboratorio(
                tareas, int(numero_servidores), float(umbral), eventos, int(semilla)
            )
            st.session_state["resultados_laboratorio"] = resultados
            st.session_state["tareas_laboratorio"] = tareas
            st.session_state["servidores_laboratorio"] = int(numero_servidores)
        except ValueError as error:
            st.error(f"No se pudo ejecutar el laboratorio: {error}")

    resultados = st.session_state.get("resultados_laboratorio")
    if not resultados:
        st.info("Configura eventos y ejecuta el laboratorio para comparar las tres estrategias.")
        return
    tareas = st.session_state["tareas_laboratorio"]
    numero_servidores = st.session_state["servidores_laboratorio"]
    columnas_resultado = st.columns(3)
    completos: list[tuple[str, ResultadoSimulacion, dict]] = []
    for columna, (nombre, resultado) in zip(columnas_resultado, resultados.items()):
        with columna:
            st.subheader(nombre)
            if isinstance(resultado, SistemaCaidoError):
                st.error(f"{resultado}. Tick {resultado.tick}.")
                st.metric("Tareas completadas", len(resultado.registros))
                st.caption(f"Pendientes: {resultado.tareas_pendientes}")
                st.dataframe(
                    pd.DataFrame([
                        {
                            "tick": evento.tiempo,
                            "tipo": evento.tipo,
                            "servidor": evento.servidor_id,
                            "detalle": evento.detalle,
                        }
                        for evento in resultado.eventos
                    ]),
                    use_container_width=True,
                )
                continue
            metricas = calcular_metricas(resultado)
            completos.append((nombre, resultado, metricas))
            st.metric("Makespan", metricas["makespan"])
            st.metric("Tareas completadas", metricas["tareas_completadas"])
            st.metric("Espera promedio", f"{metricas['tiempo_espera_promedio']:.2f}")
            st.caption(f"Reasignadas: {metricas['tareas_reasignadas']}")
            _grafica_gantt(resultado)
            _graficas_historial(resultado, f"lab_{nombre.replace(' ', '_')}")
            with st.expander("Bitácora"):
                for linea in generar_bitacora(resultado):
                    st.write(linea)
    _grafica_rho(tareas, numero_servidores)
    if completos:
        menor_makespan = min(completos, key=lambda item: item[2]["makespan"])
        menor_espera = min(completos, key=lambda item: item[2]["tiempo_espera_promedio"])
        st.info(
            f"Comparación automática: menor makespan de **{menor_makespan[0]}** "
            f"({menor_makespan[2]['makespan']} ticks); menor espera promedio de "
            f"**{menor_espera[0]}** ({menor_espera[2]['tiempo_espera_promedio']:.2f} ticks)."
        )


def main() -> None:
    st.set_page_config(
        layout="wide",
        page_title="⚖️ Balanceo de Carga",
        page_icon="⚖️",
    )
    st.title("Balanceo de carga")
    st.caption("Simulación discreta de estrategias, sobrecargas, fallas y recuperación.")
    parametros, ejecutar, escenarios, estrategias = _configurar_parametros()

    if ejecutar:
        try:
            parametros.validar()
            if not escenarios or not estrategias:
                raise ValueError("Selecciona al menos un escenario y una estrategia.")
            resultados = ejecutar_todos(
                parametros,
                escenarios_solicitados=escenarios,
                estrategias_solicitadas=estrategias,
            )
            st.session_state["resultados_simulacion"] = resultados
            st.session_state["parametros_ultima_simulacion"] = parametros
        except (ValueError, RuntimeError) as error:
            st.error(str(error))

    resultados = st.session_state.get("resultados_simulacion", {})
    parametros_vista = st.session_state.get("parametros_ultima_simulacion", parametros)
    resumen, eventos_tab, reproduccion_tab, laboratorio_tab = st.tabs(
        ["Resultados oficiales", "Eventos", "Reproducción", "Laboratorio"]
    )
    with resumen:
        if resultados:
            _mostrar_resultados_oficiales(resultados)
        else:
            st.info("Ejecuta una simulación desde la barra lateral para consultar los resultados oficiales.")
    with eventos_tab:
        if resultados:
            _mostrar_eventos(resultados)
        else:
            st.info("Los eventos de las corridas oficiales aparecerán aquí.")
    with reproduccion_tab:
        _mostrar_reproduccion(parametros_vista)
    with laboratorio_tab:
        _mostrar_laboratorio(parametros_vista)


if __name__ == "__main__":
    main()
