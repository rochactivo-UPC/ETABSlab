UNITS_MAP = {
    "lb_in_F": 1,
    "lb_ft_F": 2,
    "kip_in_F": 3,
    "kip_ft_F": 4,
    "kN_mm_C": 5,
    "kN_m_C": 6,
    "kgf_mm_C": 7,
    "kgf_m_C": 8,
    "N_mm_C": 9,
    "N_m_C": 10,
    "Ton_mm_C": 11,
    "Ton_m_C": 12,
    "kN_cm_C": 13,
    "kgf_cm_C": 14,
    "N_cm_C": 15,
    "Ton_cm_C": 16,
}


_G_M_S2 = 9.80665
_M_PER_UNIT = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "in": 0.0254,
    "ft": 0.3048,
}

_FORCE_PER_UNITS_KEY = {
    "lb": "lb",
    "kip": "kip",
    "kN": "kN",
    "kgf": "kgf",
    "N": "N",
    "Ton": "Ton",
}


def _units_length_key(units_value):
    if units_value is None:
        return None
    if isinstance(units_value, int):
        code = units_value
        for name, val in UNITS_MAP.items():
            if val == code:
                units_value = name
                break
    if not isinstance(units_value, str):
        return None
    raw = units_value.strip()
    if not raw:
        return None
    if raw.lower() == "cm":
        return "cm"
    if "_mm_" in raw:
        return "mm"
    if "_cm_" in raw:
        return "cm"
    if "_m_" in raw:
        return "m"
    if raw.startswith("lb_in") or raw.startswith("kip_in"):
        return "in"
    if raw.startswith("lb_ft") or raw.startswith("kip_ft"):
        return "ft"
    return None


def accel_scale_from_units(units_value, accel_in_g=True):
    if not accel_in_g:
        return 1.0
    key = _units_length_key(units_value)
    if key is None:
        raise RuntimeError(
            f"No se pudo inferir longitud desde output_units='{units_value}'."
        )
    return _G_M_S2 / _M_PER_UNIT[key]


def _resolve_units_code(units_value):
    if units_value is None:
        return None
    if isinstance(units_value, int):
        return units_value
    if not isinstance(units_value, str):
        return None

    raw = units_value.strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw.lower() == "cm":
        return UNITS_MAP["kN_cm_C"]

    return UNITS_MAP.get(raw)


def infer_length_unit_label(units_value):
    key = _units_length_key(units_value)
    return key or ""


def infer_force_unit_label(units_value):
    code = _resolve_units_code(units_value)
    if code is not None:
        for name, val in UNITS_MAP.items():
            if val == code:
                units_value = name
                break

    if not isinstance(units_value, str):
        return ""

    raw = units_value.strip()
    if not raw:
        return ""
    if raw.lower() == "cm":
        return "kN"

    token = raw.split("_", 1)[0]
    return _FORCE_PER_UNITS_KEY.get(token, "")


def set_present_units(sap_model, units_value):
    code = _resolve_units_code(units_value)
    if code is None:
        raise RuntimeError(
            f"No se pudo resolver output_units='{units_value}'. "
            "Usa 'cm' o uno de los enums de SAP2000 (p. ej. kN_cm_C)."
        )

    method = getattr(sap_model, "SetPresentUnits", None)
    if method is None:
        raise RuntimeError("SapModel.SetPresentUnits no está disponible.")

    ret = method(int(code))
    if isinstance(ret, (list, tuple)):
        ret = ret[-1]
    if ret != 0:
        raise RuntimeError(f"Error seteando unidades de salida (ret={ret})")
