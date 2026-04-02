<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import Globe from "./lib/components/Globe.svelte";
    import Logo from "./assets/logo.svg";
    import type { VesselGPSData } from "./lib/helpers/globe";
    import { store } from "./lib/store.svelte";
    import {
        type VesselDevice,
        type DeviceQuery,
        type SimOverview,
        type SwitchingSystemResponse,
        type LogEntry,
    } from "./lib/types";
    import HoldButton from "./lib/components/HoldButton.svelte";

    const VMANAGE = "http://127.0.0.1:8000";
    const SIDECAR = "http://127.0.0.1:8080";
    const GPS_SVC = "http://127.0.0.1:8001";

    const getSafeId = (name: string) =>
        name.replace(/[^a-zA-Z0-9-]/g, "-").toLowerCase();

    // ── Globe data ────────────────────────────────────────────────────
    let vesselsGPS = $state<VesselGPSData[]>([]);
    let intervalId: ReturnType<typeof setInterval>;

    async function updateGlobe() {
        try {
            const r = await fetch(`${GPS_SVC}/vessels`);
            vesselsGPS = (await r.json()) as VesselGPSData[];
        } catch {}
    }

    // ── vManage device list ───────────────────────────────────────────
    let vesselDevices = $state<VesselDevice[]>([]);

    async function fetchVesselDevices() {
        try {
            const r = await fetch(`${VMANAGE}/dataservice/device`);
            const { data } = (await r.json()) as DeviceQuery;
            vesselDevices = data;
        } catch {}
    }

    // ── Sim overview (health / metrics) ──────────────────────────────
    let simOverview = $state<SimOverview>({});
    let simOverviewInterval: ReturnType<typeof setInterval>;

    async function updateSimOverview() {
        try {
            const r = await fetch(`${VMANAGE}/sim/overview`);
            simOverview = (await r.json()) as SimOverview;
        } catch {}
    }

    // ── Sidecar logs ─────────────────────────────────────────────────
    let logsData = $state<SwitchingSystemResponse | null>(null);
    let logsInterval: ReturnType<typeof setInterval>;
    // Only show entries that have a routing_update (actual switch events)
    let switchEvents = $derived(
        logsData?.logs.filter((l) => l.routing_update !== null).reverse() ?? [],
    );

    let latestLogEntry = $derived(
        logsData?.logs && logsData.logs.length > 0
            ? logsData.logs[logsData.logs.length - 1]
            : null,
    );

    async function updateLogs() {
        if (!store.selectedVesselId || vesselDevices.length === 0) return;
        const vessel = vesselDevices.find(
            (v) => getSafeId(v.host_name) === store.selectedVesselId,
        );
        if (!vessel) return;
        try {
            const r = await fetch(
                `${SIDECAR}/logs?system_ip=${vessel.system_ip}&limit=100`,
            );
            logsData = (await r.json()) as SwitchingSystemResponse;
        } catch {}
    }

    // ── Health sliders ────────────────────────────────────────────────
    let health5G = $state(100);
    let healthSat = $state(100);
    let debounceTimer5G: ReturnType<typeof setTimeout>;
    let debounceTimerSat: ReturnType<typeof setTimeout>;

    function selectedVessel() {
        if (!store.selectedVesselId) return null;
        return (
            vesselDevices.find(
                (v) => getSafeId(v.host_name) === store.selectedVesselId,
            ) ?? null
        );
    }

    async function postHealth(linkType: "5G" | "Satellite", value: number) {
        const v = selectedVessel();
        if (!v) return;
        try {
            await fetch(
                `${VMANAGE}/sim/control/health/${v.system_ip}/${linkType}`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ health: value }),
                },
            );
        } catch {}
    }

    function on5GInput(e: Event) {
        health5G = Number((e.target as HTMLInputElement).value);
        clearTimeout(debounceTimer5G);
        debounceTimer5G = setTimeout(() => postHealth("5G", health5G), 300);
    }

    $effect(() => {
        clearTimeout(debounceTimer5G);
        debounceTimer5G = setTimeout(() => postHealth("5G", health5G), 300);
        console.log(health5G);
    });

    $effect(() => {
        clearTimeout(debounceTimerSat);
        debounceTimerSat = setTimeout(() => postHealth("5G", healthSat), 300);
    });

    function onSatInput(e: Event) {
        healthSat = Number((e.target as HTMLInputElement).value);
        clearTimeout(debounceTimerSat);
        debounceTimerSat = setTimeout(
            () => postHealth("Satellite", healthSat),
            300,
        );
    }

    // Reset sliders when vessel changes
    $effect(() => {
        if (store.selectedVesselId) {
            const vesselName = vesselsGPS.find(
                (v) => getSafeId(v.name) === store.selectedVesselId,
            )?.name;

            const links = vesselName
                ? simOverview[vesselName]?.links
                : undefined;

            const newHealth5G = Number(links?.["5G"]?.health.slice(0, -1));
            if (Number.isFinite(newHealth5G)) {
                health5G = newHealth5G;
            }

            const newHealthSat = Number(
                links?.["Satellite"]?.health.slice(0, -1),
            );
            if (Number.isFinite(newHealthSat)) {
                healthSat = newHealthSat;
            }
        }
    });

    // ── Lifecycle ─────────────────────────────────────────────────────
    onMount(async () => {
        intervalId = setInterval(updateGlobe, 100);
        simOverviewInterval = setInterval(updateSimOverview, 2000);
        await fetchVesselDevices();
        logsInterval = setInterval(updateLogs, 2000);
    });

    onDestroy(() => {
        clearInterval(intervalId);
        clearInterval(simOverviewInterval);
        clearInterval(logsInterval);
        clearTimeout(debounceTimer5G);
        clearTimeout(debounceTimerSat);
    });

    // ── Helpers ───────────────────────────────────────────────────────
    function isActiveLink(
        linkName: string,
        activeColor: "cellular" | "biz-internet",
    ) {
        return (
            (linkName === "5G" && activeColor === "cellular") ||
            (linkName === "Satellite" && activeColor === "biz-internet")
        );
    }

    function formatStep(log: LogEntry): string {
        const fiveG = log.links["5G"];
        const sat = log.links["Satellite"];
        const parts: string[] = [];
        if (fiveG)
            parts.push(
                `5G ${fiveG.predicted_vqoe.toFixed(1)} → ${log.active_link === "5G" ? "▲" : ""}`,
            );
        if (sat)
            parts.push(
                `Sat ${sat.predicted_vqoe.toFixed(1)} → ${log.active_link === "Satellite" ? "▲" : ""}`,
            );
        return parts.join("  ·  ");
    }

    let timer5GSlider;
    let timerSatelliteSlider;
