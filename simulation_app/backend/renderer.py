"""
PNG Frame Renderer for ABS-DES Pandemic Simulation.

Generates two views per simulation day:
  - ACTUAL: True epidemic state (ground truth from simulation)
  - OBSERVED: Provider-inferred state (what healthcare providers detect)

Each frame is a composite image: geographic map (top 60%) + SEIR curve (bottom 40%).
Output: actual_dayNNN.png and observed_dayNNN.png in the specified output directory.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.gridspec import GridSpec
import numpy as np
from pathlib import Path
import json
import geopandas as gpd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # pandemic_modeling/


def load_africa_boundaries():
    """Load Africa country boundaries from cached GeoJSON."""
    path = _PROJECT_ROOT / "006_continental_africa" / "africa_boundaries.geojson"
    return gpd.read_file(str(path))


def _get_country_bounds(africa_gdf, country: str):
    """Return (minx, miny, maxx, maxy) for a specific country, or None for ALL."""
    if country == "ALL":
        return None
    # Try matching on NAME, ADMIN, or NAME_LONG columns
    for col in ("NAME", "ADMIN", "NAME_LONG", "name", "admin"):
        if col in africa_gdf.columns:
            match = africa_gdf[africa_gdf[col].str.upper() == country.upper()]
            if len(match) > 0:
                return match.total_bounds
    return None


def _render_map_panel(ax, africa_gdf, lons, lats, pops, size_scale, infection_pcts,
                      norm, cmap, seed_indices, city_names, country_bounds, title):
    """Render the geographic map panel onto the given axes."""
    ax.set_title(title, fontsize=9, fontweight="bold", pad=6)

    # Plot Africa boundaries
    africa_gdf.plot(ax=ax, color="#f0ede4", edgecolor="#333333",
                    linewidth=0.6, zorder=0)

    # City scatter colored by infection percentage
    sc = ax.scatter(
        lons, lats, s=size_scale, c=infection_pcts, cmap=cmap,
        norm=norm, edgecolors="black", linewidths=0.3, zorder=2,
    )

    # Highlight seed cities with blue rings
    for si in seed_indices:
        ax.scatter(
            [lons[si]], [lats[si]],
            s=size_scale[si] * 1.8,
            facecolors="none", edgecolors="blue", linewidths=1.5, zorder=3,
        )

    # Label top 10 cities by population
    pop_order = np.argsort(-pops)
    for rank, i in enumerate(pop_order[:10]):
        ax.annotate(
            city_names[i], (lons[i], lats[i]),
            textcoords="offset points", xytext=(5, 5),
            fontsize=5, fontweight="bold", zorder=3,
            bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                      alpha=0.6, edgecolor="none"),
        )

    # Set map extent
    if country_bounds is not None:
        pad = 2.0
        ax.set_xlim(country_bounds[0] - pad, country_bounds[2] + pad)
        ax.set_ylim(country_bounds[1] - pad, country_bounds[3] + pad)
    else:
        bounds = africa_gdf.total_bounds
        pad = 2.0
        ax.set_xlim(bounds[0] - pad, bounds[2] + pad)
        ax.set_ylim(bounds[1] - pad, bounds[3] + pad)

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")

    return sc


def _render_seir_panel(ax, result, seed_idx, day, n_people, view_label):
    """Render the SEIR-D time-series curve panel onto the given axes.

    ACTUAL view shows 7 compartments (S, E, I_minor, I_needs, I_care, R, D).
    OBSERVED view shows 5 compartments (S, E, I, R, D).
    """
    seed_name = result.city_names[seed_idx]
    total_days = result.actual_S.shape[1]
    t = np.arange(total_days)

    if view_label == "ACTUAL":
        # Full severity breakdown for ACTUAL view
        s_vals = result.actual_S[seed_idx, :] / n_people
        e_vals = result.actual_E[seed_idx, :] / n_people
        i_minor_vals = result.actual_I_minor[seed_idx, :] / n_people
        i_needs_vals = result.actual_I_needs[seed_idx, :] / n_people
        i_care_vals = result.actual_I_care[seed_idx, :] / n_people
        r_vals = result.actual_R[seed_idx, :] / n_people
        d_vals = result.actual_D[seed_idx, :] / n_people

        ax.plot(t, s_vals, color="#3498db", linewidth=1.2, label="S")
        ax.plot(t, e_vals, color="#f39c12", linewidth=1.2, label="E")
        ax.plot(t, i_minor_vals, color="#e67e22", linewidth=1.2, label="I (minor)")
        ax.plot(t, i_needs_vals, color="#e74c3c", linewidth=1.2, label="I (needs care)")
        ax.plot(t, i_care_vals, color="#9b59b6", linewidth=1.2, label="I (receiving)")
        ax.plot(t, r_vals, color="#2ecc71", linewidth=1.2, label="R")
        ax.plot(t, d_vals, color="#2c3e50", linewidth=1.2, linestyle="--", label="D")
    else:
        # Aggregated view for OBSERVED
        s_vals = result.observed_S[seed_idx, :] / n_people
        e_vals = result.observed_E[seed_idx, :] / n_people
        i_vals = result.observed_I[seed_idx, :] / n_people
        r_vals = result.observed_R[seed_idx, :] / n_people
        d_vals = result.observed_D[seed_idx, :] / n_people

        ax.plot(t, s_vals, color="#3498db", linewidth=1.2, label="S")
        ax.plot(t, e_vals, color="#f39c12", linewidth=1.2, label="E")
        ax.plot(t, i_vals, color="#e74c3c", linewidth=1.2, label="I")
        ax.plot(t, r_vals, color="#2ecc71", linewidth=1.2, label="R")
        ax.plot(t, d_vals, color="#2c3e50", linewidth=1.2, linestyle="--", label="D")

    # Vertical dotted line at the current day
    ax.axvline(x=day, color="#555555", linestyle=":", linewidth=1.0, alpha=0.8)

    ax.set_xlim(0, total_days - 1)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Day", fontsize=7)
    ax.set_ylabel("Fraction of N", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.legend(loc="upper right", fontsize=5, framealpha=0.8, ncol=2)
    ax.set_title(f"Seed City: {seed_name} -- SEIR-D Dynamics ({view_label})",
                 fontsize=8, fontweight="bold", pad=4)
    ax.grid(True, alpha=0.3, linewidth=0.5)


def render_all_frames(result, africa_gdf, output_dir: Path, progress_callback,
                      country: str = "ALL"):
    """
    Generate actual_dayNNN.png and observed_dayNNN.png for each simulation day.

    Each PNG is a composite: map on top (60%), SEIR curve on bottom (40%).
    Figure size: 8x10 inches at 100 DPI = 800x1000 pixels.

    Parameters
    ----------
    result : object
        Simulation result with attributes:
            - actual_I: np.ndarray, shape (n_cities, total_days) -- true infectious counts
            - observed_I: np.ndarray, shape (n_cities, total_days) -- provider-observed counts
            - S, E, I, R: np.ndarray, shape (n_cities, total_days) -- SEIR compartments (actual)
            - city_names: list[str]
            - city_populations: list[int]
            - city_coords: list[tuple[float, float]] -- (lat, lon) pairs
            - n_people_per_city: int -- DES population per city
            - seed_city_indices: list[int]
            - scenario_name: str
    africa_gdf : GeoDataFrame
        Africa country boundary polygons.
    output_dir : Path
        Directory to write PNG frames and metadata.json.
    progress_callback : callable
        Called as progress_callback("rendering", current_frame, total_frames).
    country : str
        Country name to zoom into, or "ALL" for full continent view.
    """
    n_cities = len(result.city_names)
    total_days = result.actual_I.shape[1]
    n_people = result.n_people_per_city

    # -- Pre-compute static data -----------------------------------------------

    # City coordinates: result.city_coords is list of (lat, lon) tuples
    lats = np.array([c[0] for c in result.city_coords])
    lons = np.array([c[1] for c in result.city_coords])
    pops = np.array(result.city_populations, dtype=float)

    # Size scale based on population
    size_scale = np.sqrt(pops / pops.min()) * 15
    size_scale = np.clip(size_scale, 8, 200)

    # Shared color normalization across both views for fair comparison
    vmax_actual = result.actual_I.max() / n_people * 100
    vmax_observed = result.observed_I.max() / n_people * 100
    vmax = max(vmax_actual, vmax_observed, 0.1)
    norm = mcolors.Normalize(vmin=0, vmax=vmax)
    cmap = plt.cm.YlOrRd

    # Pick the seed city with the largest population for SEIR curves
    seed_idx = max(result.seed_city_indices,
                   key=lambda i: result.city_populations[i])

    # Country zoom bounds
    country_bounds = _get_country_bounds(africa_gdf, country)

    # Total frames to render (2 per day: actual + observed)
    total_frames = total_days * 2
    frame_count = 0

    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Render loop -----------------------------------------------------------

    for day in range(total_days):
        for view, data_array, label_prefix, label_title in [
            ("actual", result.actual_I, "actual", "ACTUAL -- True Epidemic State"),
            ("observed", result.observed_I, "observed", "OBSERVED -- Provider-Inferred State"),
        ]:
            # Compute per-city infection percentages for this day
            infection_pcts = data_array[:, day] / n_people * 100

            # Create composite figure: map (top 60%) + SEIR curve (bottom 40%)
            fig = plt.figure(figsize=(8, 10), dpi=100)
            gs = GridSpec(2, 1, figure=fig, height_ratios=[3, 2], hspace=0.28)
            ax_map = fig.add_subplot(gs[0])
            ax_seir = fig.add_subplot(gs[1])

            # Map panel
            title = f"{label_title} -- Day {day}"
            _render_map_panel(
                ax_map, africa_gdf, lons, lats, pops, size_scale,
                infection_pcts, norm, cmap, result.seed_city_indices,
                result.city_names, country_bounds, title,
            )

            # Colorbar for map
            sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax_map, orientation="horizontal",
                                fraction=0.04, pad=0.08, aspect=40)
            cbar.set_label("Infection (% of city population)", fontsize=7)
            cbar.ax.tick_params(labelsize=6)

            # SEIR curve panel
            _render_seir_panel(ax_seir, result, seed_idx, day, n_people,
                               label_prefix.upper())

            # Add infection stats text on map
            mean_inf = infection_pcts.mean()
            max_inf = infection_pcts.max()
            max_city = result.city_names[np.argmax(infection_pcts)]
            ax_map.text(
                0.02, 0.02,
                f"Mean infection: {mean_inf:.2f}%\n"
                f"Max: {max_inf:.2f}% ({max_city})",
                transform=ax_map.transAxes, fontsize=7, verticalalignment="bottom",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
            )

            # Save frame
            fname = output_dir / f"{label_prefix}_day{day:03d}.png"
            fig.savefig(str(fname), dpi=100, bbox_inches="tight",
                        facecolor="white", edgecolor="none")
            plt.close(fig)

            frame_count += 1
            if progress_callback is not None:
                progress_callback("rendering", frame_count, total_frames)

    # -- Save metadata ---------------------------------------------------------

    metadata = {
        "total_days": total_days,
        "seed_city": result.city_names[seed_idx],
        "seed_city_indices": result.seed_city_indices,
        "scenario_name": result.scenario_name,
        "city_count": n_cities,
        "n_people_per_city": n_people,
        "vmax_shared": float(vmax),
        "country_filter": country,
    }
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
