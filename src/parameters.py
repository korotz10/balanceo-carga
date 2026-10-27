"""Parámetros explícitos de una ejecución de simulación."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParametrosSimulacion:
    num_tareas: int
    num_servidores: int
    duracion_min: int
    duracion_max: int
    intervalo_llegada: int
    umbral_sobrecarga: float
    tarea_falla: int
    servidor_falla: int
    servidor_lento: int
    capacidad_reducida: float
    semilla: int
    repeticiones: int

    def validar(self) -> None:
        """Lanza ValueError con todos los parámetros inconsistentes."""
        errores: list[str] = []
        if self.num_tareas <= 0:
            errores.append("NUM_TAREAS debe ser mayor que 0")
        if self.num_servidores <= 0:
            errores.append("NUM_SERVIDORES debe ser mayor que 0")
        if self.duracion_min <= 0 or self.duracion_max < self.duracion_min:
            errores.append("Se requiere 0 < DURACION_MIN <= DURACION_MAX")
        if self.intervalo_llegada <= 0:
            errores.append("INTERVALO_LLEGADA debe ser mayor que 0")
        if self.umbral_sobrecarga <= 0:
            errores.append("UMBRAL_SOBRECARGA debe ser mayor que 0")
        if self.tarea_falla <= 0 or self.tarea_falla > self.num_tareas:
            errores.append("TAREA_FALLA debe estar entre 1 y NUM_TAREAS")
        for nombre, servidor_id in (
            ("SERVIDOR_FALLA", self.servidor_falla),
            ("SERVIDOR_LENTO", self.servidor_lento),
        ):
            if servidor_id < 0 or servidor_id >= self.num_servidores:
                errores.append(
                    f"{nombre} debe estar entre 0 y NUM_SERVIDORES - 1"
                )
        if not 0 < self.capacidad_reducida < 1:
            errores.append("CAPACIDAD_REDUCIDA debe estar entre 0 y 1")
        if self.repeticiones <= 0:
            errores.append("REPETICIONES debe ser mayor que 0")
        if errores:
            raise ValueError("Parámetros inválidos:\n" + "\n".join(errores))
