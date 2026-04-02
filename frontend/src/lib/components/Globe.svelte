<script lang="ts">
    import { fade } from "svelte/transition";
    import createGlobe from "cobe";
    import {
        smoothRoute,
        getGroundedArcs,
        type VesselGPSData,
        type VisualVessel,
    } from "../helpers/globe";
    import { store } from "../store.svelte";

    // --- Props ---
    let { vesselsGPS = [] }: { vesselsGPS: VesselGPSData[] } = $props();

    // --- UI State (Reactive) ---
    let isPaused = $state(false);

    const getSafeId = (name: string) =>
        name.replace(/[^a-zA-Z0-9-]/g, "-").toLowerCase();

    let htmlMarkers = $derived(
        vesselsGPS.map((v) => ({
            id: getSafeId(v.name),
            name: v.name,
        })),
    );

    // --- Animation State (Pure JS, NON-Reactive) ---
    let canvas: HTMLCanvasElement;
    let animVessels: (VisualVessel & { id: string })[] = [];
    let cachedArcs: any[] = [];

    let baseRotation = 0;
    let targetRotation = 0;
    let currentTheta = 0.2;
    let velocity = 0;
    let isDragging = false;
    let lastPointerX: number | null = null;

    // --- Handlers ---
    function handleLabelClick(id: string) {
        if (store.selectedVesselId === id) {
            store.selectedVesselId = null;
            isPaused = false;
        } else {
            store.selectedVesselId = id;
            isPaused = true;
            // TODO: Open your modal here
        }
    }

    function onPointerDown(e: PointerEvent) {
        isDragging = true;
        lastPointerX = e.clientX;
        velocity = 0;

        // UX Fix: If the user drags the globe, break the paused focus state
        if (isPaused) {
            isPaused = false;
            store.selectedVesselId = null;
        }
    }

    function onPointerMove(e: PointerEvent) {
        if (!isDragging || lastPointerX === null) return;
        const delta = e.clientX - lastPointerX;
        velocity = delta / 200;
        targetRotation += velocity;
        lastPointerX = e.clientX;
    }

    function onPointerUp() {
        isDragging = false;
        lastPointerX = null;
    }

    // --- Sync Props to Animation State ---
    $effect(() => {
        vesselsGPS.forEach((vessel, i) => {
            const safeId = getSafeId(vessel.name);

            if (!animVessels[i]) {
                animVessels[i] = {
                    id: safeId,
                    currentPos: [...vessel.pos],
                    targetPos: [...vessel.pos],
                };
            } else {
                animVessels[i].id = safeId;
                animVessels[i].targetPos = [...vessel.pos];
            }
        });

        if (animVessels.length > vesselsGPS.length) {
            animVessels.length = vesselsGPS.length;
        }

        cachedArcs = vesselsGPS.flatMap((v) =>
            getGroundedArcs(smoothRoute(v.path, 4)),
        );
    });

    // --- COBE Lifecycle & Animation Loop ---
    $effect(() => {
        if (!canvas) return;

        const globe = createGlobe(canvas, {
            devicePixelRatio: 2,
            width: 1200,
            height: 1200,
            phi: 0,
            theta: 0.2,
            dark: 1,
            diffuse: 1.2,
            mapSamples: 9600,
            mapBrightness: 6,
            baseColor: [0.1, 0.1, 0.15],
            markerColor: [0.24, 0.27, 0.27],
            glowColor: [0.3, 0.3, 0.5],
            markers: [],
            arcs: [],
            arcColor: [0.2, 0.4, 0.8],
            arcWidth: 0.25,
            arcHeight: 0.005,
            markerElevation: 0.005,
        });

        let animationId: number;

        function animate() {
            let targetTheta = 0.2; // Default ambient camera tilt

            // 1. Globe Physics & Centering Logic
            if (isDragging) {
                // Let user drag freely
            } else if (!isPaused) {
                // Ambient rotation state
                baseRotation += 0.001;
                velocity *= 0.95;
                targetRotation += velocity;
            } else if (isPaused && store.selectedVesselId) {
                // Paused & Centering state
                const v = animVessels.find(
                    (v) => v.id === store.selectedVesselId,
                );

                if (v) {
                    // CORRECTED MATH: COBE's official geographic to spherical mapping
                    const targetPhi =
                        Math.PI -
                        ((v.currentPos[1] * Math.PI) / 180 - Math.PI / 2);
                    const currentPhi = baseRotation + targetRotation;

                    const phiDiff = Math.atan2(
                        Math.sin(targetPhi - currentPhi),
                        Math.cos(targetPhi - currentPhi),
                    );
                    targetRotation += phiDiff * 0.05;

                    targetTheta = (v.currentPos[0] * Math.PI) / 180;
                }
            }

            // Ease theta (camera tilt) towards its target smoothly
            currentTheta += (targetTheta - currentTheta) * 0.05;

            // 2. Ease markers towards their server-provided coordinates
            animVessels.forEach((v) => {
                v.currentPos[0] += (v.targetPos[0] - v.currentPos[0]) * 0.05;
                let lonDiff = v.targetPos[1] - v.currentPos[1];
                if (lonDiff > 180) lonDiff -= 360;
                if (lonDiff < -180) lonDiff += 360;
                v.currentPos[1] += lonDiff * 0.05;
                v.currentPos[1] =
                    ((((v.currentPos[1] + 180) % 360) + 360) % 360) - 180;
            });

            // 3. Update Globe
            const markers = animVessels.map((v) => ({
                id: v.id,
                location: v.currentPos,
                size: 0.04,
                color: [0.4, 0.66, 0.37] as [number, number, number],
            }));

            globe.update({
                phi: baseRotation + targetRotation,
                theta: currentTheta,
                markers: markers,
                arcs: cachedArcs,
            });

            animationId = requestAnimationFrame(animate);
        }

        animate();

        return () => {
            globe.destroy();
            cancelAnimationFrame(animationId);
        };
    });
