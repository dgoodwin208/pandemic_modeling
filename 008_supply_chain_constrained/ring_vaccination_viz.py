#!/usr/bin/env python3
"""
Ring Vaccination Network Visualization.

Inspired by Bill Foege's surveillance-containment strategy in Nigeria (1966):
instead of mass vaccination, use ground-level information to find and ring-fence
outbreaks by vaccinating the contacts of detected cases first.

This script:
1. Runs a single-city CityDES simulation with AI providers
2. Snapshots the state when ~1/3 of agents are infected/recovered
3. Extracts a local subgraph around a detected case
4. Renders the contact network with SEIR colors and purple vaccine priority rings

Usage:
    cd 008_supply_chain_constrained && python ring_vaccination_viz.py
"""

import sys
from pathlib import Path
from collections import deque

import numpy as np
import networkx as nx

# Path setup
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _PROJECT_ROOT / "simulation_app" / "backend"
sys.path.insert(0, str(_BACKEND))

from sim_config import DiseaseParams
from city_des_extended import CityDES

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Configuration ────────────────────────────────────────────────────────────

N_PEOPLE = 500       # Small enough to visualize, large enough for structure
SEED_INFECTED = 3
RANDOM_SEED = 42

# COVID-like disease params (used as the 'scenario' object)
SCENARIO = DiseaseParams(
    scenario="covid_bioattack",
    R0=3.5,
    incubation_days=4.0,
    infectious_days=9.0,
    severe_fraction=0.020,
    care_survival_prob=0.88,
    ifr=0.005,
    gamma_shape=6.25,
    base_daily_death_prob=0.006,
    death_prob_increase_per_day=0.004,
)

# AI provider settings
AI_PROVIDERS = int(50 * N_PEOPLE / 1000)  # 50 per 1000
SCREENING_CAPACITY = 200
DISCLOSURE_PROB = 0.80
RECEPTIVITY = 0.85
ADVISED_ISOLATION_PROB = 0.55

# Visualization
SUBGRAPH_HOPS = 2          # BFS depth from focal node
MAX_DISPLAY_NODES = 120    # Cap to keep figure readable
TARGET_INFECTED_FRAC = 0.33  # Snapshot when ~1/3 are no longer susceptible


# ── SEIR color scheme (matches other project plots) ──────────────────────────

STATE_COLORS = {
    0: "#3498db",   # S = blue
    1: "#f1c40f",   # E = yellow
    2: "#e67e22",   # I_minor = orange
    3: "#e74c3c",   # I_needs_care = red
    4: "#c0392b",   # I_receiving_care = dark red
    5: "#27ae60",   # R = green
    6: "#2c3e50",   # D = dark gray
}

STATE_LABELS = {
    0: "Susceptible",
    1: "Exposed",
    2: "Infectious (mild)",
    3: "Infectious (severe)",
    4: "Hospitalized",
    5: "Recovered",
    6: "Dead",
}


# ── Simulation ───────────────────────────────────────────────────────────────

def run_to_target():
    """Run a single-city DES until ~1/3 of population is no longer susceptible."""
    city = CityDES(
        n_people=N_PEOPLE,
        scenario=SCENARIO,
        seed_infected=SEED_INFECTED,
        random_seed=RANDOM_SEED,
        avg_contacts=10,
        rewire_prob=0.4,
        daily_contact_rate=3.0,
        n_providers=AI_PROVIDERS,
        screening_capacity=SCREENING_CAPACITY,
        disclosure_prob=DISCLOSURE_PROB,
        receptivity=RECEPTIVITY,
        base_isolation_prob=0.0,
        advised_isolation_prob=ADVISED_ISOLATION_PROB,
        advice_decay_prob=0.05,
        detection_memory_days=7,
    )

    target_non_S = int(N_PEOPLE * TARGET_INFECTED_FRAC)
    snapshot_day = None

    for day in range(1, 301):
        city.step(until=day)
        city.run_provider_screening()

        non_susceptible = N_PEOPLE - city.S
        if non_susceptible >= target_non_S and snapshot_day is None:
            snapshot_day = day
            print(f"  Target reached on day {day}: "
                  f"S={city.S}, E={city.E}, I={city.I}, R={city.R}, D={city.D}")
            break

    if snapshot_day is None:
        # Just use last state
        snapshot_day = 300
        print(f"  Target not reached by day 300, using final state")

    return city, snapshot_day


