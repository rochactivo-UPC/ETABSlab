def _unpack_results_base_react(result):
    if not isinstance(result, (tuple, list)):
        raise RuntimeError(f"Respuesta BaseReact inesperada: {result}")

    if result and isinstance(result[-1], int):
        ret = int(result[-1])
        values = list(result[:-1])
    else:
        ret = int(result[0]) if result else 0
        values = list(result[1:])
    return ret, values


def get_base_reaction_envelope(sap_model):
    result = sap_model.Results.BaseReact(
        0,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        0.0,
        0.0,
        0.0,
    )
    ret, values = _unpack_results_base_react(result)
    if ret != 0:
        raise RuntimeError(f"BaseReact fallo (ret={ret})")
    if len(values) < 13:
        raise RuntimeError(f"Respuesta BaseReact demasiado corta: {result}")

    # Firma documentada:
    # NumberResults, LoadCase, StepType, StepNum, Fx, Fy, Fz, Mx, My, Mz, gx, gy, gz
    step_num = list(values[3]) if values[3] is not None else []
    fx = list(values[4]) if values[4] is not None else []
    fy = list(values[5]) if values[5] is not None else []

    if not fx or not fy:
        raise RuntimeError("BaseReact sin datos de FX/FY")

    max_vx = max(float(x) for x in fx)
    max_vy = max(float(y) for y in fy)
    min_vx = min(float(x) for x in fx)
    min_vy = min(float(y) for y in fy)

    return {
        "step_num": step_num,
        "fx": fx,
        "fy": fy,
        "max_vx": float(max_vx),
        "max_vy": float(max_vy),
        "min_vx": float(min_vx),
        "min_vy": float(min_vy),
    }
