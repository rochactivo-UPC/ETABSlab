sap_model = get_sap2000_model()
sap_model.File.OpenFile(r"C:\ruta\modelo.sdb")

results = run_nlth_batch(
    sap_model,
    records,
    case_name="NLTH_BATCH",
)

save_batch_results(results)
