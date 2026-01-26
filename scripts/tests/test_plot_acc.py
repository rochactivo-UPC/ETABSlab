from experiments.accelerograms import plot_bicomponent_and_spectrum

plot_bicomponent_and_spectrum(
    r"data/normalized/201209051442GLIB_E.txt",
    r"data/normalized/201209051442GLIB_N.txt",
    damping=0.05
)