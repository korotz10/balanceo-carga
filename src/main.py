"""Punto de entrada de línea de comandos para la simulación."""

import argparse
import logging
from pathlib import Path
from collections.abc import Callable

from src import config
from src.algorithms import Aleatoria, EstrategiaAsignacion, crear_estrategia
from src.engine import ResultadoSimulacion
from src.models import Tarea
from src.scenarios import (
    ResultadosPorCombinacion,
    ejecutar_escenario_a,
    ejecutar_escenario_b,
    ejecutar_escenario_c,
    ejecutar_todos,
)
from src.task_generator import generar_tareas
from src.report import generar_csv, generar_excel, generar_graficas

EjecutorEscenario = Callable[
    [list[Tarea], EstrategiaAsignacion, float],
    ResultadoSimulacion,
]
ESCENARIOS: dict[str, tuple[str, EjecutorEscenario]] = {
    "a": ("A - Normal", ejecutar_escenario_a),
    "b": ("B - Sobrecarga", ejecutar_escenario_b),
    "c": ("C - Falla", ejecutar_escenario_c),
}
ESTRATEGIAS = ("round_robin", "menor_carga", "aleatoria")


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simula y compara estrategias de balanceo de carga."
    )
    parser.add_argument(
        "--escenario",
        choices=(*ESCENARIOS, "all"),
        default="a",
        help="Escenario: a (normal), b (sobrecarga), c (falla) o all.",
    )
    parser.add_argument(
        "--estrategia",
        choices=(*ESTRATEGIAS, "all"),
        default="round_robin",
        help="Estrategia de asignación o all.",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=None,
        help="Semilla para generación de tareas y estrategia aleatoria.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecuta las nueve combinaciones y repite la estrategia aleatoria.",
    )
    parser.add_argument(
        "--resultados",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "results",
        help="Directorio de salida (por defecto: results/).",
    )
    parser.add_argument("--verbose", action="store_true", help="Activa logs detallados.")
    return parser.parse_args()


def _ejecutar_seleccion(
    escenario: str,
    estrategia_nombre: str,
    semilla: int,
) -> ResultadosPorCombinacion:
    tareas = generar_tareas(
        cantidad=config.NUM_TAREAS,
        duracion_min=config.DURACION_MIN,
        duracion_max=config.DURACION_MAX,
        semilla=semilla,
        intervalo_llegada=config.INTERVALO_LLEGADA,
    )
    resultados: ResultadosPorCombinacion = {}
    escenarios = list(ESCENARIOS) if escenario == "all" else [escenario]
    estrategias = list(ESTRATEGIAS) if estrategia_nombre == "all" else [estrategia_nombre]
    for escenario_id in escenarios:
        nombre_escenario, ejecutar = ESCENARIOS[escenario_id]
        for nombre_estrategia in estrategias:
            repeticiones = (
                config.REPETICIONES_ALEATORIA
                if nombre_estrategia == "aleatoria"
                else 1
            )
            ejecuciones: list[ResultadoSimulacion] = []
            for indice in range(repeticiones):
                estrategia = (
                    Aleatoria(semilla + indice)
                    if nombre_estrategia == "aleatoria"
                    else crear_estrategia(nombre_estrategia, semilla)
                )
                resultado = ejecutar(
                    tareas,
                    estrategia,
                    config.UMBRAL_SOBRECARGA,
                )
                ejecuciones.append(resultado)
            resultados[(nombre_escenario, ejecuciones[0].nombre_estrategia)] = (
                ejecuciones if len(ejecuciones) > 1 else ejecuciones[0]
            )
    return resultados


def main() -> int:
    argumentos = _argumentos()
    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config.validar_configuracion()
    semilla = config.SEMILLA if argumentos.semilla is None else argumentos.semilla

    if argumentos.all:
        resultados = ejecutar_todos(semilla=semilla)
    else:
        resultados = _ejecutar_seleccion(
            argumentos.escenario,
            argumentos.estrategia,
            semilla,
        )

    argumentos.resultados.mkdir(parents=True, exist_ok=True)
    generar_csv(resultados, argumentos.resultados / "resumen.csv")
    generar_excel(resultados, argumentos.resultados / "resumen.xlsx")
    generar_graficas(resultados, argumentos.resultados / "graficas")
    logging.getLogger(__name__).info(
        "Simulación terminada. Archivos guardados en %s", argumentos.resultados
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
