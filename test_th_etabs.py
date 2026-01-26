from etabs.connection import EtabsConnection
from experiments.accelerograms import read_ascii_accelerogram, BiComponentAccelerogram
from etabs.nlth import create_or_update_th_function_from_file
from config import MODEL_PATH

# 1. Conectar a ETABS (instancia ya abierta)
etabs = EtabsConnection(etabs_path=None, attach=True)
sap_model = etabs.connect()
etabs.open_model(MODEL_PATH)

# 2. Leer acelerogramas
ax = read_ascii_accelerogram("data/raw/acc_x.txt")
ay = read_ascii_accelerogram("data/raw/acc_y.txt")

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

# 4. Crear funciones TH en ETABS
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

print("Funciones TH creadas desde archivo correctamente")
