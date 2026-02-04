"""
nlth_case.py
Definición y configuración de un caso de análisis
Direct Time History NO LINEAL (integración directa) en SAP2000.
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
):
    """
    Crea o actualiza un caso de análisis Direct Time History No Lineal.

    Parameters
    ----------
    sap_model : SapModel
    case_name : str
        Nombre del caso NLTH.
    func_x : str
        Función TH en X.
    func_y : str
        Función TH en Y.
    scale_x, scale_y : float
        Factores de escala.
    dt : float
        Paso de integración.
    n_steps : int
        Número de pasos.
    p_delta : bool
        Activar no linealidad geométrica.
    max_iterations : int
        Máximo de iteraciones por paso.
    apply_parameters : bool
        Si True, aplica damping, time integration, nonlinear parameters e initial conditions.
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
        # Try to find names list/tuple in result
        names = None
        for item in result:
            if isinstance(item, (list, tuple)):
                names = item
                break
        if names is None:
            # Fallback: last element might be a single name
            last = result[-1]
            if isinstance(last, str):
                names = [last]
        if names is None:
            return False
        return case_name in names

    def _call_get(method_name):
        method = getattr(sap_model.LoadCases.DirHistNonlinear, method_name, None)
        if method is None:
            return None, None
        try:
            result = method(case_name)
        except Exception:
            return None, None
        ret, values = _parse_ret_tuple(result)
        if ret is None or ret != 0:
            return None, None
        return values, method_name

    def _read_existing_params():
        params = {}
        # Time integration
        values, _ = _call_get("GetTimeIntegration")
        if values and len(values) >= 5:
            params["time_integration"] = values[:5]
        # Nonlinear solution control parameters
        values, _ = _call_get("GetSolControlParameters")
        if values and len(values) >= 10:
            params["sol_control"] = values[:10]
        # Proportional damping (best effort)
        values, _ = _call_get("GetDampProportional")
        if values:
            params["damp_proportional"] = values
        return params

    def _call_case_method(method_name, args, context):
        if not method_name:
            return
        method = getattr(sap_model.LoadCases.DirHistNonlinear, method_name, None)
        if method is None:
            raise RuntimeError(
                f"Metodo {method_name} no disponible para {context} en {case_name}"
            )
        ret = method(case_name, *args)
        if isinstance(ret, (list, tuple)):
            ret_code = ret[-1]
        else:
            ret_code = ret
        if ret_code != 0:
            raise RuntimeError(
                f"Error ejecutando {method_name} en el caso {case_name} (ret={ret_code})"
            )

    # -------------------------------------------------
    # 1. Eliminar caso si existe
    # -------------------------------------------------
    # sap_model.LoadCases.Delete(case_name)

    # -------------------------------------------------
    # 2. Crear caso DIRHIST NONLINEAR si no existe
    # -------------------------------------------------
    case_exists = _case_exists()
    preserve_params = None
    if case_exists and not apply_parameters:
        preserve_params = _read_existing_params()
    if not case_exists:
        sap_model.LoadCases.DirHistNonlinear.SetCase(case_name)

    # -------------------------------------------------
    # 3. Definir cargas de aceleración
    # -------------------------------------------------
    number_loads = 2

    load_type = ["Accel", "Accel"]
    load_name = ["U1", "U2"]

    func = [func_x, func_y]

    sf = [float(scale_x), float(scale_y)]
    tf = [1.0, 1.0]
    at = [0.0, 0.0]

    csys = ["Global", "Global"]   # ← CLAVE: string vacío
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
        ang
    )

    if ret[-1] != 0:
        raise RuntimeError(
            f"Error asignando cargas dinámicas al caso {case_name} (ret={ret})"
        )

    if not case_exists:
        # -------------------------------------------------
        # 4. Fuente de masas
        # -------------------------------------------------
        sap_model.LoadCases.DirHistNonlinear.SetMassSource(
            case_name,
            "Default"
        )

    if apply_parameters and not case_exists:
        # -----------------------------------------
        # Damping (via method + args)
        # -----------------------------------------
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

        # -----------------------------------------
        # Time integration: Newmark Average
        # -----------------------------------------
        TIME_INTEGRATION_NEWMARK = 1

        time_integration = time_integration or {}
        if not isinstance(time_integration, dict):
            raise ValueError("time_integration debe ser un dict")

        method = time_integration.get("method", "newmark")
        if isinstance(method, str):
            method_map = {"newmark": TIME_INTEGRATION_NEWMARK}
            method = method_map.get(method.lower(), TIME_INTEGRATION_NEWMARK)

        alpha = float(time_integration.get("alpha", 0.0))   # no usado
        beta = float(time_integration.get("beta", 0.25))
        gamma = float(time_integration.get("gamma", 0.50))
        theta = float(time_integration.get("theta", 0.0))   # requerido aunque no se use

        ret = sap_model.LoadCases.DirHistNonlinear.SetTimeIntegration(
            case_name,
            int(method),
            alpha,
            beta,
            gamma,
            theta
        )

        if ret != 0:
            raise RuntimeError(
                f"Error configurando integración temporal en el caso {case_name}"
            )

    # -------------------------------------------------
    # 6. Opciones de solución no lineal
    # -------------------------------------------------

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
            line_search_step_fact
        )

        if ret != 0:
            raise RuntimeError(
                f"Error configurando parámetros de solución en el caso {case_name}"
            )

    # -------------------------------------------------
    # 6b. Initial conditions (via method + args)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 7. Output time step
    # -------------------------------------------------
    if output_steps is None:
        output_steps = n_steps

    ret = sap_model.LoadCases.DirHistNonlinear.SetTimeStep(
        case_name,
        int(output_steps),
        float(output_time_step)
    )

    if ret != 0:
        raise RuntimeError(
            f"Error configurando output time step en el caso {case_name}"
        )

    if preserve_params: # TODO no tocar los parámetros si ya hay un caso existente, simplificar esto
        # Restore any preserved parameters after updates.
        time_integration_vals = preserve_params.get("time_integration")
        if time_integration_vals and len(time_integration_vals) >= 5:
            method, alpha, beta, gamma, theta = time_integration_vals[:5]
            sap_model.LoadCases.DirHistNonlinear.SetTimeIntegration(
                case_name,
                int(method),
                float(alpha),
                float(beta),
                float(gamma),
                float(theta)
            )

        sol_control_vals = preserve_params.get("sol_control")
        if sol_control_vals and len(sol_control_vals) >= 10:
            sap_model.LoadCases.DirHistNonlinear.SetSolControlParameters(
                case_name,
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

        damp_vals = preserve_params.get("damp_proportional")
        if damp_vals:
            sap_model.LoadCases.DirHistNonlinear.SetDampProportional(
                case_name, *damp_vals
            )
