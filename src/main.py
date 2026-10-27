"""Punto de entrada de línea de comandos para la simulación."""

import argparse
import logging
from dataclasses import replace
from pathlib import Path

from src import config
from src.report import generar_csv, generar_excel, generar_graficas
from src.scenarios import ResultadosPorCombinacion, ejecutar_todos


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simula y compara estrategias de balanceo de carga."
    )
    parser.add_argument(
        "--escenario",
        choices=("a", "b", "c", "all"),
        default="a",
        help="Escenario: a (normal), b (sobrecarga), c (falla) o all.",
    )
    parser.add_argument(
        "--estrategia",
        choices=("round_robin", "menor_carga", "aleatoria", "all"),
        default="round_robin",
        help="Estrategia de asignación o all.",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=None,
        help="Semilla base para las corridas reproducibles.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecuta todas las combinaciones y repeticiones configuradas.",
    )
    parser.add_argument(
        "--resultados",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "results",
        help="Directorio de salida (por defecto: results/).",
    )
    parser.add_argument("--verbose", action="store_true", help="Activa logs detallados.")
    return parser.parse_args()


def ejecutar_desde_parametros(
    parametros,
    escenario: str = "all",
    estrategia: str = "all",
) -> ResultadosPorCombinacion:
    """Ejecuta la selección solicitada usando el mismo motor que el panel."""
    parametros.validar()
    escenarios_solicitados = None if escenario == "all" else [escenario]
    estrategias_solicitadas = None if estrategia == "all" else [estrategia]
    return ejecutar_todos(
        parametros,
        escenarios_solicitados=escenarios_solicitados,
        estrategias_solicitadas=estrategias_solicitadas,
    )


def main() -> int:
    argumentos = _argumentos()
    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parametros = config.PARAMETROS_POR_DEFECTO
    if argumentos.semilla is not None:
        parametros = replace(parametros, semilla=argumentos.semilla)
    parametros.validar()

    resultados = ejecutar_desde_parametros(
        parametros,
        escenario="all" if argumentos.all else argumentos.escenario,
        estrategia="all" if argumentos.all else argumentos.estrategia,
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
