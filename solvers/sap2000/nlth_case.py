"""
nlth_case.py
Helpers to create or update nonlinear direct-history cases in SAP2000.
"""


def create_or_update_nlth_case(
    sap_model,
    case_name,
    func_x,
    func_y,
    scale_x=1.0,
    scale_y=1.0,
    dt=0.01,
    n_steps=5000,
    output_time_step=0.05,
    output_steps=None,
    p_delta=True,
    max_iterations=30,
    apply_parameters=True,
    damping=None,
    time_integration=None,
    nonlinear_parameters=None,
    initial_conditions=None,
    initial_case=None,
    inherit_from_case=None,
):
    """
    Create or update a nonlinear direct-history load case.

    If the case already exists and ``apply_parameters`` is False, the function
    preserves the existing structural parameters while updating loads, output
    step and initial case.

    If the case does not exist and ``apply_parameters`` is False, the function
    can inherit structural parameters from ``inherit_from_case``.
    """

    def _parse_ret_tuple(result):
        if not isinstance(result, (list, tuple)):
            return None, None
        if len(result) == 0:
            return None, None
        if isinstance(result[-1], int):
            return result[-1], list(result[:-1])
        return 0, list(result)

    def _case_exists():
        try:
            result = sap_model.LoadCases.GetNameList()
        except Exception:
            return False
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            return False
        names = None
        for item in result:
            if isinstance(item, (list, tuple)):
                names = item
                break
        if names is None:
            last = result[-1]
            if isinstance(last, str):
                names = [last]
        if names is None:
            return False
        return case_name in names

    def _call_get(method_name, target_case_name=None):
        method = getattr(sap_model.LoadCases.DirHistNonlinear, method_name, None)
        if method is None:
            return None, None
        try:
            result = method(target_case_name or case_name)
        except Exception:
            return None, None
        ret, values = _parse_ret_tuple(result)
        if ret is None or ret != 0:
            return None, None
        return values, method_name

    def _read_case_params(target_case_name):
        params = {}
        values, _ = _call_get("GetTimeIntegration", target_case_name)
        if values and len(values) >= 5:
            params["time_integration"] = values[:5]

        values, _ = _call_get("GetSolControlParameters", target_case_name)
        if values and len(values) >= 10:
            params["sol_control"] = values[:10]

        values, _ = _call_get("GetDampProportional", target_case_name)
        if values:
            params["damp_proportional"] = values

        values, _ = _call_get("GetDampConstant", target_case_name)
        if values:
            params["damp_constant"] = values

        values, _ = _call_get("GetGeometricNonlinearity", target_case_name)
        if values:
            params["geometric_nonlinearity"] = values[0]

        return params

    def _restore_case_params(target_case_name, params):
        if not params:
            return

        geom_value = params.get("geometric_nonlinearity")
        if geom_value is not None:
            method = getattr(
                sap_model.LoadCases.DirHistNonlinear, "SetGeometricNonlinearity", None
            )
            if method is not None:
                ret = method(target_case_name, int(geom_value))
                if ret != 0:
                    raise RuntimeError(
                        f"Error restaurando geometric nonlinearity en {target_case_name} (ret={ret})"
                    )

        time_integration_vals = params.get("time_integration")
        if time_integration_vals and len(time_integration_vals) >= 5:
            method, alpha, beta, gamma, theta = time_integration_vals[:5]
            ret = sap_model.LoadCases.DirHistNonlinear.SetTimeIntegration(
                target_case_name,
                int(method),
                float(alpha),
                float(beta),
                float(gamma),
                float(theta),
            )
            if ret != 0:
                raise RuntimeError(
                    f"Error restaurando time integration en {target_case_name} (ret={ret})"
                )

        sol_control_vals = params.get("sol_control")
        if sol_control_vals and len(sol_control_vals) >= 10:
            ret = sap_model.LoadCases.DirHistNonlinear.SetSolControlParameters(
                target_case_name,
                float(sol_control_vals[0]),
                float(sol_control_vals[1]),
                int(sol_control_vals[2]),
                int(sol_control_vals[3]),
                float(sol_control_vals[4]),
                bool(sol_control_vals[5]),
                float(sol_control_vals[6]),
                int(sol_control_vals[7]),
                float(sol_control_vals[8]),
                float(sol_control_vals[9]),
            )
            if ret != 0:
                raise RuntimeError(
                    f"Error restaurando nonlinear parameters en {target_case_name} (ret={ret})"
                )

        damp_vals = params.get("damp_proportional")
        if damp_vals:
            ret = sap_model.LoadCases.DirHistNonlinear.SetDampProportional(
                target_case_name, *damp_vals
            )
            if ret != 0:
                raise RuntimeError(
                    f"Error restaurando damping proportional en {target_case_name} (ret={ret})"
                )
        elif params.get("damp_constant"):
            ret = sap_model.LoadCases.DirHistNonlinear.SetDampConstant(
                target_case_name,
                float(params["damp_constant"][0]),
            )
            if ret != 0:
                raise RuntimeError(
                    f"Error restaurando damping constant en {target_case_name} (ret={ret})"
                )

    def _call_case_method(method_name, args, context):
        if not method_name:
            return
        method = getattr(sap_model.LoadCases.DirHistNonlinear, method_name, None)
        if method is None:
            raise RuntimeError(
                f"Metodo {method_name} no disponible para {context} en {case_name}"
            )
        ret = method(case_name, *args)
        ret_code = ret[-1] if isinstance(ret, (list, tuple)) else ret
        if ret_code != 0:
            raise RuntimeError(
                f"Error ejecutando {method_name} en el caso {case_name} (ret={ret_code})"
            )

    case_exists = _case_exists()
    preserve_params = None
    if case_exists and not apply_parameters:
        preserve_params = _read_case_params(case_name)
    elif (not case_exists) and (not apply_parameters) and inherit_from_case:
        preserve_params = _read_case_params(str(inherit_from_case))

    if not case_exists:
        sap_model.LoadCases.DirHistNonlinear.SetCase(case_name)

    number_loads = 2
    load_type = ["Accel", "Accel"]
    load_name = ["U1", "U2"]
    func = [func_x, func_y]
    sf = [float(scale_x), float(scale_y)]
    tf = [1.0, 1.0]
    at = [0.0, 0.0]
    csys = ["Global", "Global"]
    ang = [0.0, 0.0]

    ret = sap_model.LoadCases.DirHistNonlinear.SetLoads(
        case_name,
        number_loads,
        load_type,
        load_name,
        func,
        sf,
        tf,
        at,
        csys,
        ang,
    )
    if ret[-1] != 0:
        raise RuntimeError(
            f"Error asignando cargas dinamicas al caso {case_name} (ret={ret})"
        )

    if not case_exists:
        sap_model.LoadCases.DirHistNonlinear.SetMassSource(case_name, "Default")

    if apply_parameters and not case_exists:
        geom_method = getattr(
            sap_model.LoadCases.DirHistNonlinear, "SetGeometricNonlinearity", None
        )
        if geom_method is not None:
            ret = geom_method(case_name, 1 if bool(p_delta) else 0)
            if ret != 0:
                raise RuntimeError(
                    f"Error configurando geometric nonlinearity en el caso {case_name} (ret={ret})"
                )

        if damping:
            if not isinstance(damping, dict):
                raise ValueError("damping debe ser un dict con method y args")
            method_name = damping.get("method")
            args = damping.get("args", [])
            if args is None:
                args = []
            if not isinstance(args, (list, tuple)):
                raise ValueError("damping.args debe ser lista")
            _call_case_method(method_name, args, "damping")

        TIME_INTEGRATION_NEWMARK = 1
        time_integration = time_integration or {}
        if not isinstance(time_integration, dict):
            raise ValueError("time_integration debe ser un dict")

        method = time_integration.get("method", "newmark")
        if isinstance(method, str):
            method_map = {"newmark": TIME_INTEGRATION_NEWMARK}
            method = method_map.get(method.lower(), TIME_INTEGRATION_NEWMARK)

        alpha = float(time_integration.get("alpha", 0.0))
        beta = float(time_integration.get("beta", 0.25))
        gamma = float(time_integration.get("gamma", 0.50))
        theta = float(time_integration.get("theta", 0.0))

        ret = sap_model.LoadCases.DirHistNonlinear.SetTimeIntegration(
            case_name,
            int(method),
            alpha,
            beta,
            gamma,
            theta,
        )
        if ret != 0:
            raise RuntimeError(
                f"Error configurando integracion temporal en el caso {case_name}"
            )

    if apply_parameters and nonlinear_parameters and not case_exists:
        if not isinstance(nonlinear_parameters, dict):
            raise ValueError("nonlinear_parameters debe ser un dict")

        dt_max = float(nonlinear_parameters.get("dt_max", dt))
        dt_min = float(nonlinear_parameters.get("dt_min", dt / 10.0))
        if "dt_max_factor" in nonlinear_parameters:
            dt_max = float(nonlinear_parameters["dt_max_factor"]) * dt
        if "dt_min_factor" in nonlinear_parameters:
            dt_min = float(nonlinear_parameters["dt_min_factor"]) * dt

        max_iter_cs = int(nonlinear_parameters.get("max_iter_cs", 10))
        max_iter_nr = int(nonlinear_parameters.get("max_iter_nr", 50))
        tol_conv_d = float(nonlinear_parameters.get("tol_conv_d", 1.0e-4))
        use_event_stepping = bool(nonlinear_parameters.get("use_event_stepping", True))
        tol_event_d = float(nonlinear_parameters.get("tol_event_d", 1.0e-3))
        max_line_search_per_iter = int(
            nonlinear_parameters.get("max_line_search_per_iter", 5)
        )
        tol_line_search = float(nonlinear_parameters.get("tol_line_search", 0.8))
        line_search_step_fact = float(
            nonlinear_parameters.get("line_search_step_fact", 0.5)
        )

        ret = sap_model.LoadCases.DirHistNonlinear.SetSolControlParameters(
            case_name,
            dt_max,
            dt_min,
            max_iter_cs,
            max_iter_nr,
            tol_conv_d,
            use_event_stepping,
            tol_event_d,
            max_line_search_per_iter,
            tol_line_search,
            line_search_step_fact,
        )
        if ret != 0:
            raise RuntimeError(
                f"Error configurando parametros de solucion en el caso {case_name}"
            )

    if apply_parameters and initial_conditions and not case_exists:
        if not isinstance(initial_conditions, dict):
            raise ValueError("initial_conditions debe ser un dict con method y args")
        method_name = initial_conditions.get("method")
        args = initial_conditions.get("args", [])
        if args is None:
            args = []
        if not isinstance(args, (list, tuple)):
            raise ValueError("initial_conditions.args debe ser lista")
        _call_case_method(method_name, args, "initial_conditions")

    if output_steps is None:
        output_steps = n_steps

    ret = sap_model.LoadCases.DirHistNonlinear.SetTimeStep(
        case_name,
        int(output_steps),
        float(output_time_step),
    )
    if ret != 0:
        raise RuntimeError(
            f"Error configurando output time step en el caso {case_name}"
        )

    if initial_case is not None:
        init_name = "" if not str(initial_case).strip() else str(initial_case)
        method = getattr(sap_model.LoadCases.DirHistNonlinear, "SetInitialCase", None)
        if method is None:
            raise RuntimeError("Metodo SetInitialCase no disponible en SAP2000")
        ret = method(case_name, init_name)
        if ret != 0:
            raise RuntimeError(
                f"Error configurando initial case en {case_name} (ret={ret})"
            )

    if preserve_params:
        _restore_case_params(case_name, preserve_params)
