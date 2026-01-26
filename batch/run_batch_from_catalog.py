from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from solvers.sap2000.nlth import create_or_update_th_function_from_file
from solvers.sap2000.nlth_case import create_or_update_nlth_case
from solvers.sap2000.analysis import get_case_status_map


def _load_existing_results(results_path: Path) -> pd.DataFrame:
    if results_path.exists():
        try:
            return pd.read_csv(results_path)
        except EmptyDataError:
            return pd.DataFrame()
    return pd.DataFrame(
        columns=[
            "record_id",
            "finished",
            "ret_getcasestatus",
            "status_code",
            "dt",
            "n_steps",
            "x_txt_path",
            "y_txt_path",
            "error",
        ]
    )


def run_batch_from_catalog(
    sap_model,
    catalog_csv,
    case_name="NLTH_BATCH",
    overwrite_functions=True,
    resume=True
):
    catalog_path = Path(catalog_csv).resolve()
    if not catalog_path.exists():
        raise FileNotFoundError(catalog_path)

    catalog = pd.read_csv(catalog_path)
    results_path = Path("results").resolve() / "batch_results.csv"
    existing = _load_existing_results(results_path)

    finished_ids = set()
    if resume and not existing.empty:
        finished_ids = set(
            existing.loc[existing["finished"] == True, "record_id"].tolist()
        )

    results_rows = []
    total = len(catalog.index)

    for idx, row in catalog.iterrows():
        record_id = str(row["record_id"])
        if resume and record_id in finished_ids:
            continue

        print(f"[{idx + 1}/{total}] {record_id}")

        error = ""
        finished = False
        status_code = None
        ret_getcasestatus = None

        try:
            if row.get("status_preprocess") != "OK":
                raise RuntimeError("Registro con preproceso fallido")

            x_txt = Path(row["x_txt_path"]).resolve()
            y_txt = Path(row["y_txt_path"]).resolve()
            dt = float(row["dt"])
            n_steps = int(row["n_steps"])

            func_x = f"TH_{record_id}_X"
            func_y = f"TH_{record_id}_Y"

            if overwrite_functions:
                create_or_update_th_function_from_file(
                    sap_model,
                    func_name=func_x,
                    file_path=str(x_txt),
                    dt=dt
                )
                create_or_update_th_function_from_file(
                    sap_model,
                    func_name=func_y,
                    file_path=str(y_txt),
                    dt=dt
                )

            create_or_update_nlth_case(
                sap_model,
                case_name=case_name,
                func_x=func_x,
                func_y=func_y,
                dt=dt,
                n_steps=n_steps
            )

            sap_model.Analyze.RunAnalysis()

            case_dict, ret = get_case_status_map(sap_model)
            ret_getcasestatus = ret
            if ret != 0:
                raise RuntimeError("Error llamando a GetCaseStatus")

            if case_name not in case_dict:
                raise RuntimeError(f"Caso {case_name} no encontrado")

            status_code = int(case_dict[case_name])
            finished = status_code == 4
            print(f"  Estado caso {case_name}: {status_code} (Finished={finished})")

        except Exception as exc:
            error = str(exc)
            print(f"  Error: {error}")

        results_rows.append(
            {
                "record_id": record_id,
                "finished": finished,
                "ret_getcasestatus": ret_getcasestatus,
                "status_code": status_code,
                "dt": row.get("dt"),
                "n_steps": row.get("n_steps"),
                "x_txt_path": row.get("x_txt_path"),
                "y_txt_path": row.get("y_txt_path"),
                "error": error,
            }
        )

        updated = pd.concat(
            [existing, pd.DataFrame(results_rows)],
            ignore_index=True
        )
        results_path.parent.mkdir(parents=True, exist_ok=True)
        updated.to_csv(results_path, index=False)

    final_df = pd.concat(
        [existing, pd.DataFrame(results_rows)],
        ignore_index=True
    )
    return final_df