</script>

<div class="globe-wrapper" in:fade={{ duration: 1000 }}>
    <canvas
        bind:this={canvas}
        onpointerdown={onPointerDown}
        onpointermove={onPointerMove}
        onpointerup={onPointerUp}
        onpointerleave={onPointerUp}
    ></canvas>

    {#each htmlMarkers as m}
        <button
            class="marker-label {store.selectedVesselId === m.id
                ? 'active'
                : ''}"
            style="position-anchor: --cobe-{m.id}; opacity: var(--cobe-visible-{m.id}, 0);"
            onpointerdown={(e) => e.stopPropagation()}
            onclick={() => handleLabelClick(m.id)}
            aria-label="View details for {m.name}"
        >
            {m.name}
        </button>
    {/each}
</div>

<style>
    .globe-wrapper {
        position: relative;
        width: 600px;
        height: 600px;
        max-width: 100%;
        max-height: 100%;
    }

    canvas {
        width: 100%;
        height: 100%;
        cursor: grab;
        display: block;
    }

    canvas:active {
        cursor: grabbing;
    }

    .marker-label {
        position: absolute;
        bottom: anchor(top);
        left: anchor(center);
        translate: -50% 0;
        margin-bottom: 8px;
        padding: 0.25rem 0.5rem;
        background: #1a1a1a;
        color: #fff;
        font-size: 0.75rem;
        border: 1px solid transparent;
        border-radius: 4px;
        white-space: nowrap;
        pointer-events: auto;
        cursor: pointer;
        transition:
            opacity 0.3s,
            background 0.2s,
            border-color 0.2s;
    }

    .marker-label:hover {
        background: #2a2a2a;
        border-color: rgba(255, 255, 255, 0.3);
    }

    .marker-label.active {
        background: #3b82f6;
        border-color: #60a5fa;
        z-index: 10;
    }
</style>
