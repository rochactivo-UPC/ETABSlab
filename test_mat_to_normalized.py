from experiments.accelerograms import mat_to_normalized

mat_to_normalized(
    r"C:\Users\rocha\Documents\ETABSlab\data\201209051442GNYA (1).mat",
    r"C:\Users\rocha\Documents\ETABSlab\data\normalized",
    units="m/s2",
    acc_key="acc_f_e",
    acc_id="GNYA_acc_f_e"
)
