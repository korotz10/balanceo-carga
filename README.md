# Simulación de balanceo de carga en sistemas distribuidos

Este proyecto compara tres estrategias de asignación — Round Robin, Menor Carga y Aleatoria — en un entorno simulado con 4 servidores y 100 tareas, evaluando comportamiento bajo carga normal, sobrecarga y caída de un nodo. La simulación genera evidencia en CSV, Excel y PNG, y admite un panel visual con Streamlit.

## 1. Marco conceptual

En sistemas distribuidos, una estación de trabajo concentra un conjunto de recursos para ejecutar tareas puntuales. Un pool de procesadores, en cambio, representa múltiples nodos capaces de ejecutar trabajo en paralelo. La simulación se aproxima más a un pool de procesadores con varios servidores idénticos o heterogéneos, ya que cada nodo recibe trabajo y procesa su cola FIFO según su capacidad.

La asignación estática usa reglas predefinidas que no consultan el estado del sistema en el momento de decidir (por ejemplo, Round Robin o Aleatoria). La asignación dinámica sí observa el estado actual del sistema para elegir la mejor opción (como Menor Carga). En este proyecto, la asignación decide a qué servidor va cada tarea; la planificación local, en cada servidor, decide el orden de ejecución dentro de su cola. El balanceo de carga consiste en distribuir la carga entre los servidores para minimizar tiempos de espera, evitar sobrecarga y mantener disponibilidad.

## 2. Configuración y cálculo de utilización

Los valores por defecto elegidos son:

- `INTERVALO_LLEGADA = 2`
- `UMBRAL_SOBRECARGA = 12`

La media de duración de las tareas es:

- `(1 + 10) / 2 = 5.5`

Con 4 servidores y una llegada cada 2 unidades de tiempo:

- Escenario A: ρ = 5.5 / (4 × 2) = 0.6875 = 68.75%
- Escenario C: ρ = 5.5 / (3 × 2) = 0.9167 = 91.67%
- Escenario B: con un servidor a mitad de capacidad, la capacidad efectiva es 3.5 y ρ = 5.5 / (3.5 × 2) = 0.7857 = 78.57%

Esto mantiene el escenario A cercano al objetivo de 60-70 %, y B/C cerca de 80-90 %, sin saturar el sistema de forma permanente. El umbral de sobrecarga se fija en 12 porque equivale a aproximadamente dos tareas promedio por servidor; así se detecta congestión sin bloquear cada nodo indefinidamente.

## 3. Ejecución y salidas

```powershell
# Instalación
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env

# Simulación completa
python -m src.main --all

# Pruebas
python -m pytest tests -q

# Panel visual
streamlit run src/dashboard.py
```

Los archivos generados se guardan en `results/` y también se copian a `docs/img/` para documentar resultados en GitHub:

- `results/resumen.csv`
- `results/resumen.xlsx`
- `results/graficas/*.png`
- `docs/img/*.png`

## 4. Resultados reales

Los valores de la tabla corresponden a la ejecución real con los parámetros por defecto y 30 repeticiones por combinación.

| Escenario | Estrategia | Makespan promedio ± σ | Desv. estándar de carga ± σ | Tiempo promedio de espera ± σ | Sobrecargas totales ± σ |
|---|---|---:|---:|---:|---:|
| A - Normal | Round Robin | 204.97 ± 2.09 | 11.27 ± 4.28 | 0.456 ± 0.139 | 0.0 ± 0.0 |
| A - Normal | Menor Carga | 204.47 ± 2.08 | 43.55 ± 5.95 | 0.048 ± 0.028 | 0.0 ± 0.0 |
| A - Normal | Aleatoria | 209.67 ± 3.87 | 19.28 ± 8.26 | 3.362 ± 0.797 | 11.7 ± 6.85 |
| B - Sobrecarga | Round Robin | 214.87 ± 6.08 | 22.28 ± 4.34 | 2.357 ± 0.403 | 13.8 ± 2.80 |
| B - Sobrecarga | Menor Carga | 206.80 ± 4.45 | 43.92 ± 4.30 | 0.261 ± 0.135 | 4.9 ± 2.00 |
| B - Sobrecarga | Aleatoria | 216.17 ± 5.95 | 27.54 ± 6.32 | 4.558 ± 0.814 | 24.0 ± 5.18 |
| C - Falla | Round Robin | 210.33 ± 4.30 | 45.13 ± 5.35 | 1.995 ± 0.760 | 5.3 ± 6.15 |
| C - Falla | Menor Carga | 206.17 ± 2.92 | 54.37 ± 4.28 | 0.832 ± 0.548 | 0.5 ± 1.86 |
| C - Falla | Aleatoria | 214.93 ± 3.58 | 47.81 ± 7.81 | 4.976 ± 1.144 | 21.5 ± 9.33 |

### Gráficas

![Carga escenario A](./img/carga_a.png)

![Carga escenario B](./img/carga_b.png)

![Carga escenario C](./img/carga_c.png)

![Comparación Makespan](./img/makespan_comparativo.png)

![Comparación desviación de carga](./img/desviacion_carga_comparativo.png)

