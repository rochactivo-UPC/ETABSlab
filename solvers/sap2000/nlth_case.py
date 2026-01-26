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
    p_delta=True,
    max_iterations=30
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
    """

    # -------------------------------------------------
    # 1. Eliminar caso si existe
    # -------------------------------------------------
    # sap_model.LoadCases.Delete(case_name)

    # -------------------------------------------------
    # 2. Crear caso DIRHIST NONLINEAR
    # -------------------------------------------------
    sap_model.LoadCases.DirHistNonlinear.SetCase(case_name)

    # -------------------------------------------------
    # 3. Definir cargas de aceleración
    # -------------------------------------------------
    number_loads = 2

    load_type = ["Accel", "Accel"]
    load_name = ["U1", "U2"]

    func = [func_x, func_y]

    sf = [1.0, 1.0]
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


        # -------------------------------------------------
        # 4. Fuente de masas
        # -------------------------------------------------
        sap_model.LoadCases.DirHistNonlinear.SetMassSource(
            case_name,
            "Default"
        )

    # -----------------------------------------
    # Time integration: Newmark Average
    # -----------------------------------------
    TIME_INTEGRATION_NEWMARK = 1

    alpha = 0.0    # no usado
    beta  = 0.25
    gamma = 0.50
    theta = 0.0    # requerido aunque no se use

    ret = sap_model.LoadCases.DirHistNonlinear.SetTimeIntegration(
        case_name,
        TIME_INTEGRATION_NEWMARK,
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

    dt_max = dt
    dt_min = dt / 10.0

    max_iter_cs = 10
    max_iter_nr = 50

    tol_conv_d = 1.0e-4

    use_event_stepping = True
    tol_event_d = 1.0e-3

    max_line_search_per_iter = 5
    tol_line_search = 0.8
    line_search_step_fact = 0.5

    # ret = sap_model.LoadCases.DirHistNonlinear.SetSolControlParameters(
    #     case_name,
    #     dt_max,
    #     dt_min,
    #     max_iter_cs,
    #     max_iter_nr,
    #     tol_conv_d,
    #     use_event_stepping,
    #     tol_event_d,
    #     max_line_search_per_iter,
    #     tol_line_search,
    #     line_search_step_fact
    # )

    # if ret != 0:
    #     raise RuntimeError(
    #         f"Error configurando parámetros de solución en el caso {case_name}"
    #     )

