def select_case_for_output(sap_model, case_name: str) -> None:
    sap_model.Results.Setup.DeselectAllCasesAndCombosForOutput()
    ret = sap_model.Results.Setup.SetCaseSelectedForOutput(case_name)
    if ret != 0:
        raise RuntimeError(f"Error seleccionando caso para output: {case_name}")
