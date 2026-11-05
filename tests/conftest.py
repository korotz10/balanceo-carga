import pytest

from src.parameters import ParametrosSimulacion


BASE_PARAMETROS = {
    "num_tareas": 100,
    "num_servidores": 4,
    "duracion_min": 1,
    "duracion_max": 10,
    "intervalo_llegada": 2,
    "umbral_sobrecarga": 12,
    "tarea_falla": 50,
    "servidor_falla": 2,
    "servidor_lento": 2,
    "capacidad_reducida": 0.5,
    "semilla": 42,
    "repeticiones": 30,
}


def parametros_base(**overrides: object) -> ParametrosSimulacion:
    valores = {**BASE_PARAMETROS, **overrides}
    return ParametrosSimulacion(**valores)


crear_parametros_base = parametros_base


@pytest.fixture
def parametros_simulacion() -> ParametrosSimulacion:
    return parametros_base()
