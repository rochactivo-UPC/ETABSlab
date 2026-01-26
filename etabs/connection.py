# etabs/connection.py

import comtypes.client
import comtypes.gen.ETABSv1
import os

class EtabsConnection:
    def __init__(self, etabs_path, attach=True):
        self.etabs_path = etabs_path
        self.attach = attach
        self.etabs_object = None
        self.sap_model = None

    def connect(self):
        import comtypes.client
        from comtypes import COMError
        from comtypes.gen.ETABSv1 import cSapModel


        helper = comtypes.client.CreateObject("ETABSv1.Helper")
        helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)

        try:
            self.etabs_object = helper.GetObject("CSI.ETABS.API.ETABSObject")
        except (OSError, COMError):
            raise RuntimeError(
                "No se encontró una instancia abierta de ETABS. "
                "Abra ETABS manualmente antes de ejecutar el script."
            )

        self.sap_model = self.etabs_object.SapModel
        # self.sap_model = self.sap_model.QueryInterface(cSapModel)

        return self.sap_model


    def open_model(self, model_path):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

        ret = self.sap_model.File.OpenFile(model_path)
        if ret != 0:
            raise RuntimeError("ETABS no pudo abrir el modelo")

    def run_analysis(self):
        return self.sap_model.Analyze.RunAnalysis()