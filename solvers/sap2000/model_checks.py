from pathlib import Path


def _unpack_ret_value(result):
    if isinstance(result, (tuple, list)):
        if len(result) == 0:
            return None, None
        if len(result) == 1:
            return result[0], None
        return result[0], result[1]
    return 0, result


def _get_model_filename(sap_model):
    result = sap_model.GetModelFilename(True)
    ret, value = _unpack_ret_value(result)
    if ret != 0:
        return None, ret
    return str(value) if value else "", ret


def _get_model_is_locked(sap_model):
    result = sap_model.GetModelIsLocked()
    ret, value = _unpack_ret_value(result)
    if ret != 0:
        return None, ret
    return bool(value), ret


def check_model_loaded_and_unlocked(sap_model, expected_model_path=None, allow_locked=False):
    model_path, ret_path = _get_model_filename(sap_model)
    if ret_path != 0:
        raise RuntimeError(f"Error consultando modelo cargado (ret={ret_path})")
    if not model_path:
        raise RuntimeError("No hay un modelo cargado en la instancia SAP2000")

    if expected_model_path:
        expected = Path(expected_model_path).resolve()
        loaded = Path(model_path).resolve()
        if expected != loaded:
            raise RuntimeError(
                f"Modelo cargado distinto. Esperado: {expected} / Cargado: {loaded}"
            )

    locked, ret_lock = _get_model_is_locked(sap_model)
    if ret_lock != 0:
        raise RuntimeError(f"Error consultando lock del modelo (ret={ret_lock})")
    if locked and not allow_locked:
        raise RuntimeError("El modelo esta bloqueado; libera el lock antes de continuar")

    return model_path
