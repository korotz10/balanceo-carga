# Simulación de balanceo de carga

Proyecto académico en Python que simula el reparto de tareas entre
servidores y compara Round Robin, Menor Carga y Aleatoria.

## 1. Objetivo

Observar cómo distintas estrategias afectan la distribución de trabajo,
el tiempo de espera y el tiempo total de procesamiento en escenarios
distribuidos simplificados.

## 2. Escenarios

- **A - Normal:** servidores con capacidad equivalente.
- **B - Sobrecarga:** un servidor tiene capacidad reducida.
- **C - Falla:** un servidor cae tras cierto número de asignaciones y sus
  tareas pendientes se reasignan.

## 3. Estrategias

- **Round Robin:** alterna por ID entre los servidores disponibles.
- **Menor Carga:** escoge el menor tiempo de trabajo estimado pendiente;
  desempata por ID.
- **Aleatoria:** escoge un servidor disponible con un generador reproducible.
  En `--all` se ejecutan varias semillas configurables.

## 4. Requisitos

- Python 3.10 o superior.
- Dependencias listadas en `requirements.txt`.

## 5. Instalación

Desde la carpeta raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

La copia de `.env` es opcional: si no existe, se aplican los valores por
defecto del código.

## 6. Configuración

Edita `.env` para configurar cantidad y duración de tareas, servidores,
semillas, umbral de sobrecarga, servidor que falla y repeticiones aleatorias.
Los valores se validan antes de iniciar la simulación.

## 7. Ejecución

```powershell
# Ejecuta A - Normal con Round Robin
python -m src.main

# Ejecuta un escenario y estrategia concretos
python -m src.main --escenario c --estrategia menor_carga

# Ejecuta todas las estrategias de un escenario
python -m src.main --escenario b --estrategia all

# Ejecuta todas las combinaciones
python -m src.main --all
```

Opciones disponibles:

```text
--escenario {a,b,c,all}
--estrategia {round_robin,menor_carga,aleatoria,all}
--semilla ENTERO
--all
--resultados DIRECTORIO
--verbose
```

## 8. Salidas

Los archivos se generan en `results/` (o en el directorio indicado con
`--resultados`):

- `resumen.csv`: una fila por combinación escenario/estrategia.
- `resumen.xlsx`: hojas `A`, `B` y `C` para los escenarios ejecutados.
- `graficas/`: carga por servidor por escenario y comparaciones de makespan
  y desviación estándar de carga.

Los resultados generados se excluyen de Git; se conserva `results/.gitkeep`.

## 9. Pruebas

```powershell
python -m pytest tests -v
```

## 10. Modelo de simulación

El motor usa un reloj discreto, sin esperas reales. Las tareas se procesan
en FIFO, y la duración consumida por tick depende de la capacidad del
servidor. Cada ejecución usa sus propias instancias de servidores y su
propio generador aleatorio.

## 11. Estructura

```text
src/
  algorithms.py      Estrategias de asignación
  config.py          Carga y validación de configuración
  engine.py          Reloj, procesamiento y eventos
  main.py            Interfaz de línea de comandos
  metrics.py         Métricas de resultados
  models.py          Tarea, servidor y estados
  report.py          CSV, Excel y gráficas
  scenarios.py       Configuración de escenarios
  task_generator.py  Tareas reproducibles
tests/               Pruebas automatizadas
docs/                Documentación de arquitectura
results/             Salidas generadas
```

## 12. Arquitectura y limitaciones

El diagrama del flujo de datos y el tratamiento de fallas están en
[docs/arquitectura.md](docs/arquitectura.md). Es una simulación educativa:
no crea procesos ni servidores reales, no incorpora tráfico de red y
modela la falla como un único evento. Las tareas que no pueden procesarse
por pérdida de todos los servidores causan un error explícito, no una
exportación parcial.