def extract_subgraph(city: CityDES, hops: int, max_nodes: int):
    """Extract a BFS subgraph around a detected infectious case.

    Strategy: find a detected agent who is currently infectious and has
    contact candidates in their neighborhood. This gives us the most
    informative view of the ring vaccination logic.
    """
    # Find focal node: a detected infectious agent with neighbors in contact_candidates
    detected_infectious = [
        pid for pid in city._detected_day
        if city._states[pid] in (2, 3, 4)
    ]

    if not detected_infectious:
        # Fallback: any detected agent
        detected_infectious = list(city._detected_day.keys())

    if not detected_infectious:
        # Fallback: any infectious agent
        detected_infectious = [
            i for i in range(city.n_people)
            if city._states[i] in (2, 3, 4)
        ]

    if not detected_infectious:
        raise RuntimeError("No infectious agents found for visualization")

    # Score each candidate by how many contact_candidates are in their neighborhood
    best_focal = None
    best_score = -1
    for pid in detected_infectious:
        neighbors = set(city._neighbors[pid])
        contact_neighbors = neighbors & city._contact_candidates
        score = len(contact_neighbors)
        if score > best_score:
            best_score = score
            best_focal = pid

    focal = best_focal
    print(f"  Focal node: agent {focal} (state={city._states[focal]}, "
          f"contact_candidate_neighbors={best_score})")

    # BFS to get k-hop neighborhood
    visited = {focal}
    queue = deque([(focal, 0)])
    while queue and len(visited) < max_nodes:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for nb in city._neighbors[node]:
            if nb not in visited and len(visited) < max_nodes:
                visited.add(nb)
                queue.append((nb, depth + 1))

    # Build networkx subgraph
    G = nx.Graph()
    for node in visited:
        G.add_node(node)
    for node in visited:
        for nb in city._neighbors[node]:
            if nb in visited:
                G.add_edge(node, nb)

    return G, focal


