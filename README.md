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

## 4. Resultados de la ejecución regenerada

La siguiente tabla procede de `python -m src.main --all`, con los valores documentados en `.env.example`, semillas de tareas 42 a 71 y 30 repeticiones por combinación. Cada fila completó las 100 tareas. `σ` representa la desviación estándar entre repeticiones. La reasignación solo aplica al escenario C; se muestra como `—` en A y B.

| Escenario | Estrategia | Tareas completadas | Makespan ± σ | Desv. estándar de carga ± σ | Tiempo promedio de espera ± σ | Tareas reasignadas ± σ | Sobrecargas totales ± σ | Tiempo en cola de espera ± σ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A - Normal | Round Robin | 100 | 204,97 ± 2,09 | 11,27 ± 4,28 | 0,456 ± 0,139 | — | 0,90 ± 1,22 | 0,0000 ± 0,0000 |
| A - Normal | Menor Carga | 100 | 204,47 ± 2,08 | 7,60 ± 3,18 | 0,048 ± 0,028 | — | 0,00 ± 0,00 | 0,0000 ± 0,0000 |
| A - Normal | Aleatoria | 100 | 210,30 ± 4,17 | 16,41 ± 5,31 | 3,008 ± 0,593 | — | 19,57 ± 6,77 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Round Robin | 100 | 212,70 ± 5,15 | 23,28 ± 4,00 | 2,109 ± 0,388 | — | 16,73 ± 3,86 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Menor Carga | 100 | 205,87 ± 3,23 | 28,18 ± 2,92 | 0,277 ± 0,126 | — | 6,70 ± 1,62 | 0,0000 ± 0,0000 |
| B - Sobrecarga | Aleatoria | 100 | 211,73 ± 3,71 | 29,41 ± 7,29 | 3,974 ± 0,762 | — | 31,13 ± 8,09 | 0,0000 ± 0,0000 |
| C - Falla | Round Robin | 100 | 210,03 ± 3,64 | 42,91 ± 5,86 | 1,923 ± 0,744 | 1,17 ± 0,37 | 10,90 ± 8,06 | 0,0057 ± 0,0305 |
| C - Falla | Menor Carga | 100 | 206,17 ± 2,92 | 43,31 ± 4,48 | 0,841 ± 0,549 | 1,00 ± 0,00 | 3,43 ± 5,14 | 0,0000 ± 0,0000 |
| C - Falla | Aleatoria | 100 | 211,93 ± 3,08 | 43,89 ± 8,57 | 4,365 ± 1,005 | 2,20 ± 0,79 | 30,73 ± 11,18 | 0,0127 ± 0,0401 |

La suma de la carga acumulada por servidor coincide con la duración total de las tareas en cada ejecución. El archivo `results/resumen.csv` contiene las cifras con precisión completa y el reporte Excel separa los escenarios en hojas.

## 5. Cómo interpretar las métricas

- **Tiempo promedio de espera:** ticks que una tarea pasa en su cola antes de empezar a procesarse; es la métrica principal porque representa lo que percibe cada tarea.
- **Sobrecargas totales:** cantidad de veces que un servidor superó el umbral; indica el estrés observado en el sistema.
- **Makespan:** tick en que termina la última tarea. Lo domina en gran medida la llegada de la última tarea, aproximadamente `(N - 1) × INTERVALO_LLEGADA = 198` ticks, más el procesamiento pendiente. Por eso discrimina poco; diferencias menores que una desviación estándar no justifican afirmar que una estrategia es mejor.
- **Desviación estándar de la carga:** desigualdad del trabajo acumulado entre servidores. Mide equilibrio acumulado, no equilibrio instantáneo. En Menor Carga, el desempate rotativo evita favorecer siempre al servidor con ID menor y cambia la distribución observada.
- **± σ:** muestra la variación entre repeticiones. Si dos promedios difieren menos que la desviación estándar correspondiente, no se debe afirmar que uno es mejor solo por su promedio.
- **Tiempo en cola de espera:** mide cuánto esperan las tareas cuando ningún servidor está disponible. Es cero o cercano a cero en estas ejecuciones porque la utilización configurada es menor que 1 y la ausencia simultánea de servidores disponibles es poco frecuente; la caída puede producir esperas pequeñas y temporales.

