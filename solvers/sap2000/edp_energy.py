def _call_link_force(sap_model, link_name, item_type):
    return sap_model.Results.LinkForce(
        link_name,
        item_type,
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
        [],
        [],
        [],
    )


def _call_link_deformation(sap_model, link_name, item_type):
    return sap_model.Results.LinkDeformation(
        link_name,
        item_type,
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
        [],
    )


def _parse_link_force(result):
    if not isinstance(result, (tuple, list)) or len(result) < 8:
        raise RuntimeError(f"Respuesta LinkForce inesperada: {result}")
    # COM often returns (NumberResults, Obj, Elm, PointElm, LoadCase, StepType,
    # StepNum, P, V2, V3, T, M2, M3, ret)
    if isinstance(result[-1], int):
        ret = result[-1]
        values = list(result[:-1])
    else:
        ret = result[0]
        values = list(result[1:])

    if len(values) < 13:
        raise RuntimeError(f"Respuesta LinkForce inesperada: {result}")

    number_results = values[0]
    point_elm = values[3]
    load_case = values[4]
    step_type = values[5]
    step_num = values[6]
    p = values[7]
    v2 = values[8]
    v3 = values[9]
    t = values[10]
    m2 = values[11]
    m3 = values[12]
    return ret, number_results, point_elm, load_case, step_type, step_num, p, v2, v3, t, m2, m3


def _parse_link_deformation(result):
    if not isinstance(result, (tuple, list)) or len(result) < 8:
        raise RuntimeError(f"Respuesta LinkDeformation inesperada: {result}")
    # COM often returns (NumberResults, Obj, Elm, LoadCase, StepType, StepNum,
    # U1, U2, U3, R1, R2, R3, ret)
    if isinstance(result[-1], int):
        ret = result[-1]
        values = list(result[:-1])
    else:
        ret = result[0]
        values = list(result[1:])

    if len(values) < 12:
        raise RuntimeError(f"Respuesta LinkDeformation inesperada: {result}")

    number_results = values[0]
    load_case = values[3]
    step_type = values[4]
    step_num = values[5]
    u1 = values[6]
    u2 = values[7]
    u3 = values[8]
    r1 = values[9]
    r2 = values[10]
    r3 = values[11]
    return ret, number_results, load_case, step_type, step_num, u1, u2, u3, r1, r2, r3


def _integrate_work(force_vals, disp_vals, mode: str = "signed"):
    if not force_vals or not disp_vals:
        return []
    n = min(len(force_vals), len(disp_vals))
    if n < 2:
        return [0.0] * n
    work = [0.0]
    for i in range(1, n):
        f0 = float(force_vals[i - 1])
        f1 = float(force_vals[i])
        du = float(disp_vals[i]) - float(disp_vals[i - 1])
        inc = 0.5 * (f0 + f1) * du
        if mode == "abs":
            inc = abs(inc)
        elif mode == "positive":
            inc = max(0.0, inc)
        work.append(work[-1] + inc)
    return work


def dump_link_force_raw(sap_model, link_name: str):
    # Try object (0), element (1), then group (2) and return first successful.
    tries = []
    for item_type in (0, 1, 2):
        result_force = _call_link_force(sap_model, link_name, item_type)
        try:
            ret_f, n_f, pt_f, lc_f, st_f, sn_f, p, v2, v3, t, m2, m3 = _parse_link_force(
                result_force
            )
        except Exception as exc:
            tries.append((item_type, f"parse_error: {exc}"))
            continue
        tries.append((item_type, ret_f, n_f))
        if ret_f == 0:
            return {
                "item_type": item_type,
                "ret": ret_f,
                "number_results": n_f,
                "point_elm": list(pt_f) if pt_f is not None else [],
                "load_case": list(lc_f) if lc_f is not None else [],
                "step_type": list(st_f) if st_f is not None else [],
                "step_num": list(sn_f) if sn_f is not None else [],
                "p": list(p) if p is not None else [],
                "v2": list(v2) if v2 is not None else [],
                "v3": list(v3) if v3 is not None else [],
                "t": list(t) if t is not None else [],
                "m2": list(m2) if m2 is not None else [],
                "m3": list(m3) if m3 is not None else [],
                "tries": tries,
            }
    return {"tries": tries}


