from experiments.accelerograms import read_ascii_accelerogram, BiComponentAccelerogram

ax = read_ascii_accelerogram("data/acc_x.txt")
ay = read_ascii_accelerogram("data/acc_y.txt")

acc = BiComponentAccelerogram(ax, ay)

print("dt:", acc.dt)
print("n_steps:", acc.n_steps)
print("duration:", acc.duration)