## 6. Análisis y conclusiones

En A, Menor Carga promedia 0,048 ticks de espera frente a 0,456 de Round Robin y 3,008 de Aleatoria. También registra cero sobrecargas, frente a 0,90 de Round Robin y 19,57 de Aleatoria. Con el desempate rotativo, la carga media por servidor de Menor Carga queda entre 133,93 y 138,40 unidades; su desviación estándar de carga, 7,60 ± 3,18, es menor que la de Round Robin (11,27 ± 4,28) y Aleatoria (16,41 ± 5,31). El makespan de Round Robin y Menor Carga difiere solo 0,50 ticks, por debajo de sus desviaciones estándar, así que esos promedios no permiten declarar una ventaja de makespan.

En B, Menor Carga vuelve a minimizar la espera (0,277 ticks) y registra menos sobrecargas (6,70) que Round Robin (2,109 ticks y 16,73 sobrecargas) y Aleatoria (3,974 ticks y 31,13 sobrecargas). Sin embargo, Round Robin logra menor desviación de carga (23,28 frente a 28,18 para Menor Carga); por tanto, no corresponde describir Menor Carga como la más equilibrada en este escenario. El makespan medio de Menor Carga es 6,83 ticks inferior al de Round Robin, más que una σ de cada estrategia; es una diferencia descriptiva, no una prueba estadística formal.

En C, el servidor que falla se escoge entre los que tienen más trabajo pendiente en el instante configurado; por ello la reasignación es visible y varía según la estrategia. Menor Carga promedia 1,00 tarea reasignada y 0,841 ticks de espera; Round Robin, 1,17 tareas y 1,923 ticks; Aleatoria, 2,20 tareas y 4,365 ticks. Menor Carga también tiene menos sobrecargas que las otras estrategias (3,43 frente a 10,90 y 30,73). La desviación de carga de Round Robin (42,91) y Menor Carga (43,31) es cercana, así que no hay una diferencia práctica clara en equilibrio acumulado. El makespan de Menor Carga es 3,87 ticks menor que el de Round Robin; supera por poco una σ de cada promedio, pero no se ha aplicado una prueba inferencial.

Las tres estrategias reciben únicamente servidores disponibles. La regla de sobrecarga es una protección del sistema: un nodo sobrecargado sigue procesando, pero no recibe tareas nuevas hasta recuperarse. Esa protección puede aumentar la espera y se refleja en los eventos de sobrecarga; no constituye una ventaja exclusiva de una estrategia.

**Conclusión por escenario:** con servidores iguales y bajo costo de monitoreo, Round Robin es una alternativa sencilla y distribuye de forma uniforme la carga acumulada (en A, las cargas medias por nodo están entre 135,00 y 137,90). Si se prioriza minimizar espera y monitorear la carga no es costoso, Menor Carga mejora esos resultados en A. Para capacidad heterogénea como B, conviene Menor Carga cuando importan la espera y evitar sobrecargas; Round Robin ofrece menor desviación de carga acumulada, pero espera más y genera más sobrecargas. En C, Menor Carga obtiene la menor espera y menos sobrecargas de esta ejecución; Aleatoria resulta menos conveniente en ambos criterios.

## 7. Limitaciones

- La falla es un único evento permanente: el servidor caído no se recupera.
- Las tareas son independientes; no se modelan dependencias ni prioridades.
- El motor usa un reloj discreto y no simula red, latencias ni comunicación real.
- Los resultados dependen de parámetros como `INTERVALO_LLEGADA` y `UMBRAL_SOBRECARGA`.
- En C, la cantidad de tareas reasignadas depende del disparador y del trabajo pendiente del servidor que falla en ese instante.

