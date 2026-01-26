from solvers.sap2000.connect import Sap2000Connection
from solvers.sap2000.nlth import create_or_update_th_function_from_file
from experiments.accelerograms import read_ascii_accelerogram, BiComponentAccelerogram

MODEL_PATH = r"C:\Users\rocha\Desktop\SAP2000 test\test.sdb"


# 1. Conectar a SAP2000 (instancia abierta)
sap = Sap2000Connection()
sap_model = sap.connect()
sap.open_model(MODEL_PATH)

# 2. Leer acelerogramas originales
ax = read_ascii_accelerogram("data/raw/acc_x.txt",
                            units="m/s2",
                            acc_id="TEST_X"
                            )
ay = read_ascii_accelerogram("data/raw/acc_y.txt",
                            units="m/s2",
                            acc_id="TEST_Y"
                            )

acc = BiComponentAccelerogram(ax, ay)

# 3. Escribir archivos normalizados
fx = acc.ax.write_normalized_file(
    output_dir="data/normalized",
    file_prefix="X_"
)

fy = acc.ay.write_normalized_file(
    output_dir="data/normalized",
    file_prefix="Y_"
)

# 4. Crear / sobrescribir funciones TH
create_or_update_th_function_from_file(
    sap_model,
    func_name="TH_ACC_X",
    file_path=fx,
    header_lines=3,
    dt=acc.dt
)

create_or_update_th_function_from_file(
    sap_model,
    func_name="TH_ACC_Y",
    file_path=fy,
    header_lines=3,
    dt=acc.dt
)

print("Funciones Time History creadas correctamente en SAP2000")
