# DCMA 14-Point + Earned Schedule Manager

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://dcma-earned-schedule-manager.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-0A5C91.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Community%20Cloud-00A88F.svg)](https://streamlit.io/)
[![Primavera P6](https://img.shields.io/badge/Primavera%20P6-XER-078B55.svg)](https://www.oracle.com/construction-engineering/primavera-p6/)
[![Version](https://img.shields.io/badge/version-0.3.2-082D50.svg)](https://github.com/jaguado67/dcma-earned-schedule-manager)

Aplicación desarrollada para analizar la salud estructural de cronogramas exportados desde Oracle Primavera P6 mediante archivos XER.

El sistema integra el **DCMA 14-Point Schedule Assessment**, análisis de recursos y costos, exploración de hallazgos y fundamentos de **Earned Schedule Management** dentro de un flujo de trabajo trazable.

## Aplicación en línea

Acceda a la versión desplegada en Streamlit Community Cloud:

**[Abrir DCMA + Earned Schedule Manager](https://dcma-earned-schedule-manager.streamlit.app/)**

## Objetivo

La aplicación busca transformar el archivo XER en una fuente estructurada para el diagnóstico del cronograma.

Permite identificar problemas relacionados con:

* lógica incompleta;
* relaciones adelantadas o *leads*;
* esperas o *lags*;
* tipos de relación;
* restricciones duras;
* holguras elevadas;
* holguras negativas;
* actividades con duraciones extensas;
* fechas potencialmente inválidas;
* actividades sin asignación de recursos;
* actividades incumplidas respecto de la línea base;
* prueba controlada del camino crítico;
* Critical Path Length Index — CPLI;
* Baseline Execution Index — BEI.

## Funcionalidades principales

### Carga y lectura de archivos XER

* Carga simultánea de uno o varios cronogramas.
* Selección del proyecto activo.
* Carga opcional de la línea base contractual.
* Lectura directa de las tablas exportadas desde Primavera P6.
* Identificación de versión, fecha de exportación y último recálculo.
* Inventario de tablas y registros contenidos en el XER.

### DCMA 14-Point Assessment

Cada prueba presenta:

* resultado observado;
* meta o límite de referencia;
* estado de cumplimiento;
* reloj gráfico de condición;
* cantidad de registros afectados;
* hallazgos descargables en formato CSV.

Los estados utilizados son:

| Estado       | Interpretación                                                          |
| ------------ | ----------------------------------------------------------------------- |
| Cumple       | El resultado se encuentra dentro del criterio establecido               |
| No cumple    | El indicador supera el límite aceptable                                 |
| Revisar      | El resultado requiere validación técnica                                |
| No evaluable | El XER no contiene la información suficiente para emitir una conclusión |

La ausencia de información no se convierte automáticamente en cumplimiento.

### Pruebas de desempeño

Las pruebas 11 a 14 se presentan como un bloque independiente porque requieren información adicional o procedimientos específicos:

* **Missed Activities:** requiere línea base contractual y Data Date validada.
* **Critical Path Test:** requiere una prueba controlada y un nuevo recálculo en Primavera P6.
* **CPLI:** requiere la selección del hito contractual y la validación de la ruta crítica.
* **BEI:** requiere una línea base contractual correctamente vinculada.

### Explorador de hallazgos

La aplicación permite inspeccionar las actividades y relaciones responsables de cada resultado:

* actividades sin predecesoras o sucesoras;
* relaciones con leads;
* relaciones con lags;
* relaciones diferentes de Finish-to-Start;
* restricciones;
* holguras;
* duraciones;
* fechas;
* asignaciones de recursos.

Los registros pueden descargarse para su revisión y corrección en Primavera P6.

### Recursos, equipos y costos

El módulo analiza la información disponible en las tablas de asignaciones y recursos:

* recursos maestros;
* actividades con asignaciones;
* mano de obra;
* equipos;
* materiales;
* cantidades objetivo;
* cantidades restantes;
* costo objetivo;
* costo restante;
* concentración de asignaciones en recursos genéricos o *dummy*.

La existencia formal de una asignación no demuestra por sí sola que el cronograma sea ejecutable con la capacidad real disponible.

### Earned Schedule Management

El módulo de Earned Schedule utiliza series acumuladas de:

* Planned Value — PV;
* Earned Value — EV;
* Actual Cost — AC.

A partir de estas series calcula:

* Schedule Performance Index — SPI;
* Cost Performance Index — CPI;
* Earned Schedule — ES;
* Schedule Variance in time units — SV(t);
* Schedule Performance Index in time units — SPI(t).

La aplicación incluye una plantilla descargable para cargar la información acumulada por período.

## Archivos de demostración

El repositorio incluye dos archivos XER para pruebas iniciales:

* Torre Mar V2;
* Torre Sierra V2.

Estos cronogramas permiten explorar la interfaz y verificar el comportamiento de los indicadores antes de cargar información propia.

## Estructura del proyecto

```text
dcma-earned-schedule-manager/
├── .streamlit/
│   └── config.toml
├── assets/
│   ├── logo_bolivar.png
│   ├── logo_cronostasis.png
│   └── hero_cronostasis.png
├── demo/
│   ├── torre_mar_v2.xer
│   └── torre_sierra_v2.xer
├── src/
│   ├── dcma.py
│   ├── earned_schedule.py
│   └── xer.py
├── tests/
│   └── test_engine.py
├── .gitignore
├── METHODOLOGY.md
├── README.md
├── requirements.txt
└── streamlit_app.py
```

## Instalación local

### 1. Clonar el repositorio

```powershell
git clone https://github.com/jaguado67/dcma-earned-schedule-manager.git
cd dcma-earned-schedule-manager
```

### 2. Crear el entorno virtual

```powershell
py -m venv .venv
```

### 3. Activar el entorno

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar las dependencias

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 5. Ejecutar la aplicación

```powershell
py -m streamlit run streamlit_app.py
```

La aplicación estará disponible normalmente en:

```text
http://localhost:8501
```

## Actualización del repositorio

Después de realizar cambios:

```powershell
git status
git add .
git commit -m "Describe the implemented change"
git push
```

Streamlit Community Cloud detectará el nuevo commit y actualizará automáticamente la aplicación.

## Seguridad

Los siguientes archivos y directorios no deben publicarse:

```gitignore
.venv/
__pycache__/
*.pyc
.env
.streamlit/secrets.toml
```

Antes de cargar un XER en un repositorio público, debe verificarse que no contenga información contractual, financiera, personal o comercial restringida.

## Alcance y limitaciones

El análisis DCMA evalúa principalmente la estructura y determinadas condiciones del cronograma.

Un resultado favorable no demuestra automáticamente que el cronograma sea:

* constructivamente viable;
* completo respecto del alcance;
* consistente con las cantidades;
* compatible con la productividad esperada;
* ejecutable con los recursos disponibles;
* coherente con las restricciones espaciales;
* aprobado contractualmente.

La herramienta tampoco modifica automáticamente el archivo XER ni reemplaza el proceso de programación y recálculo en Primavera P6.

La aplicación analiza y documenta. La decisión profesional sigue perteneciendo al equipo de planificación. Por ahora, ningún gráfico circular ha recibido autoridad contractual.

## Referencias metodológicas

El desarrollo considera conceptos y buenas prácticas provenientes de:

* DCMA 14-Point Schedule Assessment;
* PMI Practice Standard for Scheduling;
* AACE International Recommended Practices;
* Earned Value Management;
* Earned Schedule;
* Oracle Primavera P6 Professional.

Los criterios deben interpretarse dentro del contexto contractual, constructivo y organizacional de cada proyecto.

## Versión actual

**v0.3.2**

Esta versión incluye:

* carga múltiple de archivos XER;
* línea base opcional;
* panel de 14 indicadores;
* relojes gráficos de condición;
* explorador de hallazgos;
* análisis inicial de recursos y costos;
* módulo de Earned Schedule;
* identidad visual Constructora Bolívar y Cronostasis;
* pruebas de desempeño agrupadas;
* requisitos explícitos para los indicadores no evaluables.

## Autor y desarrollo

**Jair Aguado**
Ingeniero electricista y especialista en planificación y control de proyectos.

Desarrollo metodológico y analítico:

**CRONOSTASIS — Planning, Scheduling & Project Analytics**

## Licencia y uso

Este proyecto se publica con fines de análisis, demostración y desarrollo profesional.

Antes de utilizar sus resultados como soporte contractual, pericial o ejecutivo, deben validarse:

* la integridad del archivo XER;
* la configuración del proyecto en Primavera P6;
* la línea base aplicable;
* la Data Date;
* los calendarios;
* la ruta crítica;
* los recursos;
* los criterios contractuales.