def _get_link_points(sap_model, link_name: str):
    method = getattr(sap_model.LinkObj, "GetPoints", None)
    if method is None:
        return None, None
    try:
        result = method(link_name)
    except Exception:
        return None, None
    if not isinstance(result, (tuple, list)) or len(result) < 3:
        return None, None
    if isinstance(result[-1], int):
        ret = result[-1]
        values = list(result[:-1])
    else:
        ret = result[0]
        values = list(result[1:])
    if ret != 0 or len(values) < 2:
        return None, None
    return values[0], values[1]


def _resolve_point_filter(sap_model, link_name: str, point_elm: str | None):
    if not point_elm:
        return None
    pe = point_elm.strip().lower()
    if pe in ("i-end", "i", "iend"):
        i_pt, _j_pt = _get_link_points(sap_model, link_name)
        return i_pt
    if pe in ("j-end", "j", "jend"):
        _i_pt, j_pt = _get_link_points(sap_model, link_name)
        return j_pt
    return point_elm


def _try_link_results(sap_model, link_name, item_type):
    result_force = _call_link_force(sap_model, link_name, item_type)
    ret_f, _n_f, pt_f, lc_f, st_f, sn_f, p, v2, v3, t, m2, m3 = _parse_link_force(
        result_force
    )
    result_def = _call_link_deformation(sap_model, link_name, item_type)
    ret_d, _n_d, lc_d, st_d, sn_d, u1, u2, u3, r1, r2, r3 = _parse_link_deformation(
        result_def
    )
    return {
        "ret_f": ret_f,
        "ret_d": ret_d,
        "lc_f": lc_f,
        "pt_f": pt_f,
        "st_f": st_f,
        "sn_f": sn_f,
        "sn_d": sn_d,
        "p": p,
        "v2": v2,
        "v3": v3,
        "t": t,
        "m2": m2,
        "m3": m3,
        "u1": u1,
        "u2": u2,
        "u3": u3,
        "r1": r1,
        "r2": r2,
        "r3": r3,
    }


def _align_by_step(force_vals, force_steps, disp_vals, disp_steps):
    if not force_vals or not disp_vals:
        return [], []
    if force_steps and disp_steps:
        disp_map = {}
        for step, val in zip(disp_steps, disp_vals):
            disp_map[step] = val
        aligned_disp = [disp_map.get(step) for step in force_steps]
        # Drop any missing matches
        keep = [i for i, d in enumerate(aligned_disp) if d is not None]
        return (
            [force_vals[i] for i in keep],
            [aligned_disp[i] for i in keep],
        )
    if len(force_vals) != len(disp_vals):
        n = min(len(force_vals), len(disp_vals))
        return force_vals[:n], disp_vals[:n]
    return force_vals, disp_vals


def get_link_force_deformation(
    sap_model,
    link_name: str,
    component: str = "U1_P",
    point_elm: str | None = None,
):
    # Try object (0), element (1), then group (2).
    results = None
    for item_type in (0, 1, 2):
        candidate = _try_link_results(sap_model, link_name, item_type)
        if candidate["ret_f"] == 0 and candidate["ret_d"] == 0:
            results = candidate
            break
    if results is None:
        raise RuntimeError(
            f"LinkForce/LinkDeformation sin resultados para {link_name}. "
            "Verifica caso corrido y seleccionado para output."
        )

    comp = (component or "U1_P").upper().strip()
    force_map = {
        "U1_P": results["p"],
        "U2_V2": results["v2"],
        "U3_V3": results["v3"],
        "R1_T": results["t"],
        "R2_M2": results["m2"],
        "R3_M3": results["m3"],
    }
    disp_map = {
        "U1_P": results["u1"],
        "U2_V2": results["u2"],
        "U3_V3": results["u3"],
        "R1_T": results["r1"],
        "R2_M2": results["r2"],
        "R3_M3": results["r3"],
    }

    if comp not in force_map:
        raise RuntimeError(f"Componente no soportado: {component}")

    force_vals = list(force_map[comp]) if force_map[comp] is not None else []
    disp_vals = list(disp_map[comp]) if disp_map[comp] is not None else []
    step_num = list(results["sn_f"]) if results["sn_f"] is not None else []
    disp_steps = list(results["sn_d"]) if results["sn_d"] is not None else []
    point_vals = list(results["pt_f"]) if results["pt_f"] is not None else []

    if point_elm:
        pe = _resolve_point_filter(sap_model, link_name, point_elm)
        if point_vals and pe is not None:
            pe_norm = str(pe).strip().lower()
            keep = [i for i, p in enumerate(point_vals) if str(p).strip().lower() == pe_norm]
            force_vals = [force_vals[i] for i in keep]
            step_num = [step_num[i] for i in keep] if step_num else []

    force_vals, disp_vals = _align_by_step(
        force_vals, step_num, disp_vals, disp_steps
    )

    return {
        "force": force_vals,
        "disp": disp_vals,
        "step_num": step_num,
        "component": comp,
    }


