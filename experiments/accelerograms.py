import os
import numpy as np
from pathlib import Path
import re

try:
    from scipy.io import loadmat
except Exception:  # pragma: no cover - optional dependency
    loadmat = None

class Accelerogram:
    def __init__(self, time, acc, units="m/s2", acc_id=None):
        self.time = time
        self.acc = acc
        self.units = units
        self.id = acc_id or "ACC"
        self.dt = time[1] - time[0]
        
    @property
    def n_steps(self):
        return len(self.acc)

    def write_normalized_file(
        self,
        output_dir,
        file_prefix="",
        header_lines=3,
        scale_to_g=True
    ):
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        fname = f"{file_prefix}{self.id}.txt"
        fpath = output_dir / fname

        if scale_to_g:
            units = self.units.lower()
            if units in ["gal", "cm/s2", "cm/s^2"]:
                data = self.acc / 981.0
            elif units in ["m/s2", "m/s^2"]:
                data = self.acc / 9.81
            else:
                raise ValueError(f"Unidades no soportadas: {self.units}")
        else:
            data = self.acc

        with open(fpath, "w") as f:
            f.write(f"# Accelerogram ID: {self.id}\n")
            f.write(f"# dt = {self.dt}\n")
            f.write("# Acceleration [g]\n")
            for v in data:
                f.write(f"{v:.6e}\n")

        return str(fpath)  # ← RUTA ABSOLUTA

    
class BiComponentAccelerogram:
    def __init__(self, ax: Accelerogram, ay: Accelerogram):
        if ax.dt != ay.dt:
            raise ValueError("Las componentes X e Y tienen dt distinto")

        self.ax = ax
        self.ay = ay
        self.dt = ax.dt
        self.n_steps = min(ax.n_steps, ay.n_steps)
        self.duration = self.dt * (self.n_steps - 1)



def read_ascii_accelerogram(
    filepath,
    units=None,
    acc_id=None,
    header_prefixes=("#", "%", "//")
):
    filepath = Path(filepath).resolve()
    if not filepath.exists():
        raise FileNotFoundError(filepath)

    header_lines = []
    data_lines = []

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if any(line.startswith(p) for p in header_prefixes):
                header_lines.append(line)
            else:
                data_lines.append(line)

    # Intentar inferir unidades y dt del header
    inferred_units = None
    inferred_dt = None

    for h in header_lines:
        h_low = h.lower()
        if "gal" in h_low or "cm/s2" in h_low or "cm/s^2" in h_low:
            inferred_units = "gal"
        elif "[g]" in h_low or " g" in h_low:
            inferred_units = "g"
        elif "m/s2" in h_low or "m/s^2" in h_low:
            inferred_units = "m/s2"

        if "dt" in h_low:
            try:
                inferred_dt = float(h_low.split("dt")[1].split("=")[1])
            except Exception:
                pass

    if units is None:
        if inferred_units is None:
            raise ValueError(
                f"{filepath.name}: no se pudo inferir unidades (gal o m/s2)"
            )
        units = inferred_units

    # Leer datos
    data = np.loadtxt(data_lines)

    if data.ndim == 1:
        if inferred_dt is None:
            raise ValueError(
                f"{filepath.name}: archivo sin columna de tiempo y sin dt en header"
            )
        acc = data
        t = np.arange(len(acc)) * inferred_dt
    elif data.ndim == 2 and data.shape[1] >= 2:
        t = data[:, 0]
        acc = data[:, 1]
    else:
        raise ValueError(f"{filepath.name}: formato no reconocido")

    return Accelerogram(
        time=t,
        acc=acc,
        units=units,
        acc_id=acc_id or filepath.stem
    )


def compute_response_spectrum(acc, dt, periods, damping=0.05):
    acc = np.asarray(acc, dtype=float)
    periods = np.asarray(periods, dtype=float)
    if np.any(periods <= 0):
        raise ValueError("Los periodos deben ser > 0")

    beta = 0.25
    gamma = 0.5

    sa = np.zeros_like(periods)

    for i, t in enumerate(periods):
        omega = 2.0 * np.pi / t
        k = omega * omega
        c = 2.0 * damping * omega

        u = 0.0
        v = 0.0
        a = -acc[0]

        a0 = 1.0 / (beta * dt * dt)
        a1 = gamma / (beta * dt)
        a2 = 1.0 / (beta * dt)
        a3 = (1.0 / (2.0 * beta)) - 1.0
        a4 = (gamma / beta) - 1.0
        a5 = dt * ((gamma / (2.0 * beta)) - 1.0)

        k_eff = k + a0 + a1 * c

        max_abs_acc = abs(a + acc[0])

        for j in range(1, len(acc)):
            p = -acc[j]
            p_eff = (
                p
                + a0 * u
                + a2 * v
                + a3 * a
                + c * (a1 * u + a4 * v + a5 * a)
            )

            u_new = p_eff / k_eff
            a_new = a0 * (u_new - u) - a2 * v - a3 * a
            v_new = v + dt * ((1.0 - gamma) * a + gamma * a_new)

            abs_acc = abs(a_new + acc[j])
            if abs_acc > max_abs_acc:
                max_abs_acc = abs_acc

            u, v, a = u_new, v_new, a_new

        sa[i] = max_abs_acc

    return periods, sa


