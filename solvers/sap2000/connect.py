import comtypes.client
import comtypes.gen.SAP2000v1
from comtypes import COMError


class Sap2000Connection:
    """
    Conexión robusta a una instancia ABIERTA de SAP2000.
    """

    def __init__(self):
        self.sap_object = None
        self.sap_model = None

    def connect(self):
        """
        Conecta a una instancia abierta de SAP2000.
        """
        try:
            helper = comtypes.client.CreateObject("SAP2000v1.Helper")
            helper = helper.QueryInterface(
                comtypes.gen.SAP2000v1.cHelper
            )

            self.sap_object = helper.GetObject(
                "CSI.SAP2000.API.SapObject"
            )

            self.sap_model = self.sap_object.SapModel

        except (OSError, COMError):
            raise RuntimeError(
                "No se encontró una instancia abierta de SAP2000. "
                "Abra SAP2000 manualmente antes de ejecutar el script."
            )

        return self.sap_model

    def open_model(self, model_path: str):
        """
        Abre un modelo .sdb existente.
        """
        ret = self.sap_model.File.OpenFile(model_path)

        if ret != 0:
            raise RuntimeError(
                f"No se pudo abrir el modelo SAP2000: {model_path}"
            )

def get_sap2000_model():
    """
    API pública estandarizada para obtener SapModel.

    Returns
    -------
    SapModel
        Objeto SapModel conectado a una instancia abierta de SAP2000.
    """
    conn = Sap2000Connection()
    return conn.connect()
