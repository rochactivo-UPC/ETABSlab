from pathlib import Path

def create_or_update_th_function_from_file(
    sap_model,
    func_name,
    file_path,
    dt,
    header_lines=3,
    value_type=1
):
    """
    Crea o actualiza una función Time History en SAP2000 desde archivo.

    Parameters
    ----------
    sap_model : SapModel
    func_name : str
    file_path : str
        Ruta absoluta al archivo ASCII.
    dt : float
        Paso de tiempo.
    header_lines : int, optional
        Número de líneas de cabecera (default = 3).
    value_type : int, optional
        1 = valores a dt constante
        2 = tiempo + valor
    """

    file_path = Path(file_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    # SAP2000: si existe, se sobrescribe automáticamente
    ret = sap_model.Func.FuncTH.SetFromFile_1(
        func_name,
        str(file_path),
        header_lines,
        0,          # PreChars
        1,          # PointsPerLine
        value_type,
        True,       # FreeFormat
        10,         # NumberFixed (irrelevante si FreeFormat=True)
        dt
    )

    if ret != 0:
        raise RuntimeError(
            f"Error creando función TH '{func_name}' desde {file_path}"
        )
