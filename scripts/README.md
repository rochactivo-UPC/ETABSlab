# Scripts

## Estructura esperada

- `data/mat/` contiene los archivos `.mat` de acelerogramas.
- Cada `.mat` debe tener `acc_f_e`, `acc_f_n` y `dt` (en gal = cm/s2).
- Los `.txt` normalizados se generan en `data/normalized/`.
- El catalogo se guarda en `results/catalog.csv`.

## Preproceso

Genera el catalogo y normaliza cada registro:

```bash
python scripts/preprocess_mat_catalog.py
```

## Batch NLTH

1. Edita `MODEL_PATH` en `scripts/run_nlth_batch.py`.
2. Abre SAP2000 manualmente.
3. Ejecuta:

```bash
python scripts/run_nlth_batch.py
```
