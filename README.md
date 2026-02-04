# ETABSlab (SAP2000 NLTH)

Pipeline simple para correr NLTH en SAP2000, extraer desplazamientos por nodos,
calcular drifts consecutivos y guardar resultados en SQLite.

## Requisitos

- Python con dependencias de `requirements.txt`
- SAP2000 abierto (instancia activa)
- Modelo `.sdb` accesible

## Configuracion

Archivo unico: `config/settings.yaml`

Ejemplo:
```
model_path: "C:/Users/rocha/Desktop/SAP2000 test/test.sdb"
case_name: "NLTH_BATCH"
output_time_step: 0.05
nodes:
  - {name: "BASE", joint: "13", z: 0.00}
  - {name: "L01", joint: "14", z: 3.66}
  - {name: "L02", joint: "15", z: 7.32}
  - {name: "ROOF", joint: "32", z: 10.97}
```

## Flujo principal

- Preprocesar catalogo (si aplica):
  - `python scripts/preprocess_mat_catalog.py`
- Ejecutar batch NLTH:
  - `python scripts/run_nlth_batch.py`
- Inspeccionar SQLite:
  - `python scripts/tests/inspect_db.py`

## Ejecutable (Windows)

Para generar un exe fuera del repo (sin ensuciar la carpeta):

1) Instalar PyInstaller:
```
pip install pyinstaller
```

2) Construir el exe usando el script:
```
.\build.ps1
```

Salida por defecto:
`C:\Users\rocha\Documents\ETABSlab_exe\dist\etabslab_batch.exe`

Cambiar la ruta de salida:
```
.\build.ps1 -OutRoot "D:\ETABSlab_exe"
```

Notas:
- La PC destino debe tener SAP2000 instalado y activo (COM/OAPI).
- Copiar junto al exe los archivos necesarios (ej. `config/settings.yaml`, `results/catalog.csv`, datos de entrada).

## Persistencia (SQLite)

DB: `results/edp.sqlite`

Tablas:
- `runs`: metadata de cada corrida
- `node_disp`: u1/u2 max por nodo
- `drifts`: drift entre nodos consecutivos
- `run_summary`: maximos globales por corrida

## Pruebas manuales / utilitarios

Scripts en `scripts/tests/`:
- `test_edp_nodes.py`: extrae desplazamientos por nodo
- `test_drift.py`: calcula drifts consecutivos
- `test_db_write.py`: escribe en SQLite con datos reales
- `inspect_db.py`: imprime y grafica resultados
- `inspect_jointdispl.py`: debug de JointDispl
- `print_nodes_config.py`: imprime config
- `test_select_case_output.py`: selecciona caso de output

## Troubleshooting rapido

- `ret=27` en `GetNameList`: modelo no cargado o API no lista.
- `ret=2` en `JointDispl`: el joint o el caso no existen, o no hay resultados.
- Si el modelo esta bloqueado: se permite lectura con `allow_locked=True`.
- El numero de pasos de salida se calcula como `duracion / output_time_step`.

## Estructura

```
batch/                 runner del catalogo
config/                configuraciones YAML
inputs/                loaders de configuracion
persistence/           SQLite
scripts/               entrypoints
scripts/tests/         utilitarios/manuales
solvers/sap2000/       integracion SAP2000
results/               salidas (CSV, SQLite)
```
