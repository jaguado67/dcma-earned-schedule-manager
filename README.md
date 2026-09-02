# DCMA + Earned Schedule Manager

Aplicación Streamlit para auditar archivos Oracle Primavera P6/OPC XER mediante los 14 puntos DCMA y ampliar el control hacia recursos, costos y Earned Schedule Management.

## Alcance de la versión 0.3.2

- Carga múltiple de XER actuales.
- Carga opcional de baseline XER.
- Parser XER sin dependencia de una base de datos P6.
- Evaluación explícita de los 14 puntos DCMA.
- Estados `Cumple`, `No cumple`, `Revisar` y `No evaluable`.
- Explorador y exportación CSV de hallazgos.
- Resumen de recursos, equipos y costos.
- Módulo Earned Schedule con PV, EV y AC acumulados.
- Dataset de demostración: Torre Mar V2 y Torre Sierra V2.
- Identidad visual Cronostasis + Constructora Bolívar.
- Panel de 14 relojes circulares con magnitud, meta y condición de cada prueba.
- Claves únicas para cada gráfico Streamlit; elimina `StreamlitDuplicateElementId`.
- Identidad institucional vertical en el sidebar: Constructora Bolívar arriba y Cronostasis debajo.
- Cabecera analítica simplificada, estado de entradas, flujo de revisión y contexto visible del corte.
- Separación visual de los logos y margen superior reforzado para evitar el recorte de la cabecera.
- Bloque compacto para las pruebas 11–14, con requisitos explícitos cuando una métrica todavía no es evaluable.

## Principio de diseño

La herramienta no convierte la ausencia de información en un resultado aprobado. Missed Tasks, Critical Path Test, CPLI y BEI permanecen como `No evaluable` hasta que se proporcionen las entradas y pruebas requeridas.

## Ejecutar en VS Code

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

En macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Entrada Earned Schedule

CSV o Excel con columnas acumuladas:

- `Period`
- `PV`
- `EV`
- `AC`

La aplicación calcula `SV`, `SPI`, `CV`, `CPI`, `ES`, `SV(t)` y `SPI(t)`.

## Siguiente versión propuesta

- Emparejamiento formal baseline/update por GUID.
- Critical Path Test asistido mediante XER de control.
- CPLI y BEI completamente automatizados.
- Histogramas time-phased de mano de obra y equipos.
- Demanda vs. capacidad por contratista y especialidad.
- Curvas de costos y forecast integrado.
- Comparación entre cortes y trazabilidad de cambios.
