# Deterministic examples

The `configs/` files are readable copies of the examples embedded in the wheel. All commands run without network access.

## Logistic map

```text
x[n+1] = r x[n] (1 - x[n])
```

`phaseprobe scan --example logistic` searches a narrow declared `r` range and classifies retained tail recurrence. Its positive case brackets a finite-time period-2/period-4 classification change; its negative control stays period-2. The long burn-in reduces, but cannot eliminate, critical-slowing bias. Source: [May (1976)](https://www.nature.com/articles/261459a0).

## Lorenz system

```text
dx/dt = sigma (y - x)
dy/dt = x (rho - z) - y
dz/dt = x y - beta z
```

`phaseprobe perturb --example lorenz` compares twin fixed-step RK4 trajectories separated only in initial `x`. The finding is a finite-time Euclidean-separation threshold and rate, not a Lyapunov exponent. The negative control shortens the window and declares an unreachable threshold. Source: [Lorenz (1963)](https://journals.ametsoc.org/view/journals/atsc/20/2/1520-0469_1963_020_0130_dnf_2_0_co_2.xml).

## Predator–prey

```text
dx/dt = alpha x - beta x y
dy/dt = delta x y - gamma y
H = delta x - gamma log(x) + beta y - alpha log(y)
```

`phaseprobe check --example predator-prey` checks positive populations and retained drift in the analytic first integral. Its positive case uses `dt=0.005`; the deliberate coarse-step negative control uses `dt=0.25` and fails policy. This tests numerical integration quality, not ecological validity. Source: [Lotka (1920)](https://doi.org/10.1073/pnas.6.7.410).

## Genetic toggle

```text
du/dt = alpha_u / (1 + v^hill_v) - u
dv/dt = alpha_v / (1 + u^hill_u) - v
```

`phaseprobe perturb --example toggle` increases initial `v` from a `u`-dominant baseline, then refines the first perturbation that ends `v`-dominant. The negative control remains in the original basin. This is a dimensionless illustrative mutual-repression model, not a calibrated biological prediction. Source: [Gardner, Cantor & Collins (2000)](https://www.nature.com/articles/35002131).
