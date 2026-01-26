# scripts/tests

Utilitarios y pruebas manuales. No forman parte del flujo productivo.

Ejemplos:
- `test_edp_nodes.py`: extrae desplazamientos por nodo.
- `test_drift.py`: calcula drifts consecutivos.
- `test_db_write.py`: escribe resultados reales en SQLite.
- `inspect_db.py`: inspecciona y grafica resultados desde SQLite.
- `inspect_jointdispl.py`: debug de `Results.JointDispl`.

Ejecutar desde la raiz del repo, por ejemplo:

```
python scripts/tests/test_edp_nodes.py
```
