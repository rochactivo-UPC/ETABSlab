from __future__ import annotations

import sys
import re
import time
from pathlib import Path
from datetime import datetime, timedelta

import yaml
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QToolButton,
    QStyle,
    QTabWidget,
    QHeaderView,
    QSizePolicy,
    QProgressBar,
)
from PySide6.QtGui import QFont, QIcon

PROGRESS_RE = re.compile(r"^\[(\d+)/(\d+)\]")


class SettingsGui(QMainWindow):
    def __init__(self):
        super().__init__()
        if getattr(sys, "frozen", False):
            self.base_dir = Path(sys.executable).resolve().parent
            self.runtime_dir = Path(__file__).resolve().parents[1]
        else:
            self.base_dir = Path(__file__).resolve().parents[1]
            self.runtime_dir = self.base_dir
        self.settings_path = self.base_dir / "config" / "settings.yaml"
        self.process: QProcess | None = None
        self._stdout_buffer = ""
        self._is_batch_run = False
        self._batch_started_at: float | None = None
        self._batch_total = 0
        self._batch_current = 0

        self.setWindowTitle("ETABSlab - Settings + Runner")
        icon_path = self.base_dir / "EQLab.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1200, 900)

        central = QWidget()
        root_layout = QVBoxLayout(central)

        top_box = QGroupBox("Settings")
        top_layout = QHBoxLayout(top_box)
        self.settings_path_edit = QLineEdit(str(self.settings_path))
        self.btn_settings_browse = QPushButton("Seleccionar settings")
        self.btn_load_settings = QToolButton()
        self.btn_load_settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_load_settings.setToolTip("Load settings")
        self.btn_save_settings_top = QToolButton()
        self.btn_save_settings_top.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save_settings_top.setToolTip("Save settings")
        top_layout.addWidget(QLabel("Archivo settings"))
        top_layout.addWidget(self.settings_path_edit, stretch=1)
        top_layout.addWidget(self.btn_settings_browse)
        top_layout.addWidget(self.btn_load_settings)
        top_layout.addWidget(self.btn_save_settings_top)
        root_layout.addWidget(top_box)

        self.tabs = QTabWidget()
        config_tab = QWidget()
        config_tab_layout = QVBoxLayout(config_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        self.form_layout = QVBoxLayout(form_container)
        self.form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(form_container)
        config_tab_layout.addWidget(scroll)
        self.tabs.addTab(config_tab, "Configuracion")

        nodes_tab = self._build_nodes_tab()
        self.tabs.addTab(nodes_tab, "Nodos")
        actions_log_tab = self._build_actions_log_tab()
        self.tabs.addTab(actions_log_tab, "Ejecucion")
        root_layout.addWidget(self.tabs, stretch=1)

        self._build_form()

        self.setCentralWidget(central)

        self.btn_save_settings_top.clicked.connect(self.save_settings)
        self.btn_load_settings.clicked.connect(self.load_settings)
        self.btn_settings_browse.clicked.connect(self._browse_settings)
        self.btn_pre.clicked.connect(self.run_preprocess)
        self.btn_batch.clicked.connect(self.run_batch)
        self.btn_post.clicked.connect(self.run_postprocess)
        self.btn_cancel.clicked.connect(self.cancel_process)
        self.btn_catalog_browse.clicked.connect(self._browse_catalog)
        self.btn_model_browse.clicked.connect(self._browse_model_sdb)
        self.node_count.valueChanged.connect(self._sync_node_rows)
        self.use_ping_pong.toggled.connect(self._update_ping_pong_enabled)
        self.nl_apply_parameters.toggled.connect(self._update_nlth_params_enabled)
        self.enable_link_energy.toggled.connect(self._update_link_energy_enabled)

        self.load_settings()

    def _default_catalog_from_settings(self) -> Path:
        return self.settings_path.parent.parent / "results" / "catalog.csv"

    def _build_form(self):
        cols_widget = QWidget()
        cols_layout = QHBoxLayout(cols_widget)
        left_col_widget = QWidget()
        right_col_widget = QWidget()
        left_col = QVBoxLayout(left_col_widget)
        right_col = QVBoxLayout(right_col_widget)
        cols_layout.addWidget(left_col_widget, stretch=1)
        cols_layout.addWidget(right_col_widget, stretch=1)
        self.form_layout.addWidget(cols_widget)

        main_group = QGroupBox("Configuracion principal")
        main_form = QFormLayout(main_group)
        self.model_path = QLineEdit()
        self.btn_model_browse = QPushButton("Seleccionar .sdb")
        self.case_name = QLineEdit()
        self.use_ping_pong = QCheckBox()
        self.ping_case_a = QLineEdit()
        self.ping_case_b = QLineEdit()
        self.initial_gravity_case = QLineEdit()
        self.checkpoint_every = QSpinBox()
        self.checkpoint_every.setRange(0, 1_000_000)
        self.clear_results_after_edp = QCheckBox()
        self.overwrite_db = QCheckBox()
        self.output_time_step = QDoubleSpinBox()
        self.output_time_step.setDecimals(6)
        self.output_time_step.setRange(0.0, 1_000.0)
        self.output_units = QLineEdit()
        self.accel_in_g = QCheckBox()

        model_row = QHBoxLayout()
        model_row.addWidget(self.model_path)
        model_row.addWidget(self.btn_model_browse)
        model_row_widget = QWidget()
        model_row_widget.setLayout(model_row)
        main_form.addRow("model_path", model_row_widget)
        main_form.addRow("case_name", self.case_name)
        main_form.addRow("use_ping_pong", self.use_ping_pong)
        main_form.addRow("ping_pong_case_A", self.ping_case_a)
        main_form.addRow("ping_pong_case_B", self.ping_case_b)
        main_form.addRow("initial_gravity_case", self.initial_gravity_case)
        main_form.addRow("checkpoint_every", self.checkpoint_every)
        main_form.addRow("clear_results_after_edp", self.clear_results_after_edp)
        main_form.addRow("overwrite_db", self.overwrite_db)
        main_form.addRow("output_time_step", self.output_time_step)
        main_form.addRow("output_units", self.output_units)
        main_form.addRow("accel_in_g", self.accel_in_g)
        left_col.addWidget(main_group)

        run_group = QGroupBox("Ejecucion")
        run_layout = QFormLayout(run_group)
        self.catalog_path = QLineEdit(str(self._default_catalog_from_settings()))
        self.btn_catalog_browse = QPushButton("Seleccionar catalogo")
        row = QHBoxLayout()
        row.addWidget(self.catalog_path)
        row.addWidget(self.btn_catalog_browse)
        row_widget = QWidget()
        row_widget.setLayout(row)
        run_layout.addRow("Catalogo batch", row_widget)
        left_col.addWidget(run_group)

        energy_group = QGroupBox("Energia de links")
        energy_form = QFormLayout(energy_group)
        self.enable_link_energy = QCheckBox()
        self.energy_link = QLineEdit()
        self.energy_component = QLineEdit()
        self.energy_point_elm = QLineEdit()
        self.energy_mode = QLineEdit()
        energy_form.addRow("enable_link_energy", self.enable_link_energy)
        energy_form.addRow("energy_link", self.energy_link)
        energy_form.addRow("energy_component", self.energy_component)
        energy_form.addRow("energy_point_elm", self.energy_point_elm)
        energy_form.addRow("energy_mode", self.energy_mode)
        left_col.addWidget(energy_group)

        nlth_group = QGroupBox("nlth_case")
        nlth_form = QFormLayout(nlth_group)
        self.nl_apply_parameters = QCheckBox()
        self.nl_p_delta = QCheckBox()
        self.nl_initial_case = QLineEdit()
        self.damping_method = QLineEdit()
        self.damping_args = QLineEdit()
        self.ti_method = QLineEdit()
        self.ti_alpha = QLineEdit()
        self.ti_beta = QLineEdit()
        self.ti_gamma = QLineEdit()
        self.ti_theta = QLineEdit()
        self.np_dt_max_factor = QLineEdit()
        self.np_dt_min_factor = QLineEdit()
        self.np_max_iter_cs = QLineEdit()
        self.np_max_iter_nr = QLineEdit()
        self.np_tol_conv_d = QLineEdit()
        self.np_use_event_stepping = QCheckBox()
        self.np_tol_event_d = QLineEdit()
        self.np_max_line_search_per_iter = QLineEdit()
        self.np_tol_line_search = QLineEdit()
        self.np_line_search_step_fact = QLineEdit()
        self.ic_method = QLineEdit()
        self.ic_args = QLineEdit()

        nlth_form.addRow("apply_parameters", self.nl_apply_parameters)
        nlth_form.addRow("p_delta", self.nl_p_delta)
        nlth_form.addRow("initial_case", self.nl_initial_case)
        nlth_form.addRow("damping.method", self.damping_method)
        nlth_form.addRow("damping.args (yaml list)", self.damping_args)
        nlth_form.addRow("time_integration.method", self.ti_method)
        nlth_form.addRow("time_integration.alpha", self.ti_alpha)
        nlth_form.addRow("time_integration.beta", self.ti_beta)
        nlth_form.addRow("time_integration.gamma", self.ti_gamma)
        nlth_form.addRow("time_integration.theta", self.ti_theta)
        nlth_form.addRow("nonlinear.dt_max_factor", self.np_dt_max_factor)
        nlth_form.addRow("nonlinear.dt_min_factor", self.np_dt_min_factor)
        nlth_form.addRow("nonlinear.max_iter_cs", self.np_max_iter_cs)
        nlth_form.addRow("nonlinear.max_iter_nr", self.np_max_iter_nr)
        nlth_form.addRow("nonlinear.tol_conv_d", self.np_tol_conv_d)
        nlth_form.addRow("nonlinear.use_event_stepping", self.np_use_event_stepping)
        nlth_form.addRow("nonlinear.tol_event_d", self.np_tol_event_d)
        nlth_form.addRow("nonlinear.max_line_search_per_iter", self.np_max_line_search_per_iter)
        nlth_form.addRow("nonlinear.tol_line_search", self.np_tol_line_search)
        nlth_form.addRow("nonlinear.line_search_step_fact", self.np_line_search_step_fact)
        nlth_form.addRow("initial_conditions.method", self.ic_method)
        nlth_form.addRow("initial_conditions.args (yaml list)", self.ic_args)
        right_col.addWidget(nlth_group)



    def _build_nodes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        header = QHBoxLayout()
        self.node_count = QSpinBox()
        self.node_count.setRange(0, 10_000)
        header.addWidget(QLabel("Numero de nodos"))
        header.addWidget(self.node_count)
        header.addStretch(1)
        layout.addLayout(header)
        self.nodes_table = QTableWidget(0, 3)
        self.nodes_table.setHorizontalHeaderLabels(["name", "joint", "z"])
        self.nodes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.nodes_table.setMinimumHeight(420)
        layout.addWidget(self.nodes_table)
        return tab

    def _build_actions_log_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        actions_box = QGroupBox("Acciones")
        actions_layout = QVBoxLayout(actions_box)
        self.btn_pre = QPushButton("Preprocesar BD")
        self.btn_batch = QPushButton("Ejecutar batch")
        self.btn_post = QPushButton("Post procesar SQL")
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_load_nodes = QPushButton("Cargar nodos desde modelo (pendiente)")
        self.btn_load_nodes.setEnabled(False)

        button_font = QFont()
        button_font.setPointSize(11)
        for btn in [self.btn_pre, self.btn_batch, self.btn_post, self.btn_cancel, self.btn_load_nodes]:
            btn.setFont(button_font)
            btn.setMinimumHeight(44)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        actions_layout.addWidget(self.btn_pre)
        actions_layout.addWidget(self.btn_batch)
        actions_layout.addWidget(self.btn_post)
        actions_layout.addWidget(self.btn_cancel)
        actions_layout.addWidget(self.btn_load_nodes)
        actions_layout.addStretch(1)
        actions_box.setMaximumWidth(360)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        progress_box = QGroupBox("Progreso batch")
        progress_layout = QVBoxLayout(progress_box)
        self.batch_progress = QProgressBar()
        self.batch_progress.setMinimum(0)
        self.batch_progress.setMaximum(100)
        self.batch_progress.setValue(0)
        self.lbl_batch_counts = QLabel("Progreso: -")
        self.lbl_eta = QLabel("ETA: -")
        self.lbl_total_est = QLabel("Tiempo total estimado: -")
        self.lbl_avg = QLabel("Promedio por analisis: -")
        progress_layout.addWidget(self.batch_progress)
        progress_layout.addWidget(self.lbl_batch_counts)
        progress_layout.addWidget(self.lbl_eta)
        progress_layout.addWidget(self.lbl_total_est)
        progress_layout.addWidget(self.lbl_avg)
        right_layout.addWidget(progress_box)

        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_box, stretch=1)

        layout.addWidget(actions_box, stretch=1)
        layout.addWidget(right, stretch=3)
        return tab

    def _append_log(self, text: str):
        self.log_text.append(text.rstrip())

    def _format_duration(self, seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        total = int(round(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _reset_batch_progress(self):
        self._stdout_buffer = ""
        self._batch_started_at = None
        self._batch_total = 0
        self._batch_current = 0
        self.batch_progress.setMinimum(0)
        self.batch_progress.setMaximum(100)
        self.batch_progress.setValue(0)
        self.lbl_batch_counts.setText("Progreso: -")
        self.lbl_eta.setText("ETA: -")
        self.lbl_total_est.setText("Tiempo total estimado: -")
        self.lbl_avg.setText("Promedio por analisis: -")

    def _handle_output_line(self, line: str):
        if not self._is_batch_run:
            return
        m = PROGRESS_RE.match(line.strip())
        if not m:
            return
        current = int(m.group(1))
        total = int(m.group(2))
        if total <= 0:
            return
        if self._batch_started_at is None:
            self._batch_started_at = time.monotonic()
        self._batch_current = current
        self._batch_total = total
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(min(current, total))
        self.lbl_batch_counts.setText(f"Progreso: {current}/{total}")

        elapsed = time.monotonic() - self._batch_started_at
        if current > 0:
            avg = elapsed / current
            total_est = avg * total
            remaining = max(0, total - current) * avg
            eta = datetime.now() + timedelta(seconds=remaining)
            self.lbl_avg.setText(f"Promedio por analisis: {self._format_duration(avg)}")
            self.lbl_total_est.setText(f"Tiempo total estimado: {self._format_duration(total_est)}")
            self.lbl_eta.setText(f"ETA: {eta.strftime('%Y-%m-%d %H:%M:%S')}")

    def _sync_node_rows(self, count: int):
        current = self.nodes_table.rowCount()
        self.nodes_table.setRowCount(count)
        for i in range(current, count):
            for j in range(3):
                self.nodes_table.setItem(i, j, QTableWidgetItem(""))

    def _browse_catalog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar catalogo CSV",
            str(self.base_dir / "results"),
            "CSV (*.csv)",
        )
        if path:
            self.catalog_path.setText(path)

    def _browse_model_sdb(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar modelo SAP2000 (.sdb)",
            str(self.base_dir),
            "SAP2000 Model (*.sdb)",
        )
        if path:
            self.model_path.setText(path)

    def _browse_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar settings.yaml",
            str(self.base_dir / "config"),
            "YAML (*.yaml *.yml)",
        )
        if path:
            self.settings_path_edit.setText(path)
            self.settings_path = Path(path).resolve()
            default_catalog = self._default_catalog_from_settings().resolve()
            current_catalog = self.catalog_path.text().strip()
            if (not current_catalog) or (not Path(current_catalog).exists()):
                self.catalog_path.setText(str(default_catalog))
            self.load_settings()

    def _update_ping_pong_enabled(self):
        enabled = self.use_ping_pong.isChecked()
        for widget in [
            self.ping_case_a,
            self.ping_case_b,
            self.initial_gravity_case,
        ]:
            widget.setEnabled(enabled)

    def _update_nlth_params_enabled(self):
        enabled = self.nl_apply_parameters.isChecked()
        for widget in [
            self.damping_method,
            self.damping_args,
            self.ti_method,
            self.ti_alpha,
            self.ti_beta,
            self.ti_gamma,
            self.ti_theta,
            self.np_dt_max_factor,
            self.np_dt_min_factor,
            self.np_max_iter_cs,
            self.np_max_iter_nr,
            self.np_tol_conv_d,
            self.np_use_event_stepping,
            self.np_tol_event_d,
            self.np_max_line_search_per_iter,
            self.np_tol_line_search,
            self.np_line_search_step_fact,
            self.ic_method,
            self.ic_args,
        ]:
            widget.setEnabled(enabled)

    def _update_link_energy_enabled(self):
        enabled = self.enable_link_energy.isChecked()
        for widget in [
            self.energy_link,
            self.energy_component,
            self.energy_point_elm,
            self.energy_mode,
        ]:
            widget.setEnabled(enabled)

    def _parse_yaml_list(self, raw: str):
        value = yaml.safe_load(raw) if raw.strip() else []
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Se esperaba una lista YAML")
        return value

    def load_settings(self):
        current = self.settings_path_edit.text().strip()
        if current:
            self.settings_path = Path(current).resolve()
        self.settings_path_edit.setText(str(self.settings_path))
        default_catalog = self._default_catalog_from_settings().resolve()
        current_catalog = self.catalog_path.text().strip()
        if (not current_catalog) or (not Path(current_catalog).exists()):
            self.catalog_path.setText(str(default_catalog))
        if not self.settings_path.exists():
            QMessageBox.critical(self, "Error", f"No existe {self.settings_path}")
            return
        with self.settings_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        self.model_path.setText(str(data.get("model_path", "")))
        self.case_name.setText(str(data.get("case_name", "")))
        self.use_ping_pong.setChecked(bool(data.get("use_ping_pong", False)))
        ping = data.get("ping_pong_cases", ["NLTH_A", "NLTH_B"])
        self.ping_case_a.setText(str(ping[0] if len(ping) > 0 else "NLTH_A"))
        self.ping_case_b.setText(str(ping[1] if len(ping) > 1 else "NLTH_B"))
        self.initial_gravity_case.setText(str(data.get("initial_gravity_case", "")))
        self.checkpoint_every.setValue(int(data.get("checkpoint_every", 10)))
        self.clear_results_after_edp.setChecked(bool(data.get("clear_results_after_edp", False)))
        self.overwrite_db.setChecked(bool(data.get("overwrite_db", False)))
        self.output_time_step.setValue(float(data.get("output_time_step", 0.05)))
        self.output_units.setText(str(data.get("output_units", "cm")))
        self.accel_in_g.setChecked(bool(data.get("accel_in_g", True)))

        self.enable_link_energy.setChecked(bool(data.get("enable_link_energy", False)))
        self.energy_link.setText(str(data.get("energy_link", "")))
        self.energy_component.setText(str(data.get("energy_component", "U1_P")))
        self.energy_point_elm.setText(str(data.get("energy_point_elm", "I-End")))
        self.energy_mode.setText(str(data.get("energy_mode", "signed")))

        nlth = data.get("nlth_case", {}) or {}
        damp = nlth.get("damping", {}) or {}
        ti = nlth.get("time_integration", {}) or {}
        np = nlth.get("nonlinear_parameters", {}) or {}
        ic = nlth.get("initial_conditions", {}) or {}
        self.nl_apply_parameters.setChecked(bool(nlth.get("apply_parameters", True)))
        self.nl_p_delta.setChecked(bool(nlth.get("p_delta", True)))
        self.nl_initial_case.setText(str(nlth.get("initial_case", "NL DL+0.25LL")))
        self.damping_method.setText(str(damp.get("method", "")))
        self.damping_args.setText(yaml.safe_dump(damp.get("args", []), default_flow_style=True).strip())
        self.ti_method.setText(str(ti.get("method", "newmark")))
        self.ti_alpha.setText(str(ti.get("alpha", 0.0)))
        self.ti_beta.setText(str(ti.get("beta", 0.25)))
        self.ti_gamma.setText(str(ti.get("gamma", 0.5)))
        self.ti_theta.setText(str(ti.get("theta", 0.0)))
        self.np_dt_max_factor.setText(str(np.get("dt_max_factor", 1.0)))
        self.np_dt_min_factor.setText(str(np.get("dt_min_factor", 0.2)))
        self.np_max_iter_cs.setText(str(np.get("max_iter_cs", 6)))
        self.np_max_iter_nr.setText(str(np.get("max_iter_nr", 20)))
        self.np_tol_conv_d.setText(str(np.get("tol_conv_d", 0.001)))
        self.np_use_event_stepping.setChecked(bool(np.get("use_event_stepping", True)))
        self.np_tol_event_d.setText(str(np.get("tol_event_d", 0.005)))
        self.np_max_line_search_per_iter.setText(str(np.get("max_line_search_per_iter", 3)))
        self.np_tol_line_search.setText(str(np.get("tol_line_search", 0.8)))
        self.np_line_search_step_fact.setText(str(np.get("line_search_step_fact", 2.0)))
        self.ic_method.setText(str(ic.get("method", "")))
        self.ic_args.setText(yaml.safe_dump(ic.get("args", []), default_flow_style=True).strip())

        nodes = data.get("nodes", []) or []
        self.node_count.setValue(len(nodes))
        self._sync_node_rows(len(nodes))
        self.nodes_table.clearContents()
        for i, node in enumerate(nodes):
            self.nodes_table.setItem(i, 0, QTableWidgetItem(str(node.get("name", ""))))
            self.nodes_table.setItem(i, 1, QTableWidgetItem(str(node.get("joint", ""))))
            self.nodes_table.setItem(i, 2, QTableWidgetItem(str(node.get("z", 0.0))))
        self._update_ping_pong_enabled()
        self._update_nlth_params_enabled()
        self._update_link_energy_enabled()

    def _collect_nodes(self):
        nodes = []
        for i in range(self.nodes_table.rowCount()):
            name_item = self.nodes_table.item(i, 0)
            joint_item = self.nodes_table.item(i, 1)
            z_item = self.nodes_table.item(i, 2)
            name = (name_item.text() if name_item else "").strip()
            joint = (joint_item.text() if joint_item else "").strip()
            z_raw = (z_item.text() if z_item else "").strip()
            if not name and not joint and not z_raw:
                continue
            nodes.append(
                {
                    "name": name,
                    "joint": joint,
                    "z": float(z_raw),
                }
            )
        return nodes

    def _build_settings_dict(self):
        return {
            "model_path": self.model_path.text().strip(),
            "case_name": self.case_name.text().strip(),
            "use_ping_pong": self.use_ping_pong.isChecked(),
            "ping_pong_cases": [self.ping_case_a.text().strip(), self.ping_case_b.text().strip()],
            "initial_gravity_case": self.initial_gravity_case.text().strip(),
            "checkpoint_every": int(self.checkpoint_every.value()),
            "clear_results_after_edp": self.clear_results_after_edp.isChecked(),
            "energy_link": self.energy_link.text().strip(),
            "enable_link_energy": self.enable_link_energy.isChecked(),
            "energy_component": self.energy_component.text().strip(),
            "energy_point_elm": self.energy_point_elm.text().strip(),
            "energy_mode": self.energy_mode.text().strip() or "signed",
            "output_time_step": float(self.output_time_step.value()),
            "output_units": self.output_units.text().strip(),
            "accel_in_g": self.accel_in_g.isChecked(),
            "overwrite_db": self.overwrite_db.isChecked(),
            "nlth_case": {
                "apply_parameters": self.nl_apply_parameters.isChecked(),
                "p_delta": self.nl_p_delta.isChecked(),
                "initial_case": self.nl_initial_case.text().strip(),
                "damping": {
                    "method": self.damping_method.text().strip(),
                    "args": self._parse_yaml_list(self.damping_args.text()),
                },
                "time_integration": {
                    "method": self.ti_method.text().strip(),
                    "alpha": float(self.ti_alpha.text().strip() or "0.0"),
                    "beta": float(self.ti_beta.text().strip() or "0.25"),
                    "gamma": float(self.ti_gamma.text().strip() or "0.5"),
                    "theta": float(self.ti_theta.text().strip() or "0.0"),
                },
                "nonlinear_parameters": {
                    "dt_max_factor": float(self.np_dt_max_factor.text().strip() or "1.0"),
                    "dt_min_factor": float(self.np_dt_min_factor.text().strip() or "0.2"),
                    "max_iter_cs": int(self.np_max_iter_cs.text().strip() or "6"),
                    "max_iter_nr": int(self.np_max_iter_nr.text().strip() or "20"),
                    "tol_conv_d": float(self.np_tol_conv_d.text().strip() or "0.001"),
                    "use_event_stepping": self.np_use_event_stepping.isChecked(),
                    "tol_event_d": float(self.np_tol_event_d.text().strip() or "0.005"),
                    "max_line_search_per_iter": int(self.np_max_line_search_per_iter.text().strip() or "3"),
                    "tol_line_search": float(self.np_tol_line_search.text().strip() or "0.8"),
                    "line_search_step_fact": float(self.np_line_search_step_fact.text().strip() or "2.0"),
                },
                "initial_conditions": {
                    "method": self.ic_method.text().strip(),
                    "args": self._parse_yaml_list(self.ic_args.text()),
                },
            },
            "nodes": self._collect_nodes(),
        }

    def save_settings(self):
        try:
            data = self._build_settings_dict()
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with self.settings_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)
            self._append_log(f"[gui] Settings guardado: {self.settings_path}")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Error guardando settings", str(exc))
            self._append_log(f"[gui] Error guardando settings: {exc}")
            return False

    def _python_executable(self):
        venv_py = self.base_dir / ".venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)
        if Path(sys.executable).exists():
            return sys.executable
        return "python"

    def _frozen_executable_for_script(self, script_path: str) -> str | None:
        script_name = Path(script_path).name.lower()
        mapping = {
            "run_nlth_batch.py": "etabslab_batch.exe",
        }
        exe_name = mapping.get(script_name)
        if not exe_name:
            return None
        exe_path = self.base_dir / exe_name
        if exe_path.exists():
            return str(exe_path)
        return None

    def _set_running_state(self, running: bool):
        for btn in [
            self.btn_save_settings_top,
            self.btn_load_settings,
            self.btn_settings_browse,
            self.btn_pre,
            self.btn_batch,
            self.btn_post,
        ]:
            btn.setEnabled(not running)
        self.btn_cancel.setEnabled(running)

    def _run_command(self, args: list[str]):
        if self.process is not None:
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso ejecutandose.")
            return
        if not self.save_settings():
            return
        self._reset_batch_progress()
        self._is_batch_run = any(str(a).endswith("run_nlth_batch.py") for a in args)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.base_dir))
        frozen_target = None
        if getattr(sys, "frozen", False) and args:
            frozen_target = self._frozen_executable_for_script(args[0])

        if frozen_target:
            self.process.setProgram(frozen_target)
            self.process.setArguments(args[1:])
        else:
            self.process.setProgram(self._python_executable())
            self.process.setArguments(args)
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)
        self._set_running_state(True)

        launch_args = self.process.arguments()
        self._append_log(f"[gui] Ejecutando: {self.process.program()} {' '.join(launch_args)}")
        self.process.start()

    def run_preprocess(self):
        self._run_command([str(self.runtime_dir / "scripts" / "preprocess_mat_catalog.py")])

    def run_batch(self):
        catalog = self.catalog_path.text().strip()
        if not catalog:
            QMessageBox.warning(self, "Catalogo", "Debes indicar un catalogo CSV.")
            return
        self._run_command(
            [
                str(self.runtime_dir / "scripts" / "run_nlth_batch.py"),
                "--catalog",
                str(Path(catalog).resolve()),
                "--settings",
                str(self.settings_path),
            ]
        )

    def run_postprocess(self):
        self._run_command([str(self.runtime_dir / "scripts" / "inspect_db.py")])

    def cancel_process(self):
        if self.process is not None:
            self._append_log("[gui] Cancelando proceso...")
            self.process.kill()

    def _on_stdout(self):
        if self.process is None:
            return
        out = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if out:
            self._append_log(out)
            self._stdout_buffer += out
            while "\n" in self._stdout_buffer:
                line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
                self._handle_output_line(line.rstrip("\r"))

    def _on_stderr(self):
        if self.process is None:
            return
        err = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if err:
            self._append_log(err)

    def _on_finished(self, code: int):
        self._append_log(f"[gui] Proceso finalizado con codigo: {code}")
        if self._is_batch_run and code == 0 and self._batch_total > 0:
            self.batch_progress.setMaximum(self._batch_total)
            self.batch_progress.setValue(self._batch_total)
            self.lbl_batch_counts.setText(f"Progreso: {self._batch_total}/{self._batch_total}")
        self.process = None
        self._is_batch_run = False
        self._set_running_state(False)


def main():
    app = QApplication(sys.argv)
    win = SettingsGui()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
