# Simulación de balanceo de carga en sistemas distribuidos

Proyecto académico en Python que simula la distribución de 100 tareas entre cuatro servidores y compara Round Robin, Menor Carga y Aleatoria. Los escenarios representan operación normal, capacidad heterogénea y caída de un servidor. El proyecto genera resultados CSV, Excel y PNG, y ofrece un panel interactivo con Streamlit.

## 1. Marco conceptual

Un modelo de estaciones de trabajo suele asignar trabajos a equipos que conservan autonomía local; un pool de procesadores reúne varios nodos que atienden trabajo común; un modelo híbrido combina ambas ideas. Esta simulación se parece principalmente a un pool de procesadores: las tareas llegan a un sistema compartido y se asignan entre servidores homogéneos o heterogéneos.

La asignación estática decide sin consultar la carga actual (Round Robin y Aleatoria); la dinámica consulta el estado de los servidores (Menor Carga). La asignación decide **a qué servidor** va una tarea. La planificación local decide **en qué orden** ese servidor la procesa; aquí se usa FIFO. El balanceo de carga busca distribuir el trabajo para evitar congestión y reducir espera.

## 2. Configuración de la simulación

La configuración documentada usa 100 tareas, cuatro servidores, duraciones entre 1 y 10, semilla base 42, 30 repeticiones, `INTERVALO_LLEGADA=2` y `UMBRAL_SOBRECARGA=12`. Para estas duraciones, la media teórica es `(1 + 10) / 2 = 5,5`.

La utilización aproximada se calcula como trabajo medio por intervalo de llegada dividido entre la capacidad total:

| Escenario | Capacidad efectiva | Utilización aproximada |
|---|---:|---:|
| A - Normal | 4 servidores | 5,5 / (4 × 2) = 68,75 % |
| B - Sobrecarga | 3,5 servidores equivalentes (uno a mitad de capacidad) | 5,5 / (3,5 × 2) = 78,57 % |
| C - Falla | 3 servidores después de la caída | 5,5 / (3 × 2) = 91,67 % |

El umbral 12 limita temporalmente nuevas asignaciones al servidor que supera esa carga estimada; el nodo sigue procesando y vuelve a estar disponible al recuperarse. En C, al alcanzarse `TAREA_FALLA`, cae el servidor con más trabajo pendiente; `SERVIDOR_FALLA` solo desempata si varios servidores tienen la misma carga pendiente.

## 3. Instalación, ejecución y salidas

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env

# Simulación completa
python -m src.main --all

# Pruebas automatizadas
python -m pytest tests -q

