"""Cálculo de métricas para los resultados de simulación."""

from statistics import pstdev
from typing import Any

from src.engine import ResultadoSimulacion


def calcular_metricas(resultado: ResultadoSimulacion) -> dict[str, Any]:
    """Calcula métricas de ejecución, distribución y espera."""
    servidores = sorted(resultado.servidores, key=lambda servidor: servidor.id)
    tareas_por_servidor = {
        servidor.id: sum(
            registro.servidor_id == servidor.id for registro in resultado.registros
        )
        for servidor in servidores
    }
    carga_por_servidor = {
        servidor.id: sum(
            registro.duracion
            for registro in resultado.registros
            if registro.servidor_id == servidor.id
        )
        for servidor in servidores
    }
    cargas = list(carga_por_servidor.values())
    esperas = [
        registro.tiempo_inicio_proceso - registro.tiempo_llegada
        for registro in resultado.registros
    ]

    return {
        "escenario": resultado.nombre_escenario,
        "estrategia": resultado.nombre_estrategia,
        "tareas_completadas": len(resultado.registros),
        "tareas_por_servidor": tareas_por_servidor,
        "carga_por_servidor": carga_por_servidor,
        "desviacion_estandar_carga": pstdev(cargas) if len(cargas) > 1 else 0.0,
        "makespan": resultado.makespan,
        "tiempo_espera_promedio": sum(esperas) / len(esperas) if esperas else 0.0,
        "tareas_reasignadas": resultado.tareas_reasignadas,
    }
