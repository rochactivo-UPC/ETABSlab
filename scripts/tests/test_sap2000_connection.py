from solvers.sap2000.connect import Sap2000Connection
MODEL_PATH = r"C:\Users\rocha\Desktop\SAP2000 test\test.sdb"

sap = Sap2000Connection()
sap_model = sap.connect()
sap.open_model(MODEL_PATH)

print("Conexión a SAP2000 OK")
