from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.nlth_case import create_or_update_nlth_case
from solvers.sap2000.analysis import run_case_and_check_fail

from experiments.accelerograms import (
    read_ascii_accelerogram,
    BiComponentAccelerogram
)

# -------------------------------
# 1. Conectar a SAP2000 (attach)
# -------------------------------
sap_model = get_sap2000_model()

# -------------------------------
# 2. Leer acelerogramas
# -------------------------------
ax = read_ascii_accelerogram(
    "data/raw/acc_x.txt",
    units="m/s2",
    acc_id="ACC_X"
)

ay = read_ascii_accelerogram(
    "data/raw/acc_y.txt",
    units="m/s2",
    acc_id="ACC_Y"
)

acc = BiComponentAccelerogram(ax, ay)

# -------------------------------
# 3. Crear funciones TH
# -------------------------------
fx = ax.write_normalized_file(
    output_dir="data/normalized",
    file_prefix="X_"
)

fy = ay.write_normalized_file(
    output_dir="data/normalized",
    file_prefix="Y_"
)

from solvers.sap2000.nlth import create_or_update_th_function_from_file

create_or_update_th_function_from_file(
    sap_model,
    func_name="TH_X",
    file_path=fx,
    dt=ax.dt
)

create_or_update_th_function_from_file(
    sap_model,
    func_name="TH_Y",
    file_path=fy,
    dt=ay.dt
)

# -------------------------------
# 4. Crear / actualizar caso NLTH
# -------------------------------
case_name = "NLTH_BATCH"

create_or_update_nlth_case(
    sap_model,
    case_name=case_name,
    func_x="TH_X",
    func_y="TH_Y",
    dt=acc.dt,
    n_steps=acc.n_steps
)

# -------------------------------
# 5. Ejecutar análisis
# -------------------------------
ok = run_case_and_check_fail(sap_model, case_name)

if ok:
    print("NLTH_BATCH terminó correctamente")
else:
    print("NLTH_BATCH no terminó")