def plot_bicomponent_and_spectrum(
    x_txt_path,
    y_txt_path,
    damping=0.05,
    periods=None,
    show=True,
    save_path=None
):
    import matplotlib.pyplot as plt

    ax = read_ascii_accelerogram(x_txt_path, units="g")
    ay = read_ascii_accelerogram(y_txt_path, units="g")

    if abs(ax.dt - ay.dt) > 1e-9:
        raise ValueError("dt distinto entre componentes")

    if periods is None:
        periods = np.linspace(0.02, 5.0, 100)

    tx, sa_x = compute_response_spectrum(
        ax.acc, ax.dt, periods, damping=damping
    )
    ty, sa_y = compute_response_spectrum(
        ay.acc, ay.dt, periods, damping=damping
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle("Acelerograma y espectro de respuesta (5% amort.)")

    ax1.plot(ax.time, ax.acc, label="EW")
    ax1.plot(ay.time, ay.acc, label="NS")
    ax1.set_xlabel("Tiempo [s]")
    ax1.set_ylabel("Aceleracion [g]")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(tx, sa_x, label="Sa EW")
    ax2.plot(ty, sa_y, label="Sa NS")
    ax2.set_xlabel("Periodo [s]")
    ax2.set_ylabel("Sa [g]")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(Path(save_path).resolve()), dpi=200)

    if show:
        plt.show()

    return fig


def _pick_mat_arrays(mat_data):
    arrays = {}
    for key, value in mat_data.items():
        if key.startswith("__"):
            continue
        if isinstance(value, np.ndarray):
            arrays[key] = np.squeeze(value)
    return arrays


def _infer_time_and_acc(arrays):
    if not arrays:
        raise ValueError("No se encontraron arrays en el archivo .mat")

    # Preferir una matriz Nx2 con tiempo y aceleracion.
    for name, arr in arrays.items():
        if arr.ndim == 2:
            if arr.shape[1] == 2:
                t = arr[:, 0]
                acc = arr[:, 1]
                return name, t, acc
            if arr.shape[0] == 2:
                t = arr[0, :]
                acc = arr[1, :]
                return name, t, acc

    # Buscar pares de vectores 1D con mismo largo.
    candidates = [(k, v) for k, v in arrays.items() if v.ndim == 1]
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            k1, v1 = candidates[i]
            k2, v2 = candidates[j]
            if v1.shape[0] != v2.shape[0]:
                continue
            # Detectar tiempo como vector monotono con paso casi constante.
            dt = np.diff(v1)
            if np.all(dt > 0) and np.isfinite(dt).all():
                return f"{k1},{k2}", v1, v2
            dt = np.diff(v2)
            if np.all(dt > 0) and np.isfinite(dt).all():
                return f"{k1},{k2}", v2, v1

    # Si solo hay un vector 1D, asumir que es aceleracion.
    if len(candidates) == 1:
        k, v = candidates[0]
        return k, None, v

    raise ValueError("No se pudo inferir tiempo y aceleracion desde el .mat")


def read_mat_accelerogram(
    filepath,
    units="m/s2",
    acc_id=None,
    time_key=None,
    acc_key=None,
    dt_key="dt",
    mat_data=None
):
    filepath = Path(filepath).resolve()
    if mat_data is None:
        if not filepath.exists():
            raise FileNotFoundError(filepath)
        if loadmat is None:
            raise ImportError(
                "Falta scipy. Instala con: pip install scipy"
            )
        mat = loadmat(filepath)
    else:
        mat = mat_data
    arrays = _pick_mat_arrays(mat)

    t = None
    acc = None

    if acc_key:
        if acc_key not in arrays:
            raise KeyError(f"Key no encontrado: acc={acc_key}")
        acc = arrays[acc_key]
    if time_key:
        if time_key not in arrays:
            raise KeyError(f"Key no encontrado: time={time_key}")
        t = arrays[time_key]

    if acc is None and t is None:
        _, t, acc = _infer_time_and_acc(arrays)

    if t is None:
        if dt_key and dt_key in arrays:
            dt_val = arrays[dt_key]
            dt = float(np.asarray(dt_val).squeeze().item())
            t = np.arange(len(acc)) * dt
        else:
            raise ValueError(
                "No se encontro vector de tiempo. Indica time_key o dt_key."
            )

    return Accelerogram(
        time=t,
        acc=acc,
        units=units,
        acc_id=acc_id or filepath.stem
    )


def mat_to_normalized(
    mat_path,
    output_dir,
    units="m/s2",
    acc_id=None,
    time_key=None,
    acc_key=None,
    dt_key="dt",
    file_prefix="",
    mat_data=None
):
    acc = read_mat_accelerogram(
        mat_path,
        units=units,
        acc_id=acc_id,
        time_key=time_key,
        acc_key=acc_key,
        dt_key=dt_key,
        mat_data=mat_data
    )
    return acc.write_normalized_file(
        output_dir=output_dir,
        file_prefix=file_prefix
    )