</script>

<nav class="w-full border-b border-white/8">
    <div class="max-w-7xl mx-auto py-5 flex items-center gap-2">
        <img alt="Aegis Logo" class="h-18" src={Logo} />
        <h1 class="font-serif text-6xl translate-y-1.5">Aegis</h1>
    </div>
</nav>

<section
    class="max-w-7xl mx-auto flex items-center justify-center gap-6 p-4 w-full"
>
    <!-- Globe -->
    <div class="margin-auto w-fit flex-1 flex items-center justify-center">
        <Globe {vesselsGPS} />
    </div>

    <!-- Right panel -->
    <div class="h-full flex-1 flex flex-col gap-4 transition-all">
        {#if store.selectedVesselId}
            {@const name = vesselsGPS.find(
                (v) => v.id === store.selectedVesselId,
            )?.name}
            {#if name && simOverview[name]}
                <!-- Vessel header + link status ──────────────────── -->
                <div
                    class="rounded-2xl border border-white/10 p-4 bg-[#181b1f]"
                >
                    <h2 class="vessel-name">{name}</h2>

                    <div class="links-grid">
                        {#each Object.keys(simOverview[name].links) as linkName}
                            {@const link = simOverview[name].links[linkName]}
                            {@const active = isActiveLink(
                                linkName,
                                simOverview[name].active_color,
                            )}
                            {@const scores = latestLogEntry?.links[linkName]}
                            <div class="link-card" class:link-active={active}>
                                <div class="link-header">
                                    <span class="link-name">{linkName}</span>
                                    {#if active}
                                        <span class="active-pill">Active</span>
                                    {/if}
                                </div>
                                <p class="link-metric">
                                    Health: <strong>{link.health}</strong>
                                </p>
                                {#if scores}
                                    <p class="link-metric">
                                        Score: <strong
                                            >{scores.actual_vqoe.toFixed(
                                                1,
                                            )}</strong
                                        >
                                    </p>
                                    <p class="link-metric">
                                        Predicted: <strong
                                            >{scores.predicted_vqoe.toFixed(
                                                1,
                                            )}</strong
                                        >
                                    </p>
                                {/if}
                                <p class="link-metric">{link.live_metrics}</p>
                            </div>
                        {/each}
                    </div>
                </div>

                <!-- Health sliders ────────────────────────────────── -->
                <div
                    class="rounded-2xl border border-white/10 p-4 bg-[#181b1f]"
                >
                    <h3 class="section-title">Link Health Control</h3>

                    <div class="slider-group">
                        <div class="slider-row">
                            <label class="slider-label" for="slider-5g">
                                <span class="slider-link-name">5G</span>
                                <span class="slider-value">{health5G}%</span>
                            </label>
                            <div
                                class="w-full flex items-center justify-between gap-2"
                            >
                                <HoldButton
                                    label="–"
                                    bind:count={health5G}
                                    decrement
                                />
                                <input
                                    id="slider-5g"
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={health5G}
                                    oninput={on5GInput}
                                    class="slider slider-5g"
                                />
                                <HoldButton label="+" bind:count={health5G} />
                            </div>
                        </div>

                        <div class="slider-row">
                            <label class="slider-label" for="slider-sat">
                                <span class="slider-link-name">Satellite</span>
                                <span class="slider-value">{healthSat}%</span>
                            </label>

                            <div
                                class="w-full flex items-center justify-between gap-2"
                            >
                                <HoldButton
                                    label="–"
                                    bind:count={healthSat}
                                    decrement
                                />
                                <input
                                    id="slider-sat"
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={healthSat}
                                    oninput={onSatInput}
                                    class="slider slider-sat"
                                />
                                <HoldButton label="+" bind:count={healthSat} />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Switch log ────────────────────────────────────── -->
                <div
                    class="rounded-2xl border border-white/10 bg-[#181b1f] flex flex-col min-h-0 flex-1"
                >
                    <div class="log-header">
                        <h3 class="section-title" style="margin:0">
                            Switch Events
                        </h3>
                        <span class="log-count">
                            {switchEvents.length} event{switchEvents.length !==
                            1
                                ? "s"
                                : ""}
                        </span>
                    </div>

                    <div class="log-scroll">
                        {#if switchEvents.length === 0}
                            <p class="log-empty">No switches recorded yet.</p>
                        {:else}
                            {#each switchEvents as log}
                                <div class="log-entry">
                                    <div class="log-top">
                                        <span class="log-step"
                                            >step {log.step}</span
                                        >
                                        <span
                                            class="log-link-badge"
                                            class:badge-5g={log.active_link ===
                                                "5G"}
                                            class:badge-sat={log.active_link ===
                                                "Satellite"}
                                        >
                                            → {log.active_link}
                                        </span>
                                    </div>
                                    <p class="log-update">
                                        {log.routing_update}
                                    </p>
                                    <p class="log-scores">{formatStep(log)}</p>
                                </div>
                            {/each}
                        {/if}
                    </div>
                </div>
            {/if}
        {:else}
            <div
                class="empty-state rounded-2xl border border-white/10 bg-[#181b1f]"
            >
                <p>
                    Select a vessel on the globe to inspect its network status.
                </p>
            </div>
        {/if}
    </div>
</section>

<style>
    /* ── Nav title ──────────────────────────────────────────── */
    h1 {
        background: linear-gradient(
            to bottom,
            #cccccc 22%,
            #b8b8b8 26%,
            #b8b8b8 27%,
            #d9d9d9 40%,
            #777 78%
        );
        line-height: 1.25;
        background-position: 0 0;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: #fff;
    }

    /* ── Vessel header ──────────────────────────────────────── */
    .vessel-name {
        font-size: 1.25rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 0 0 0.75rem;
    }

    /* ── Link cards ─────────────────────────────────────────── */
    .links-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
    }

    .link-card {
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 0.75rem;
        padding: 0.75rem;
        background: rgba(255, 255, 255, 0.03);
        transition: border-color 0.2s;
    }

    .link-card.link-active {
        border-color: rgba(74, 222, 128, 0.35);
        background: rgba(74, 222, 128, 0.05);
    }

    .link-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.4rem;
    }

    .link-name {
        font-size: 0.8rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .active-pill {
        font-size: 0.65rem;
        padding: 0.1rem 0.5rem;
        border-radius: 999px;
        background: rgba(74, 222, 128, 0.12);
        border: 1px solid rgba(74, 222, 128, 0.4);
        color: #4ade80;
        font-weight: 500;
    }

    .link-metric {
        font-size: 0.72rem;
        color: #64748b;
        margin: 0.15rem 0 0;
        line-height: 1.5;
    }

    /* ── Section title ──────────────────────────────────────── */
    .section-title {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #475569;
        margin: 0 0 1rem;
    }

    /* ── Sliders ────────────────────────────────────────────── */
    .slider-group {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .slider-row {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }

    .slider-label {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }

    .slider-link-name {
        font-size: 0.8rem;
        font-weight: 500;
        color: #94a3b8;
    }

    .slider-value {
        font-size: 0.8rem;
        font-variant-numeric: tabular-nums;
        color: #64748b;
    }

    .slider {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        height: 4px;
        border-radius: 2px;
        outline: none;
        cursor: pointer;
        transition: opacity 0.15s;
    }

    .slider:hover {
        opacity: 0.9;
    }

    .slider-5g {
        background: linear-gradient(
            to right,
            #3b82f6 0%,
            #3b82f6 calc(var(--val, 100) * 1%),
            rgba(255, 255, 255, 0.1) calc(var(--val, 100) * 1%)
        );
    }

    .slider-sat {
        background: linear-gradient(
            to right,
            #a855f7 0%,
            #a855f7 calc(var(--val, 100) * 1%),
            rgba(255, 255, 255, 0.1) calc(var(--val, 100) * 1%)
        );
    }

    .slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #e2e8f0;
        cursor: pointer;
        box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.4);
        transition: transform 0.1s;
    }

    .slider::-webkit-slider-thumb:hover {
        transform: scale(1.2);
    }

    .slider::-moz-range-thumb {
        width: 14px;
        height: 14px;
        border: none;
        border-radius: 50%;
        background: #e2e8f0;
        cursor: pointer;
        box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.4);
    }

    /* ── Log panel ──────────────────────────────────────────── */
    .log-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1rem 0.75rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .log-count {
        font-size: 0.7rem;
        color: #475569;
        font-variant-numeric: tabular-nums;
    }

    .log-scroll {
        overflow-y: auto;
        max-height: 220px;
        padding: 0.5rem 0;
    }

    .log-scroll::-webkit-scrollbar {
        width: 4px;
    }
    .log-scroll::-webkit-scrollbar-track {
        background: transparent;
    }
    .log-scroll::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 2px;
    }

    .log-empty {
        font-size: 0.78rem;
        color: #334155;
        text-align: center;
        padding: 2rem 1rem;
        margin: 0;
    }

    .log-entry {
        padding: 0.6rem 1rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        transition: background 0.1s;
    }

    .log-entry:last-child {
        border-bottom: none;
    }
    .log-entry:hover {
        background: rgba(255, 255, 255, 0.02);
    }

    .log-top {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.25rem;
    }

    .log-step {
        font-size: 0.68rem;
        color: #334155;
        font-variant-numeric: tabular-nums;
        font-family: ui-monospace, monospace;
    }

    .log-link-badge {
        font-size: 0.68rem;
        font-weight: 600;
        padding: 0.1rem 0.45rem;
        border-radius: 999px;
        border: 1px solid;
    }

    .badge-5g {
        color: #60a5fa;
        border-color: rgba(96, 165, 250, 0.3);
        background: rgba(96, 165, 250, 0.08);
    }

    .badge-sat {
        color: #c084fc;
        border-color: rgba(192, 132, 252, 0.3);
        background: rgba(192, 132, 252, 0.08);
    }

    .log-update {
        font-size: 0.75rem;
        color: #94a3b8;
        margin: 0 0 0.2rem;
        line-height: 1.4;
    }

    .log-scores {
        font-size: 0.68rem;
        color: #475569;
        margin: 0;
        font-family: ui-monospace, monospace;
    }

    /* ── Empty state ────────────────────────────────────────── */
    .empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 300px;
        padding: 2rem;
    }

    .empty-state p {
        font-size: 0.85rem;
        color: #334155;
        text-align: center;
    }
</style>
