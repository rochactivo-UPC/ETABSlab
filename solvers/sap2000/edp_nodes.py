import math

import pandas as pd


def _call_joint_displ(sap_model, joint):
    return sap_model.Results.JointDispl(
        joint,
        0,
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
    )


def _get_joint_names(sap_model):
    result = sap_model.PointObj.GetNameList()
    if not isinstance(result, (tuple, list)) or len(result) < 3:
        raise RuntimeError(f"Respuesta GetNameList inesperada: {result}")
    ret, _count, names = result[0], result[1], result[2]
    if ret != 0:
        raise RuntimeError(f"Error obteniendo lista de joints (ret={ret})")
    return set(names)


def get_joint_displ(sap_model, joint: str, validate_joint_name=False) -> dict:
    if validate_joint_name:
        joint_names = _get_joint_names(sap_model)
        if joint not in joint_names:
            raise RuntimeError(f"Joint no encontrado en el modelo: {joint}")

    result = _call_joint_displ(sap_model, joint)
    if not isinstance(result, (tuple, list)) or len(result) < 9:
        raise RuntimeError(f"Respuesta JointDispl inesperada: {result}")

    ret = result[0]

    number_results = None
    obj = None
    elm = None
    load_case = None
    step_type = None
    step_num = None
    u1 = None
    u2 = None
    u3 = None
    r1 = None
    r2 = None
    r3 = None

    if len(result) >= 13 and isinstance(result[12], int):
        number_results = result[12]
        obj = result[1]
        elm = result[2]
        load_case = result[3]
        step_type = result[4]
        step_num = result[5]
        u1 = result[6]
        u2 = result[7]
        u3 = result[8]
        r1 = result[9]
        r2 = result[10]
        r3 = result[11]
    else:
        number_results = result[1]
        obj = result[2]
        elm = result[3]
        load_case = result[4]
        step_type = result[5]
        step_num = result[6]
        u1 = result[7]
        u2 = result[8]
        if len(result) > 9:
            u3 = result[9]
        if len(result) > 10:
            r1 = result[10]
        if len(result) > 11:
            r2 = result[11]
        if len(result) > 12:
            r3 = result[12]

    if isinstance(number_results, tuple):
        number_results = len(number_results)

    has_data = bool(u1) and bool(u2)
    if ret != 0 and not has_data:
        raise RuntimeError(
            f"JointDispl retorno {ret} para {joint}. "
            "Verifica que el caso esta corrido y seleccionado para output."
        )

    if number_results == 0 and not has_data:
        raise RuntimeError(f"JointDispl sin resultados para {joint}")

    return {
        "u1": list(u1) if u1 is not None else [],
        "u2": list(u2) if u2 is not None else [],
        "step_type": list(step_type) if step_type is not None else [],
        "step_num": list(step_num) if step_num is not None else [],
        "obj": list(obj) if obj is not None else [],
        "elm": list(elm) if elm is not None else [],
        "load_case": list(load_case) if load_case is not None else [],
        "u3": list(u3) if u3 is not None else [],
        "r1": list(r1) if r1 is not None else [],
        "r2": list(r2) if r2 is not None else [],
        "r3": list(r3) if r3 is not None else [],
    }


def get_node_max_displacements(sap_model, nodes, validate_joint_name=False):
    rows = []
    for node in nodes:
        disp = get_joint_displ(
            sap_model,
            node.joint,
            validate_joint_name=validate_joint_name,
        )
        u1 = disp["u1"]
        u2 = disp["u2"]
        if not u1 or not u2:
            raise RuntimeError(f"JointDispl sin U1/U2 para {node.joint}")

        u1_max = max(u1)
        u1_min = min(u1)
        u2_max = max(u2)
        u2_min = min(u2)

        rows.append(
            {
                "name": node.name,
                "joint": node.joint,
                "z": float(node.z),
                "u1_max": float(u1_max),
                "u1_min": float(u1_min),
                "u2_max": float(u2_max),
                "u2_min": float(u2_min),
            }
        )

    return pd.DataFrame(
        rows, columns=["name", "joint", "z", "u1_max", "u1_min", "u2_max", "u2_min"]
    )
