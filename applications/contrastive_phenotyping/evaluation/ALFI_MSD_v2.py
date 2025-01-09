# %%
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from viscy.representation.embedding_writer import read_embedding_dataset
from viscy.representation.evaluation.distance import (
    compute_displacement,
    compute_displacement_statistics,
)

# Paths to datasets
feature_paths = {
    "7 min interval": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_7mins.zarr",
    "14 min interval": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_14mins.zarr",
    "28 min interval": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_28mins.zarr",
    "56 min interval": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_56mins.zarr",
    "91 min interval": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_91mins.zarr",
    "Classical": "/hpc/projects/organelle_phenotyping/ALFI_ntxent_loss/logs_alfi_ntxent_time_intervals/predictions/ALFI_classical.zarr",
}

# Colors for different time intervals
interval_colors = {
    "7 min interval": "blue",
    "14 min interval": "red",
    "28 min interval": "green",
    "56 min interval": "purple",
    "91 min interval": "orange",
    "Classical": "gray",
}

# %% Compute MSD for each dataset
results = {}
raw_displacements = {}

for label, path in feature_paths.items():
    print(f"\nProcessing {label}...")
    embedding_dataset = read_embedding_dataset(Path(path))

    # Compute displacements
    displacements = compute_displacement(
        embedding_dataset=embedding_dataset,
        distance_metric="euclidean_squared",
    )
    means, stds = compute_displacement_statistics(displacements)
    results[label] = (means, stds)
    raw_displacements[label] = displacements

    # Print some statistics
    taus = sorted(means.keys())
    print(f"  Number of different τ values: {len(taus)}")
    print(f"  τ range: {min(taus)} to {max(taus)}")
    print(f"  MSD at τ=1: {means[1]:.4f} ± {stds[1]:.4f}")

# %% Plot MSD vs time (linear scale)
plt.figure(figsize=(10, 6))

# Plot each time interval
for interval_label, path in feature_paths.items():
    means, stds = results[interval_label]

    # Sort by tau for plotting
    taus = sorted(means.keys())
    mean_values = [means[tau] for tau in taus]
    std_values = [stds[tau] for tau in taus]

    plt.plot(
        taus,
        mean_values,
        "-",
        color=interval_colors[interval_label],
        alpha=0.5,
        zorder=1,
    )
    plt.scatter(
        taus,
        mean_values,
        color=interval_colors[interval_label],
        s=20,
        label=interval_label,
        zorder=2,
    )

plt.xlabel("Time Shift (τ)")
plt.ylabel("Mean Square Displacement")
plt.title("MSD vs Time Shift")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()

# %% Plot MSD vs time (log-log scale with slopes)
n_dimensions = 768
plt.figure(figsize=(10, 6))

# Plot each time interval
for interval_label, path in feature_paths.items():
    means, stds = results[interval_label]

    # Sort by tau for plotting
    taus = sorted(means.keys())
    mean_values = [means[tau] for tau in taus]
    std_values = [stds[tau] for tau in taus]

    # Filter out non-positive values for log scale
    valid_mask = np.array(mean_values) > 0
    valid_taus = np.array(taus)[valid_mask]
    valid_means = np.array(mean_values)[valid_mask]

    # Calculate slopes for different regions
    log_taus = np.log(valid_taus)
    log_means = np.log(valid_means)

    # Early slope (first third of points)
    n_points = len(log_taus)
    early_end = n_points // 3
    early_slope, early_intercept = np.polyfit(
        log_taus[:early_end], log_means[:early_end], 1
    )
    early_slope /= 2 * n_dimensions

    # middle slope (mid portions of points)
    late_start = 2 * (n_points // 3)
    mid_slope, mid_intercept = np.polyfit(
        log_taus[early_end:late_start], log_means[early_end:late_start], 1
    )
    mid_slope /= 2 * n_dimensions

    plt.plot(
        log_taus,
        log_means,
        "-",
        color=interval_colors[interval_label],
        alpha=0.5,
        zorder=1,
    )
    plt.scatter(
        log_taus,
        log_means,
        color=interval_colors[interval_label],
        s=20,
        label=f"{interval_label} (α_early={early_slope:.2f}, α_mid={mid_slope:.2f})",
        zorder=2,
    )

    # # Plot fitted lines for early and late regions
    # early_fit = np.exp(early_intercept + early_slope * log_taus[:early_end])
    # mid_fit = np.exp(mid_intercept + mid_slope * log_taus[early_end:late_start])

    # plt.plot(
    #     early_fit,
    #     log_taus[:early_end],
    #     "--",
    #     color=interval_colors[interval_label],
    #     alpha=0.3,
    #     zorder=1,
    # )
    # plt.plot(
    #     mid_fit,
    #     log_taus[early_end:late_start],
    #     "--",
    #     color=interval_colors[interval_label],
    #     alpha=0.3,
    #     zorder=1,
    # )

plt.xscale("log")
plt.yscale("log")
plt.xlabel("Time Shift (τ)")
plt.ylabel("Mean Square Displacement")
plt.title("MSD vs Time Shift (log-log)")
plt.grid(True, alpha=0.3, which="both")
plt.legend(
    title="α = slope in log-log space", bbox_to_anchor=(1.05, 1), loc="upper left"
)
plt.tight_layout()
plt.show()

# %% Plot slopes analysis
early_slopes = []
mid_slopes = []
intervals = []

for interval_label in feature_paths.keys():
    means, _ = results[interval_label]

    # Calculate slopes
    taus = np.array(sorted(means.keys()))
    mean_values = np.array([means[tau] for tau in taus])
    valid_mask = mean_values > 0

    if np.sum(valid_mask) > 3:  # Need at least 4 points to calculate both slopes
        log_taus = np.log(taus[valid_mask])
        log_means = np.log(mean_values[valid_mask])

        # Calculate early and mid slopes
        n_points = len(log_taus)
        early_end = n_points // 3
        late_start = 2 * (n_points // 3)

        early_slope, _ = np.polyfit(log_taus[:early_end], log_means[:early_end], 1)
        mid_slope, _ = np.polyfit(log_taus[early_end:late_start], log_means[early_end:late_start], 1)

        early_slopes.append(early_slope/(2*n_dimensions))
        mid_slopes.append(mid_slope/(2*n_dimensions))
        intervals.append(interval_label)

# Create bar plot
plt.figure(figsize=(12, 6))

x = np.arange(len(intervals))
width = 0.35

plt.bar(x - width / 2, early_slopes, width, label="Early slope", alpha=0.7)
plt.bar(x + width / 2, mid_slopes, width, label="Mid slope", alpha=0.7)

# # Add reference lines
# plt.axhline(y=0.001, color="k", linestyle="--", alpha=0.3, label="Normal diffusion (α=1)")
# plt.axhline(y=0, color="k", linestyle="-", alpha=0.2)

plt.xlabel("Time Interval")
plt.ylabel("Slope (α)")
plt.title("MSD Slopes by Time Interval")
plt.xticks(x, intervals, rotation=45)
plt.legend()
plt.show()

# %%