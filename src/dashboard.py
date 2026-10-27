"""Dashboard interactivo con Streamlit para la simulación de balanceo de carga."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Streamlit ejecuta este archivo directamente y puede no incluir la raíz del proyecto.
RAIZ_PROYECTO = str(Path(__file__).resolve().parents[1])
if RAIZ_PROYECTO not in sys.path:
    sys.path.insert(0, RAIZ_PROYECTO)

from src.config import crear_parametros_por_defecto
from src.metrics import calcular_metricas
from src.parameters import ParametrosSimulacion
from src.scenarios import ejecutar_todos


def _opciones_escenarios() -> list[str]:
    return ["A - Normal", "B - Sobrecarga", "C - Falla"]


def _resumen_por_resultado(resultados: dict) -> pd.DataFrame:
    filas: list[dict] = []
    for (escenario, estrategia), ejecuciones in resultados.items():
        ejecuciones = ejecuciones if isinstance(ejecuciones, list) else [ejecuciones]
        metricas = [calcular_metricas(res) for res in ejecuciones]
        fila = {
            "escenario": escenario,
            "estrategia": estrategia,
            "ejecuciones": len(ejecuciones),
            "tareas_completadas": min(m["tareas_completadas"] for m in metricas),
            "makespan_promedio": sum(m["makespan"] for m in metricas) / len(metricas),
            "desviacion_estandar_carga_promedio": sum(
                m["desviacion_estandar_carga"] for m in metricas
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
        }
        filas.append(fila)
    return pd.DataFrame(filas)


def _estilos_mejores(tabla: pd.DataFrame) -> pd.DataFrame:
    estilos = pd.DataFrame("", index=tabla.index, columns=tabla.columns)
    metricas = (
        "makespan_promedio",
        "desviacion_estandar_carga_promedio",
        "tiempo_espera_promedio",
        "tareas_reasignadas_promedio",
        "sobrecargas_total_promedio",
        "tiempo_espera_cola_promedio",
    )
    for metrica in metricas:
        if metrica not in tabla.columns:
            continue
        escenarios = ["C - Falla"] if metrica == "tareas_reasignadas_promedio" else tabla["escenario"].unique()
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
        ("tiempo_espera_promedio", "Tiempo promedio de espera"),
        ("tareas_reasignadas_promedio", "Tareas reasignadas"),
        ("sobrecargas_total_promedio", "Sobrecargas"),
        ("tiempo_espera_cola_promedio", "Tiempo medio en cola"),
    ):
        if columna not in tabla.columns:
            continue
        escenarios = ["C - Falla"] if columna == "tareas_reasignadas_promedio" else tabla["escenario"].unique()
        for escenario in escenarios:
            datos = tabla[tabla["escenario"] == escenario]
            if datos.empty:
                continue
            fila = datos.loc[datos[columna].idxmin()]
            mejores[f"{etiqueta} — {escenario}"] = fila["estrategia"]
    return mejores


def _plot_carga_por_servidor(resultados: dict) -> None:
    tabla = _resumen_por_resultado(resultados)
    escenarios = tabla["escenario"].drop_duplicates().tolist()
    escenario = st.selectbox(
        "Escenario para la carga",
        escenarios,
        key="grafica_escenario_carga",
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    subset = tabla[tabla["escenario"] == escenario]
    ejecuciones_por_estrategia = []
    for _, fila in subset.iterrows():
        metricas = [calcular_metricas(r) for r in resultados[(fila["escenario"], fila["estrategia"])]]
        ejecuciones_por_estrategia.append((fila["estrategia"], metricas))

    servidores = sorted(
        {
            servidor_id
            for _, metricas in ejecuciones_por_estrategia
            for metrica in metricas
            for servidor_id in metrica["carga_por_servidor"]
        }
    )
    ancho = 0.8 / max(len(ejecuciones_por_estrategia), 1)
    posiciones = list(range(len(servidores)))
    for indice, (nombre_estrategia, metricas) in enumerate(ejecuciones_por_estrategia):
        cargas = [
            sum(metrica["carga_por_servidor"].get(servidor_id, 0) for metrica in metricas)
            / len(metricas)
            for servidor_id in servidores
        ]
        ax.bar(
            [posicion + (indice - (len(ejecuciones_por_estrategia) - 1) / 2) * ancho for posicion in posiciones],
            cargas,
            width=ancho,
            label=nombre_estrategia,
        )
    ax.set_title(f"Carga por servidor — {escenario}")
    ax.set_xlabel("Servidor")
    ax.set_ylabel("Carga promedio")
    ax.set_xticks(posiciones)
    ax.set_xticklabels([f"S{servidor_id}" for servidor_id in servidores])
    ax.legend(title="Estrategia", loc="upper left", bbox_to_anchor=(1.02, 1))
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    st.pyplot(fig)


def _plot_metricas_por_estrategia(resultados: dict) -> None:
    tabla = _resumen_por_resultado(resultados)
    etiquetas_metricas = {
        "Makespan": "makespan_promedio",
        "Desviación estándar de carga": "desviacion_estandar_carga_promedio",
        "Tiempo promedio de espera": "tiempo_espera_promedio",
        "Sobrecargas totales": "sobrecargas_total_promedio",
    }
    etiqueta_metrica = st.selectbox("Métrica", list(etiquetas_metricas))
    metric_key = etiquetas_metricas[etiqueta_metrica]
    fig, ax = plt.subplots(figsize=(10, 5))
    escenarios = tabla["escenario"].drop_duplicates().tolist()
    estrategias = tabla["estrategia"].drop_duplicates().tolist()
    x = list(range(len(escenarios)))
    ancho = 0.8 / max(len(estrategias), 1)
    for idx, estrategia in enumerate(estrategias):
        valores = [
            float(
                tabla[(tabla["escenario"] == escenario) & (tabla["estrategia"] == estrategia)][metric_key].iloc[0]
            )
            if not tabla[(tabla["escenario"] == escenario) & (tabla["estrategia"] == estrategia)].empty
            else 0.0
            for escenario in escenarios
        ]
        ax.bar(
            [pos + (idx - (len(estrategias) - 1) / 2) * ancho for pos in x],
            valores,
            width=ancho,
            label=estrategia,
        )
    ax.set_title(f"Comparación de {etiqueta_metrica.lower()}")
    ax.set_xlabel("Escenario")
    ax.set_ylabel(etiqueta_metrica)
    ax.set_xticks(x)
    ax.set_xticklabels(escenarios)
    ax.legend(title="Estrategia", loc="upper left", bbox_to_anchor=(1.02, 1))
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    st.pyplot(fig)


def _plot_gantt(resultado) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    servidores = sorted(resultado.servidores, key=lambda s: s.id)
    eventos_por_servidor = {servidor.id: [] for servidor in servidores}
    for registro in resultado.registros:
        if registro.servidor_id in eventos_por_servidor:
            eventos_por_servidor[registro.servidor_id].append(
                (registro.tiempo_inicio_proceso, registro.tiempo_fin, registro.tarea_id)
            )
    for idx, servidor in enumerate(servidores):
        y_base = len(servidores) - idx
        for inicio, fin, tarea_id in eventos_por_servidor[servidor.id]:
            ax.broken_barh(
                [(inicio, max(fin - inicio, 1))],
                (y_base - 0.35, 0.7),
                facecolors=plt.get_cmap("tab10")(tarea_id % 10),
                edgecolor="black",
                linewidth=0.4,
            )
        for evento in resultado.eventos:
            if evento.servidor_id == servidor.id and evento.tipo in {"SOBRECARGA", "CAIDA"}:
                prioridad = 0.25 if evento.tipo == "SOBRECARGA" else 0.5
                ax.axvspan(
                    evento.tiempo,
                    evento.tiempo + 1,
                    ymin=y_base - 0.5,
                    ymax=y_base + 0.5,
                    color="orange" if evento.tipo == "SOBRECARGA" else "red",
                    alpha=0.25 if evento.tipo == "SOBRECARGA" else 0.5,
                )
        ax.text(-0.2, y_base, f"S{servidor.id}", va="center", ha="right", fontsize=9)
    ax.set_ylim(0.5, len(servidores) + 0.5)
    ax.set_yticks([row for row in range(1, len(servidores) + 1)])
    ax.set_yticklabels([f"S{servidor.id}" for servidor in servidores])
    ax.set_xlabel("Tiempo")
    ax.set_title(f"Línea de tiempo — {resultado.nombre_escenario} / {resultado.nombre_estrategia}")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    st.pyplot(fig)


def _eventos_tabla(resultados: dict) -> pd.DataFrame:
    filas = []
    for (escenario, estrategia), ejecuciones in resultados.items():
        for numero_corrida, resultado in enumerate(ejecuciones, start=1):
            filas.extend(
                {
                    "escenario": escenario,
                    "estrategia": estrategia,
                    "corrida": numero_corrida,
                    "tiempo": evento.tiempo,
                    "tipo": evento.tipo,
                    "servidor_id": evento.servidor_id,
                    "tarea_id": evento.tarea_id,
                    "detalle": evento.detalle,
                }
                for evento in resultado.eventos
            )
    return pd.DataFrame(filas)


def _configurar_parametros() -> ParametrosSimulacion:
    base = crear_parametros_por_defecto()
    with st.sidebar:
        st.header("Parámetros")
        interval_llegada = st.number_input(
            "INTERVALO_LLEGADA",
            min_value=1,
            value=int(base.intervalo_llegada),
            step=1,
        )
        umbral = st.number_input(
            "UMBRAL_SOBRECARGA",
            min_value=1.0,
            value=float(base.umbral_sobrecarga),
            step=0.5,
        )
        semilla = st.number_input("SEMILLA", value=int(base.semilla), step=1)
        num_tareas = st.number_input("NUM_TAREAS", min_value=1, value=int(base.num_tareas), step=1)
        tarea_falla = st.number_input("TAREA_FALLA", min_value=1, value=int(base.tarea_falla), step=1)
        servidor_falla = st.number_input(
            "SERVIDOR_FALLA (desempate de carga)",
            min_value=0,
            max_value=max(base.num_servidores - 1, 0),
            value=int(base.servidor_falla),
            step=1,
        )
        servidor_lento = st.number_input("SERVIDOR_LENTO", min_value=0, max_value=max(base.num_servidores - 1, 0), value=int(base.servidor_lento), step=1)
        capacidad_reducida = st.number_input("CAPACIDAD_REDUCIDA", min_value=0.1, max_value=0.99, value=float(base.capacidad_reducida), step=0.05)
        repeticiones = st.number_input("REPETICIONES", min_value=1, value=int(base.repeticiones), step=1)
        st.caption("Los valores se validan antes de ejecutar la simulación.")
        ejecutar = st.button("Ejecutar simulación", type="primary")
    parametros = ParametrosSimulacion(
        num_tareas=int(num_tareas),
        num_servidores=base.num_servidores,
        duracion_min=base.duracion_min,
        duracion_max=base.duracion_max,
        intervalo_llegada=int(interval_llegada),
        umbral_sobrecarga=float(umbral),
        tarea_falla=int(tarea_falla),
        servidor_falla=int(servidor_falla),
        servidor_lento=int(servidor_lento),
        capacidad_reducida=float(capacidad_reducida),
        semilla=int(semilla),
        repeticiones=int(repeticiones),
    )
    return parametros, ejecutar


def main() -> None:
    st.set_page_config(page_title="Balanceo de carga", layout="wide")
    st.title("Simulación de balanceo de carga")

    parametros, ejecutar = _configurar_parametros()

    escenario = st.selectbox("Escenario", ["A - Normal", "B - Sobrecarga", "C - Falla", "Todos"], index=3)
    estrategia = st.selectbox("Estrategia", ["round_robin", "menor_carga", "aleatoria", "todas"], index=3)

    if ejecutar:
        try:
            parametros.validar()
            escenarios = None if escenario == "Todos" else [escenario]
            estrategias = None if estrategia == "todas" else [estrategia]
            st.session_state["resultados_simulacion"] = ejecutar_todos(
                parametros,
                escenarios_solicitados=escenarios,
                estrategias_solicitadas=estrategias,
            )
            st.session_state["parametros_ultima_simulacion"] = parametros
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return

    resultados = st.session_state.get("resultados_simulacion")
    if not resultados:
        st.info("Ajusta los parámetros y pulsa \"Ejecutar simulación\" para comparar estrategias.")
        return

    st.caption(
        "Se muestran los resultados de la última simulación. "
        "Cambiar pestañas o filtros no vuelve a ejecutar el motor; "
        "pulsa «Ejecutar simulación» para aplicar cambios de parámetros, escenario o estrategia."
    )
    resumen = _resumen_por_resultado(resultados)

    tab1, tab2, tab3, tab4 = st.tabs(["Resumen", "Gráficas", "Línea de tiempo", "Eventos"])

    with tab1:
        st.dataframe(
            resumen.style.apply(_estilos_mejores, axis=None),
            width="stretch",
        )
        mejores = _best_by_metric(resumen)
        for metrica, mejor in mejores.items():
            st.caption(f"{metrica}: mejor resultado en {mejor}.")

    with tab2:
        _plot_carga_por_servidor(resultados)
        _plot_metricas_por_estrategia(resultados)

    with tab3:
        candidatos = [
            (escenario_resultado, estrategia_resultado, ejecuciones[0])
            for (escenario_resultado, estrategia_resultado), ejecuciones in resultados.items()
            if ejecuciones
        ]
        if not candidatos:
            st.warning("No hay ejecuciones disponibles para mostrar la línea de tiempo.")
        else:
            etiquetas = {
                f"{nombre_escenario} / {nombre_estrategia}": resultado
                for nombre_escenario, nombre_estrategia, resultado in candidatos
            }
            seleccion = st.selectbox(
                "Ejecución (escenario / estrategia)",
                list(etiquetas),
                key="ejecucion_linea_tiempo",
            )
            _plot_gantt(etiquetas[seleccion])

    with tab4:
        eventos = _eventos_tabla(resultados)
        if eventos.empty:
            st.info("No hay eventos registrados.")
        else:
            tipo = st.selectbox(
                "Tipo de evento",
                ["todos"] + sorted(eventos["tipo"].unique().tolist()),
                key="filtro_tipo_evento",
            )
            servidor = st.selectbox(
                "Servidor",
                ["todos"] + sorted(eventos["servidor_id"].unique().tolist(), key=int),
                key="filtro_servidor_evento",
            )
            tarea = st.selectbox(
                "Tarea",
                ["todos"] + sorted(eventos["tarea_id"].unique().tolist(), key=int),
                key="filtro_tarea_evento",
            )
            filtro = eventos.copy()
            if tipo != "todos":
                filtro = filtro[filtro["tipo"] == tipo]
            if servidor != "todos":
                filtro = filtro[filtro["servidor_id"] == int(servidor)]
            if tarea != "todos":
                filtro = filtro[filtro["tarea_id"] == int(tarea)]
            st.dataframe(filtro, width="stretch")


if __name__ == "__main__":
    main()