# Panel visual
streamlit run src/dashboard.py
```

Los archivos generados se guardan en `results/`: el resumen en CSV y Excel, y las gráficas PNG en `results/graficas/`; estas gráficas también se pueden consultar en el panel.

## 4. Resultados con los parámetros base

Estos resultados se generaron ejecutando `python -m src.main --all` con los parámetros base de `.env.example`: 100 tareas, cuatro servidores, semillas 42–71, 30 repeticiones, intervalo 2 y umbral 12. Cada combinación completó las 100 tareas. Cada celda `media ± σ` presenta la media y la desviación estándar poblacional entre las 30 corridas. La reasignación solo aplica a C.

| Escenario | Estrategia | Completadas | Makespan ± σ | Desv. carga ± σ | Desv. ocupación ± σ | Espera promedio ± σ | Reasignadas ± σ | Sobrecargas ± σ | Espera disponibilidad ± σ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A - Normal | Round Robin | 100 | 204,97 ± 2,09 | 11,27 ± 4,28 | 11,270 ± 4,284 | 0,456 ± 0,139 | — | 0,90 ± 1,22 | 0,0000 ± 0,0000 |
| A - Normal | Menor Carga | 100 | 204,47 ± 2,08 | 7,60 ± 3,18 | 7,596 ± 3,179 | 0,048 ± 0,028 | — | 0,00 ± 0,00 | 0,0000 ± 0,0000 |
| A - Normal | Aleatoria | 100 | 210,30 ± 4,17 | 16,41 ± 5,31 | 16,412 ± 5,308 | 3,008 ± 0,593 | — | 19,57 ± 6,77 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Round Robin | 100 | 212,70 ± 5,15 | 23,28 ± 4,00 | 27,342 ± 5,053 | 2,109 ± 0,388 | — | 16,73 ± 3,86 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Menor Carga | 100 | 205,87 ± 3,23 | 28,18 ± 2,92 | 13,201 ± 3,737 | 0,277 ± 0,126 | — | 6,70 ± 1,62 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Aleatoria | 100 | 211,73 ± 3,71 | 29,41 ± 7,29 | 22,872 ± 7,209 | 3,974 ± 0,762 | — | 31,13 ± 8,09 | 0,0000 ± 0,0000 |
| C - Falla | Round Robin | 100 | 210,03 ± 3,64 | 42,91 ± 5,86 | 10,694 ± 4,940 | 1,939 ± 0,747 | 1,17 ± 0,37 | 10,90 ± 8,06 | 0,0057 ± 0,0305 |
| C - Falla | Menor Carga | 100 | 206,17 ± 2,92 | 43,31 ± 4,48 | 5,740 ± 3,223 | 0,845 ± 0,554 | 1,00 ± 0,00 | 3,43 ± 5,14 | 0,0000 ± 0,0000 |
| C - Falla | Aleatoria | 100 | 211,93 ± 3,08 | 43,89 ± 8,57 | 13,434 ± 5,793 | 4,418 ± 1,009 | 2,20 ± 0,79 | 30,73 ± 11,18 | 0,0127 ± 0,0401 |

`desviacion_ocupacion` se calcula por corrida como la desviación estándar poblacional de `trabajo acumulado completado / capacidad`, solo entre servidores que no terminan en estado `CAIDO`; la tabla muestra el promedio y la dispersión de esa métrica entre corridas. En A, las capacidades son iguales y coincide con la desviación de carga. En B, normalizar por capacidad permite juzgar el uso relativo del nodo lento: una distribución de unidades de trabajo parecida no implica tiempos de ocupación parecidos, y dejar al nodo lento relativamente infrautilizado también aumenta la desviación. La desviación sin normalizar puede hacer parecer mejor a Round Robin (23,28) que a Menor Carga (28,18), mientras que la desviación de ocupación muestra a Menor Carga más equilibrada (13,201 frente a 27,342 y 22,872). En C, excluir el servidor caído evita contar como capacidad operativa el trabajo que dejó acumulado; Menor Carga obtiene 5,740 frente a 10,694 y 13,434.

La comprobación de conservación usa el trabajo realmente procesado: `sum(servidor.trabajo_procesado for servidor in resultado.servidores) == pytest.approx(sum(tarea.duracion for tarea in tareas))`, también en C. No se infiere la conservación a partir de la carga asignada. La regeneración que respalda estas tablas está en `results/verificacion_umbral12_20261106_1437/resumen.csv`; los parámetros efectivos de esa ejecución están registrados en `results/verificacion_umbral12_20261106_1437/parametros.csv`. El `results/resumen.csv` que ya existía difiere de esta regeneración en varias métricas; no se usa como evidencia y sus valores no permiten inferir qué umbral se usó.

### Tareas asignadas por servidor

Promedio de tareas completadas en 30 corridas con el umbral base 12:

| Escenario | Estrategia | S0 | S1 | S2 | S3 |
|---|---|---:|---:|---:|---:|
| A - Normal | Round Robin | 25,00 | 25,00 | 25,00 | 25,00 |
| A - Normal | Menor Carga | 24,83 | 25,50 | 25,03 | 24,63 |
| A - Normal | Aleatoria | 25,67 | 24,73 | 24,87 | 24,73 |
| B - Sobrecarga | Round Robin | 27,47 | 27,10 | 18,77 | 26,67 |
| B - Sobrecarga | Menor Carga | 28,10 | 28,20 | 16,33 | 27,37 |
| B - Sobrecarga | Aleatoria | 28,20 | 27,53 | 16,53 | 27,73 |
| C - Falla | Round Robin | 25,57 | 18,97 | 28,87 | 26,60 |
| C - Falla | Menor Carga | 24,73 | 26,13 | 24,37 | 24,77 |
| C - Falla | Aleatoria | 24,30 | 26,60 | 23,57 | 25,53 |

La siguiente corrida individual usa semilla 42, repetición 0 y el umbral base 12. En C, las tareas completadas pueden cambiar de servidor después de la falla:

| Escenario | Estrategia | S0 | S1 | S2 | S3 |
|---|---|---:|---:|---:|---:|
| A - Normal | Round Robin | 25 | 25 | 25 | 25 |
| A - Normal | Menor Carga | 26 | 26 | 25 | 23 |
| A - Normal | Aleatoria | 23 | 30 | 24 | 23 |
| B - Sobrecarga | Round Robin | 27 | 27 | 20 | 26 |
| B - Sobrecarga | Menor Carga | 29 | 28 | 15 | 28 |
| B - Sobrecarga | Aleatoria | 23 | 32 | 19 | 26 |
| C - Falla | Round Robin | 30 | 11 | 30 | 29 |
| C - Falla | Menor Carga | 32 | 30 | 11 | 27 |
| C - Falla | Aleatoria | 29 | 12 | 35 | 24 |

El promedio de 30 corridas oculta el desbalance que Aleatoria puede mostrar en una corrida individual: por ejemplo, en C una corrida asignó 12 tareas a S1 y 35 a S2, aunque los promedios de esas columnas son 26,60 y 23,57.

## 5. Experimento complementario: sin protección de sobrecarga

Se ejecutaron realmente los escenarios A y B durante 30 repeticiones con los mismos parámetros base y `UMBRAL_SOBRECARGA=1000`. En esta configuración no se activó ninguna sobrecarga:

| Escenario | Estrategia | Espera promedio | Makespan ± σ | Desv. ocupación promedio | Sobrecargas |
|---|---|---:|---:|---:|---:|
| A - Normal | Round Robin | 0,456 | 204,97 ± 2,09 | 11,270 | 0,00 |
| A - Normal | Menor Carga | 0,048 | 204,47 ± 2,08 | 7,596 | 0,00 |
| A - Normal | Aleatoria | 4,650 | 216,00 ± 8,41 | 23,115 | 0,00 |
| B - Sobrecarga | Round Robin | 9,931 | 281,53 ± 29,31 | 61,174 | 0,00 |
| B - Sobrecarga | Menor Carga | 0,277 | 205,87 ± 3,23 | 13,201 | 0,00 |
| B - Sobrecarga | Aleatoria | 15,753 | 294,07 ± 42,52 | 66,509 | 0,00 |

La protección por umbral se aplica a todas las estrategias, no es una función exclusiva de Menor Carga. En B, con umbral 12 Round Robin promedia 2,109 ticks de espera y un makespan de 212,70; sin esa protección, suben a 9,931 y 281,53. Por tanto, la protección reduce y puede ocultar la debilidad de Round Robin cuando distribuye las tareas entre servidores de capacidad heterogénea. Con umbral 1000, en la corrida de ejemplo de semilla 42, Aleatoria distribuyó en A/B 20, 33, 23 y 24 tareas entre S0–S3; esa dispersión ilustra por qué el promedio de 30 repeticiones no describe cada corrida.

## 6. Cómo interpretar las métricas y conclusiones

- **Tiempo promedio de espera:** ticks desde la llegada hasta el inicio del procesamiento; representa la espera observada por las tareas.
- **Sobrecargas totales:** veces que un servidor superó el umbral y dejó temporalmente de recibir tareas.
- **Makespan:** tick de finalización de la última tarea. Lo domina la llegada de la última tarea, aproximadamente `(N - 1) × INTERVALO_LLEGADA = 198` ticks, más el procesamiento pendiente; por eso las diferencias descriptivas no constituyen una prueba estadística.
- **Desviación estándar de carga:** dispersión de unidades de trabajo completado sin considerar capacidad ni estado final.
- **Desviación de ocupación:** dispersión poblacional de trabajo completado dividido entre capacidad, excluyendo servidores caídos. Resulta más informativa en B y C por las razones descritas arriba.
- **Espera de disponibilidad:** tiempo que una tarea aguarda cuando no hay servidores disponibles.
- **± σ:** variación entre las 30 repeticiones; no sustituye una prueba inferencial.

En A, Menor Carga tiene la menor desviación de ocupación (7,596), espera (0,048) y sobrecargas (0,00). En B, también es la mejor equilibrada según desviación de ocupación: 13,201 frente a 27,342 de Round Robin y 22,872 de Aleatoria; además promedia 0,277 ticks de espera. En C, vuelve a ser la más equilibrada con 5,740 frente a 10,694 y 13,434, y promedia 0,845 ticks de espera; Round Robin promedia 1,939 y Aleatoria 4,418. Estos valores de espera de C corresponden a la ejecución regenerada con el inicio de las tareas reasignadas corregido.

## 7. Limitaciones

- La falla es un único evento permanente: el servidor caído no se recupera.
- Las tareas son independientes; no se modelan dependencias ni prioridades.
- El motor usa un reloj discreto y no simula red, latencias ni comunicación real.
- Los resultados dependen de parámetros como `INTERVALO_LLEGADA` y `UMBRAL_SOBRECARGA`.
- En C, la cantidad de tareas reasignadas depende del disparador y del trabajo pendiente del servidor que falla. Toda tarea reasignada vuelve a intentar asignarse en el tick siguiente a la caída y, por tanto, pierde como mínimo un tick. Ese comportamiento se conserva intencionalmente.

## 8. Tabla de trazabilidad

La marca ✅ indica que existe una prueba en `tests/` o una ejecución real descrita como evidencia.

| Requisito | Implementación | Evidencia | Estado |
|---|---|---|---|
| Crear tareas reproducibles | `src/task_generator.py` | `tests/test_distribucion_y_regresion.py`; ejecución `--all` con semillas 42–71 | ✅ |
| Modelar tarea, servidor y estado | `src/models.py` | `tests/test_engine.py`, `tests/test_invariantes.py` | ✅ |
| Asignar con tres estrategias y rotar empates | `src/algorithms.py` | `tests/test_algorithms.py`, `tests/test_casos_algoritmos.py` | ✅ |
| Simular reloj, sobrecarga, falla y reasignación | `src/engine.py` | `tests/test_engine.py`, `tests/test_invariantes.py`, `tests/test_trazas_manuales.py` | ✅ |
| Completar tareas y conservar trabajo procesado en A, B y C | `src/engine.py` | `test_every_strategy_completes_every_task_in_all_scenarios` en `tests/test_engine.py` | ✅ |
| Calcular métricas y desviación de ocupación | `src/metrics.py` | `tests/test_engine.py`, `tests/test_distribucion_y_regresion.py` | ✅ |
| Exportar CSV, Excel y gráficas | `src/report.py` | `tests/test_report.py`; ejecución real `python -m src.main --all` | ✅ |
| Cargar y validar parámetros | `src/parameters.py`, `src/config.py` | `tests/test_engine.py`; ejecución real `python -m src.main --all` | ✅ |
| Ejecutar por línea de comandos | `src/main.py` | Ejecución real `python -m src.main --all` | ✅ |
| Mostrar y filtrar resultados en el panel | `src/dashboard.py` | `tests/test_report.py` comprueba el helper de resaltado; no hay prueba de interacción completa | — |
| Documentar arquitectura y flujo | `docs/arquitectura.md` | Evidencia documental; no es una prueba ni una ejecución | — |

## Verificación

**Fecha: 06 de noviembre de 2026.** `python -m pytest tests -v`: **129 pruebas pasadas, 0 fallidas**. Para verificar las cifras, se fijó `UMBRAL_SOBRECARGA=12` en el entorno del proceso y se comprobó que la configuración efectiva imprimía `12.0`; después, `python -m src.main --all --resultados results\verificacion_umbral12_20261106_1437` completó las nueve combinaciones con 30 repeticiones. Sus métricas coinciden con la tabla oficial al redondeo mostrado. También se ejecutó una corrida individual con semilla 42 y umbral 12; las nueve distribuciones por servidor coinciden con la tabla de esa sección. El CSV de resultados y el CSV de parámetros están en la carpeta indicada arriba. El CSV preexistente de `results/` no se sobrescribió.

## 9. Nota sobre el uso de IA

El código se desarrolló con asistencia de herramientas de IA y fue revisado y probado por el equipo con pruebas automatizadas y ejecuciones reales de la simulación.

## 10. Trabajo futuro

- Demostrar la asignación con servidores reales o contenedores.
- Integrar un balanceador de red para comparar la simulación con tráfico real.

## 11. Panel visual

Ejecuta `streamlit run src/dashboard.py`. La barra lateral organiza los parámetros de simulación, carga, escenarios y opciones avanzadas. La pestaña **Resultados oficiales** compara las estrategias con Plotly; **Eventos** muestra la línea de tiempo y la bitácora explicada; **Reproducción** permite examinar los snapshots por tick. Al pulsar **Reproducir**, el panel avanza automáticamente cada medio segundo; **Pausar**, el slider y los controles de paso permiten inspeccionar ticks concretos. Los informes oficiales y las gráficas PNG conservan su flujo existente en `src/report.py`.

## 12. Fallas y sobrecargas: comportamiento de cada estrategia

Las corridas oficiales conservan sus tres escenarios y no usan eventos programados. En el laboratorio se pueden explorar eventos al cierre de un tick:

- **CAIDA** detiene un servidor y envía a espera sus tareas en cola, conservando el trabajo que falta por procesar.
- **RECUPERACION** reactiva un servidor caído; las tareas en espera vuelven a asignarse en el siguiente tick.
- **DEGRADACION** reduce la capacidad y puede marcar el servidor como sobrecargado si la carga supera el umbral.
- **RESTAURACION** devuelve la capacidad original.

Los servidores sobrecargados siguen procesando su cola, pero no reciben trabajo nuevo hasta recuperar disponibilidad. Si todos los servidores están caídos, las tareas esperan cuando existe una recuperación programada; si no existe, el motor lanza `SistemaCaidoError` con eventos, registros completados, tick y tareas pendientes.

Round Robin rota entre servidores disponibles; Menor Carga considera el trabajo pendiente relativo a la capacidad; Aleatoria elige entre los servidores disponibles. El modo laboratorio aplica los mismos trabajos y eventos a las tres estrategias para comparar sus resultados; esos datos son exploratorios y no modifican el CSV, Excel ni las tablas oficiales.

## 13. Modo laboratorio

En **Laboratorio** se pueden ajustar el tamaño de la corrida, servidores, umbral y semilla, y agregar eventos individualmente o cargar presets de caída/recuperación y degradación/restauración. Cada estrategia se ejecuta con el mismo conjunto de tareas. El panel compara makespan y espera, muestra la bitácora, la evolución de la carga y un ρ aproximado calculado como trabajo acumulado de las llegadas dividido entre la capacidad acumulada.

Los resultados exploratorios se mantienen separados de `results/resumen.csv` y `results/resumen.xlsx`. La reproducción por ticks muestra los snapshots del motor; para construirla se vuelve a ejecutar una corrida individual con historial habilitado.

## 14. Limitaciones

- La simulación modela un reloj discreto y colas FIFO; no representa latencia de red ni coordinación entre procesos reales.
- Los eventos posteriores a la finalización de todas las tareas no se ejecutan, pues el motor termina cuando no queda trabajo.
- ρ es una estimación basada en las llegadas y la capacidad nominal, no una medición de utilización real.
- Las visualizaciones interactivas requieren Plotly; Matplotlib se conserva para los reportes PNG.

## 15. Estructura del proyecto

```text
balanceo-carga/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── docs/
│   └── arquitectura.md
├── results/
│   ├── .gitkeep
│   └── verificacion_umbral12_20261106_1437/
│       ├── parametros.csv
│       └── resumen.csv
├── src/
│   ├── __init__.py
│   ├── algorithms.py
│   ├── bitacora.py
│   ├── config.py
│   ├── dashboard.py
│   ├── engine.py
│   ├── main.py
│   ├── metrics.py
│   ├── models.py
│   ├── parameters.py
│   ├── report.py
│   ├── scenarios.py
│   └── task_generator.py
│   └── visual.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_algorithms.py
    ├── test_casos_algoritmos.py
    ├── test_dashboard_smoke.py
    ├── test_distribucion_y_regresion.py
    ├── test_eventos_programados.py
    ├── test_engine.py
    ├── test_historial.py
    ├── test_invariantes.py
    ├── test_report.py
    └── test_trazas_manuales.py
```