## 8. Tabla de trazabilidad

La marca ✅ se reserva para comportamiento comprobado con pruebas o ejecución de la simulación. La documentación de arquitectura se señala aparte porque es una evidencia documental.

| Requisito | Archivo | Clase / función exacta | Evidencia | Estado |
|---|---|---|---|---|
| Crear tareas reproducibles | `src/task_generator.py` | `generar_tareas()` | La ejecución completa registra las semillas 42–71 | ✅ |
| Modelar tarea, servidor y estado | `src/models.py` | `Tarea`, `Servidor`, `EstadoServidor` | `tests/test_engine.py` y ejecución completa | ✅ |
| Asignar con tres estrategias | `src/algorithms.py` | `RoundRobin.asignar()`, `MenorCarga.asignar()`, `Aleatoria.asignar()` | `tests/test_algorithms.py` | ✅ |
| Rotar desempates de Menor Carga | `src/algorithms.py` | `MenorCarga.asignar()` | `test_menor_carga_rotates_among_equal_load_servers` | ✅ |
| Simular reloj, sobrecarga y falla | `src/engine.py` | `ConfiguracionFalla`, `ejecutar_simulacion()` | `tests/test_engine.py` | ✅ |
| Fallar el servidor con más trabajo pendiente en C | `src/scenarios.py`, `src/engine.py` | `ejecutar_escenario_c()`, `ConfiguracionFalla.elegir_mas_cargado` | `test_scenario_failure_targets_server_with_most_pending_work` | ✅ |
| Comprobar que no se pierden tareas ni carga | `tests/test_engine.py` | `test_every_strategy_completes_every_task_in_all_scenarios` | Prueba las nueve combinaciones y conserva el trabajo generado; la ejecución real `--all` confirma 100 completadas por combinación | ✅ |
| Calcular métricas | `src/metrics.py` | `calcular_metricas()` | Pruebas de métricas en `tests/test_engine.py` | ✅ |
| Exportar CSV, Excel y gráficas | `src/report.py` | `generar_csv()`, `generar_excel()`, `generar_graficas()` | `test_reports_mark_reassignments_only_in_failure_scenario_and_add_comparisons` y ejecución completa | ✅ |
| Cargar y validar parámetros | `src/parameters.py`, `src/config.py` | `ParametrosSimulacion.validar()`, `crear_parametros_por_defecto()` | Pruebas de parámetros explícitos y ejecución completa | ✅ |
| Ejecutar por línea de comandos | `src/main.py` | `main()`, `ejecutar_desde_parametros()` | `python -m src.main --all` | ✅ |
| Mostrar y filtrar resultados en el panel | `src/dashboard.py` | `main()` | Prueba interactiva con Streamlit AppTest | ✅ |
| Documentar arquitectura y flujo | `docs/arquitectura.md` | Diagrama Mermaid | Revisión documental; no es una prueba de ejecución | — |

## 9. Nota sobre el uso de IA

El código se desarrolló con asistencia de herramientas de IA y fue revisado y probado por el equipo con pruebas automatizadas y ejecuciones reales de la simulación.

## 10. Trabajo futuro

- Demostrar la asignación con servidores reales o contenedores.
- Integrar un balanceador de red para comparar la simulación con tráfico real.

## 11. Panel visual

Ejecuta `streamlit run src/dashboard.py`. La barra lateral permite configurar la simulación; pulsa **Ejecutar simulación** para aplicar esos cambios. Las pestañas muestran el resumen, gráficas, línea de tiempo y eventos; los selectores y filtros de esas pestañas actualizan la vista sin volver a ejecutar el motor.

## 12. Estructura del proyecto

```text
balanceo-carga/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── docs/
│   └── arquitectura.md
├── results/
│   └── .gitkeep
├── src/
│   ├── __init__.py
│   ├── algorithms.py
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
└── tests/
    ├── __init__.py
    ├── test_algorithms.py
    ├── test_engine.py
    └── test_report.py
```
