"""Cálculo de métricas para los resultados de simulación."""

from statistics import pstdev
from typing import Any

from src.engine import ResultadoSimulacion


def calcular_metricas(resultado: ResultadoSimulacion) -> dict[str, Any]:
    """Calcula métricas de ejecución, distribución y espera."""
    servidores = sorted(resultado.servidores, key=lambda servidor: servidor.id)
    tareas_por_servidor = {
        servidor.id: sum(
            1 for registro in resultado.registros if registro.servidor_id == servidor.id
        )
        for servidor in servidores
    }
    carga_por_servidor = {
        servidor.id: sum(
            registro.duracion for registro in resultado.registros if registro.servidor_id == servidor.id
        )
        for servidor in servidores
    }
    cargas = list(carga_por_servidor.values())
    esperas = [
        max(0, registro.tiempo_inicio_proceso - registro.tiempo_llegada)
        for registro in resultado.registros
    ]
    espera_cola = [
        registro.tiempo_espera_disponibilidad for registro in resultado.registros
    ]
    sobrecargas_por_servidor = {
        servidor.id: sum(
            1 for evento in resultado.eventos if evento.tipo == "SOBRECARGA" and evento.servidor_id == servidor.id
        )
        for servidor in servidores
    }

    return {
        "escenario": resultado.nombre_escenario,
        "estrategia": resultado.nombre_estrategia,
        "tareas_completadas": len(resultado.registros),
        "tareas_por_servidor": tareas_por_servidor,
        "carga_por_servidor": carga_por_servidor,
        "desviacion_estandar_carga": pstdev(cargas) if len(cargas) > 1 else 0.0,
        "makespan": resultado.makespan,
        "tiempo_espera_promedio": sum(esperas) / len(esperas) if esperas else 0.0,
        "sobrecargas_por_servidor": sobrecargas_por_servidor,
        "sobrecargas_total": sum(sobrecargas_por_servidor.values()),
        "tiempo_espera_cola_promedio": sum(espera_cola) / len(espera_cola) if espera_cola else 0.0,
        "tiempo_espera_cola_maximo": max(espera_cola, default=0),
        "tareas_reasignadas": resultado.tareas_reasignadas,
    }