## 5. Análisis y conclusiones

- Menor Carga ofrece el mejor tiempo medio de espera y un rendimiento muy estable en los escenarios normales y de sobrecarga. Es la estrategia más equilibrada y la más útil cuando la carga no es uniforme ni se conoce exactamente el patrón de llegada.
- Round Robin tiene un tiempo de completado muy cercano a Menor Carga y suele distribuir bien el trabajo si todos los servidores muestran la misma capacidad. Sin embargo, en una situación con servidores heterogéneos o con caídas, su comportamiento es más sensible a la congestión local.
- Aleatoria presenta la mayor variabilidad y los mayores tiempos de espera. Su valor es útil como referencia estadística, pero no es recomendable en sistemas en los que la latencia o la estabilidad importan.
- En el escenario B, la sobrecarga aparece precisamente en el servidor lento; el sistema reacciona marcando ese nodo como `SOBRECARGADO` y evitando enviar nuevas tareas hasta que su carga baje. Esto protege el sistema y evita una caída de servicio total, aunque afecta el makespan.
- En el escenario C, la falla provoca reasignaciones y aumenta la espera de algunas tareas, pero la simulación confirma que ninguna tarea se pierde. Menor Carga vuelve a ofrecer el mejor comportamiento global, mientras que Aleatoria presenta una variabilidad más alta.

La decisión de mantener ambos: la protección de sobrecarga para todas las estrategias y el cálculo de tiempo en cola, permite comparar de forma justa y evita que los algoritmos “ignore” el estado del sistema. En otras palabras, todas las estrategias reciben solo servidores disponibles; la regla de sobrecarga sigue siendo un mecanismo de seguridad del sistema, no una ventaja de estrategia.

## 6. Tabla de trazabilidad

| Requisito | Archivo | Función / bloque | Verificado |
|---|---|---|---|
| 100 tareas, 4 servidores, 3 estrategias | `src/task_generator.py` | `generar_tareas()` | ✅ |
| Modelo de tarea y servidor con estados | `src/models.py` | `Tarea`, `Servidor`, `EstadoServidor` | ✅ |
| Generación de escenarios | `src/scenarios.py` | `ejecutar_escenario_a/b/c` | ✅ |
| Round Robin, Menor Carga y Aleatoria | `src/algorithms.py` | `RoundRobin.asignar()`, `MenorCarga.asignar()`, `Aleatoria.asignar()` | ✅ |
| Reloj simulado y eventos | `src/engine.py` | `ejecutar_simulacion()` | ✅ |
| Métricas de espera y sobrecarga | `src/metrics.py` | `calcular_metricas()` | ✅ |
| CSV, Excel y PNG | `src/report.py` | `generar_csv()`, `generar_excel()`, `generar_graficas()` | ✅ |
| Parámetros explícitos por dataclass | `src/parameters.py` | `ParametrosSimulacion` | ✅ |
| Configuración desde `.env` | `src/config.py` | `crear_parametros_por_defecto()` | ✅ |
| CLI principal | `src/main.py` | `main()` | ✅ |
| Dashboard Streamlit | `src/dashboard.py` | `main()` | ✅ |
| Documentación de arquitectura | `docs/arquitectura.md` | Diagrama Mermaid | ✅ |

## 7. Nota honesta sobre IA

El código y la documentación de este proyecto se desarrollaron con asistencia de IA y fueron revisados, ejecutados y validados por el equipo con pruebas automatizadas y simulaciones completas. La ejecución real de la simulación y los resultados reportados en este README corresponden a la versión comprobada del repositorio.

## 8. Trabajo futuro

- Integrar servidores reales o contenedores para comparar resultados con una infraestructura física.
- Añadir un balanceador de red o proxy con políticas de enrutamiento para validar la diferencia entre asignación local y equilibrio global.
- Extender el motor para modelar tareas con dependencias, tiempos de arranque y fallos transitorios.
- Extraer métricas adicionales como throughput, latencia por tarea y tiempo de recuperación del sistema.

## 9. Instrucciones del panel visual

El panel se ejecuta con:

```powershell
streamlit run src/dashboard.py
```

Desde la barra lateral se pueden ajustar `INTERVALO_LLEGADA`, `UMBRAL_SOBRECARGA`, `SEMILLA`, `TAREA_FALLA`, `SERVIDOR_FALLA`, `SERVIDOR_LENTO`, `CAPACIDAD_REDUCIDA`, `NUM_TAREAS` y `REPETICIONES`. El botón `Ejecutar simulación` actualiza los resultados en tiempo real. El dashboard presenta cuatro pestañas:

1. Resumen: tabla comparativa por estrategia con el mejor valor resaltado.
2. Gráficas: carga por servidor y comparación de makespan / desviación estándar.
3. Línea de tiempo: vista tipo Gantt por servidor con sobrecarga y caída marcadas.
4. Eventos: tabla filtrable por tipo, servidor y tarea.

## 10. Estructura del proyecto

```text
balanceo-carga/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
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
├── tests/
├── docs/
│   ├── arquitectura.md
│   └── img/
├── results/
└── .venv/
```