def get_link_energy(
    sap_model,
    link_name: str,
    component: str = "U1_P",
    point_elm: str | None = None,
    energy_mode: str = "signed",
    include_history: bool = False,
) -> dict:
    # Try object (0), element (1), then group (2).
    tries = []
    results = None
    for item_type in (0, 1, 2):
        candidate = _try_link_results(sap_model, link_name, item_type)
        tries.append((item_type, candidate["ret_f"], candidate["ret_d"]))
        if candidate["ret_f"] == 0 and candidate["ret_d"] == 0:
            results = candidate
            break
    if results is None:
        attempts = ", ".join(
            f"type={t} ret_f={rf} ret_d={rd}" for t, rf, rd in tries
        )
        raise RuntimeError(
            f"LinkForce/LinkDeformation sin resultados para {link_name}. "
            f"Intentos: {attempts}. Verifica caso corrido, seleccionado "
            "para output y nombre/tipo correcto (obj/elm/grupo)."
        )

    lc_f = results["lc_f"]
    st_f = results["st_f"]
    sn_f = list(results["sn_f"]) if results["sn_f"] is not None else []
    sn_d = list(results["sn_d"]) if results["sn_d"] is not None else []
    pt_f = list(results["pt_f"]) if results["pt_f"] is not None else []
    p = results["p"]
    v2 = results["v2"]
    v3 = results["v3"]
    t = results["t"]
    m2 = results["m2"]
    m3 = results["m3"]
    u1 = results["u1"]
    u2 = results["u2"]
    u3 = results["u3"]
    r1 = results["r1"]
    r2 = results["r2"]
    r3 = results["r3"]

    comp = (component or "U1_P").upper().strip()
    force_map = {
        "U1_P": p,
        "U2_V2": v2,
        "U3_V3": v3,
        "R1_T": t,
        "R2_M2": m2,
        "R3_M3": m3,
    }
    disp_map = {
        "U1_P": u1,
        "U2_V2": u2,
        "U3_V3": u3,
        "R1_T": r1,
        "R2_M2": r2,
        "R3_M3": r3,
    }

    if comp not in force_map:
        raise RuntimeError(f"Componente no soportado: {component}")

    force_vals = list(force_map[comp]) if force_map[comp] is not None else []
    disp_vals = list(disp_map[comp]) if disp_map[comp] is not None else []

    if point_elm:
        pe = _resolve_point_filter(sap_model, link_name, point_elm)
        if pt_f and pe is not None:
            pe_norm = str(pe).strip().lower()
            keep = [i for i, pnt in enumerate(pt_f) if str(pnt).strip().lower() == pe_norm]
            force_vals = [force_vals[i] for i in keep]
            if sn_f:
                sn_f = [sn_f[i] for i in keep]

    force_vals, disp_vals = _align_by_step(
        force_vals, sn_f, disp_vals, sn_d
    )
    if not force_vals or not disp_vals:
        return {}

    energy_vals = _integrate_work(force_vals, disp_vals, mode=energy_mode)
    max_energy = max(energy_vals)
    min_energy = min(energy_vals)
    final_energy = energy_vals[-1]
    abs_max = max(abs(v) for v in energy_vals)

    payload = {
        "max": float(max_energy),
        "min": float(min_energy),
        "final": float(final_energy),
        "abs_max": float(abs_max),
        "step_num": list(sn_f) if sn_f is not None else [],
        "step_type": list(st_f) if st_f is not None else [],
        "load_case": list(lc_f) if lc_f is not None else [],
        "component": comp,
    }
    if include_history:
        payload["energy"] = list(energy_vals)
    return payload
