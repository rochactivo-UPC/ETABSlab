def get_case_status_map(sap_model):
    n, names, status, ret = sap_model.Analyze.GetCaseStatus()
    return dict(zip(names, status)), ret


def run_case_and_check_fail(sap_model, case_name):
    sap_model.Analyze.RunAnalysis()

    case_dict, ret = get_case_status_map(sap_model)

    if ret != 0:
        raise RuntimeError("Error llamando a GetCaseStatus")

    if case_name not in case_dict:
        raise RuntimeError(f"Caso {case_name} no encontrado")

    return case_dict[case_name] == 4
