# etabs/nlth.py

import numpy as np

def create_or_update_th_function_from_file(
    sap_model,
    func_name: str,
    file_path: str,
    header_lines: int,
    dt: float
):
    """
    Crea o sobrescribe una función Time History en ETABS
    usando SetFromFile (ETABS v22 COM).
    """

    VALUE_TYPE_EQUAL_DT = 1   # valores a dt constante
    FREE_FORMAT = True
    
    shalala =     sap_model.Func.FuncTh
    
    ret = sap_model.Func.FuncTH._invoke(
    "SetFromFile", 
    ("MyFunction",
        func_name,
        file_path,
        header_lines,     # HeadLines
        0,                # PreChars
        1,                # PointsPerLine
        VALUE_TYPE_EQUAL_DT,
        FREE_FORMAT,
        10,               # NumberFixed (ignorado si FreeFormat=True)
        dt
    )
    )

    if ret != 0:
        raise RuntimeError(
            f"Error creando función TH desde archivo: {func_name}"
        )