def render_network(city: CityDES, G: nx.Graph, focal: int, snapshot_day: int):
    """Render the contact network with SEIR colors and vaccine priority rings."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    nodes = list(G.nodes())
    states = [int(city._states[n]) for n in nodes]

    # Classify each node
    is_vax_priority = set(city.vaccine_priority_targets)

    # Node sizes: focal is bigger, detected slightly bigger, rest uniform
    node_sizes = []
    for n in nodes:
        if n == focal:
            node_sizes.append(400)
        elif n in city._detected_day:
            node_sizes.append(260)
        elif n in is_vax_priority:
            node_sizes.append(200)
        else:
            node_sizes.append(130)

    # Layout: Kamada-Kawai gives cleaner separation than spring for small graphs
    pos = nx.kamada_kawai_layout(G)

    # --- Figure ---
    fig, ax = plt.subplots(1, 1, figsize=(16, 13))
    ax.set_facecolor("#fafbfc")
    fig.set_facecolor("white")

    # Classify edges into layers for drawing order
    tracing_edges = []      # detected ↔ contact_candidate (purple)
    network_edges = []       # all other edges (light structural)

    for u, v in G.edges():
        is_tracing = (
            (u in city._detected_day and v in city._contact_candidates) or
            (v in city._detected_day and u in city._contact_candidates)
        )
        if is_tracing:
            tracing_edges.append((u, v))
        else:
            network_edges.append((u, v))

    # Layer 1: Structural edges (faint)
    nx.draw_networkx_edges(G, pos, ax=ax, edgelist=network_edges,
                           edge_color="#d5d8dc", width=0.5, alpha=0.5)

    # Layer 2: Contact tracing edges (purple, prominent)
    if tracing_edges:
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=tracing_edges,
                               edge_color="#9b59b6", width=1.8, alpha=0.7,
                               style="solid")

    # Layer 3: Draw all nodes (base layer)
    node_colors = [STATE_COLORS[s] for s in states]
    nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=nodes,
                           node_color=node_colors, node_size=node_sizes,
                           edgecolors="white", linewidths=0.8)

    # Layer 4: Purple rings on vaccine priority targets
    vax_priority_nodes = [n for n in nodes if n in is_vax_priority]
    if vax_priority_nodes:
        vax_sizes = [node_sizes[nodes.index(n)] * 2.5 for n in vax_priority_nodes]
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=vax_priority_nodes,
                               node_color="none",
                               edgecolors="#8e44ad",
                               linewidths=3.0,
                               node_size=vax_sizes)

    # Layer 5: Bold outline on detected nodes (provider-identified)
    detected_nodes = [n for n in nodes if n in city._detected_day]
    if detected_nodes:
        det_sizes = [node_sizes[nodes.index(n)] for n in detected_nodes]
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=detected_nodes,
                               node_color=[STATE_COLORS[int(city._states[n])] for n in detected_nodes],
                               edgecolors="#2c3e50",
                               linewidths=2.5,
                               node_size=det_sizes)

    # Layer 6: Focal node star
    ax.scatter([pos[focal][0]], [pos[focal][1]],
               s=600, marker="*", c="#2c3e50", zorder=10,
               edgecolors="white", linewidths=1.5)

    # --- Legend (right side) ---
    legend_elements = []

    # State colors
    for state_id in [0, 1, 2, 3, 5, 6]:
        if any(s == state_id for s in states):
            legend_elements.append(
                Line2D([0], [0], marker='o', color='w',
                       markerfacecolor=STATE_COLORS[state_id],
                       markersize=11, label=STATE_LABELS[state_id])
            )

    legend_elements.append(Line2D([0], [0], color='w', label=''))  # spacer

    # Special markers
    legend_elements.append(
        Line2D([0], [0], marker='o', color='w',
               markerfacecolor='#3498db', markeredgecolor='#8e44ad',
               markeredgewidth=3, markersize=15,
               label=f'Vaccine priority target ({len(vax_priority_nodes)})')
    )
    legend_elements.append(
        Line2D([0], [0], marker='o', color='w',
               markerfacecolor='#e67e22', markeredgecolor='#2c3e50',
               markeredgewidth=2.5, markersize=11,
               label=f'Detected by AI provider ({len(detected_nodes)})')
    )
    legend_elements.append(
        Line2D([0], [0], marker='*', color='w',
               markerfacecolor='#2c3e50', markersize=15,
               label='Index patient (focal case)')
    )

    legend_elements.append(Line2D([0], [0], color='w', label=''))  # spacer

    legend_elements.append(
        Line2D([0], [0], color='#9b59b6', linewidth=2.5,
               label='Contact tracing link')
    )
    legend_elements.append(
        Line2D([0], [0], color='#d5d8dc', linewidth=1,
               label='Social network edge')
    )

    leg = ax.legend(handles=legend_elements, loc='upper left', fontsize=10.5,
                    framealpha=0.95, edgecolor='#bdc3c7', fancybox=True,
                    borderpad=1.0, labelspacing=0.8)
    leg.get_frame().set_linewidth(1.5)

    # --- Stats annotation ---
    total_in_view = len(nodes)
    s_count = sum(1 for s in states if s == 0)
    e_count = sum(1 for s in states if s == 1)
    i_count = sum(1 for s in states if s in (2, 3, 4))
    r_count = sum(1 for s in states if s == 5)
    d_count = sum(1 for s in states if s == 6)
    cc_in_view = sum(1 for n in nodes if n in city._contact_candidates)

    stats_text = (
        f"Day {snapshot_day}  |  {total_in_view} agents shown "
        f"({SUBGRAPH_HOPS}-hop neighborhood of index patient)\n"
        f"City status: {city.S}S  {city.E}E  {city.I}I  {city.R}R  {city.D}D  "
        f"({N_PEOPLE} total)    |    "
        f"In view: {s_count}S  {e_count}E  {i_count}I  {r_count}R  {d_count}D\n"
        f"Contact candidates: {cc_in_view}    |    "
        f"Vaccine priority queue: {len(vax_priority_nodes)} susceptible contacts identified"
    )
    ax.text(0.5, -0.01, stats_text,
            transform=ax.transAxes, ha='center', va='top',
            fontsize=9.5, color='#555', family='monospace',
            linespacing=1.6)

    # Title
    ax.set_title(
        "Surveillance-Containment: AI Providers Identify Who Gets the Vaccine Next\n"
        "Purple rings mark susceptible contacts of detected cases — the priority vaccination queue",
        fontsize=14, fontweight='bold', pad=20, color='#2c3e50'
    )

    ax.set_axis_off()
    fig.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = RESULTS_DIR / "fig_04_ring_vaccination.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  Saved {out_path.name}")
    return out_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  RING VACCINATION NETWORK VISUALIZATION")
    print("=" * 60)
    print(f"  N={N_PEOPLE}, target={TARGET_INFECTED_FRAC:.0%} non-susceptible")
    print(f"  AI providers: {AI_PROVIDERS} ({50}/1000)")
    print()

    print("Running simulation...")
    city, snapshot_day = run_to_target()

    print(f"\nExtracting {SUBGRAPH_HOPS}-hop subgraph...")
    G, focal = extract_subgraph(city, SUBGRAPH_HOPS, MAX_DISPLAY_NODES)
    print(f"  Subgraph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Count vaccine priority targets in view
    vax_targets = set(city.vaccine_priority_targets)
    vax_in_view = sum(1 for n in G.nodes() if n in vax_targets)
    print(f"  Vaccine priority targets in view: {vax_in_view}")
    print(f"  Total contact candidates: {len(city._contact_candidates)}")
    print(f"  Total vaccine priority targets: {len(vax_targets)}")

    print("\nRendering network...")
    out_path = render_network(city, G, focal, snapshot_day)

    print(f"\nDone! → {out_path}")


if __name__ == "__main__":
    main()
