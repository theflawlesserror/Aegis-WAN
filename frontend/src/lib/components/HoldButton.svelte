<script lang="ts">
    let {
        count = $bindable(0),
        step = 1,
        decrement = false,
        interval = 100,
        label = "Decrement",
    } = $props();

    let timer: ReturnType<typeof setInterval>;

    const stop = () => clearInterval(timer);
    const start = (e: Event) => {
        if (e.type === "touchstart") e.preventDefault();
        count += step * (decrement ? -1 : 1);
        timer = setInterval(
            () => (count += step * (decrement ? -1 : 1)),
            interval,
        );
    };
</script>

<button
    onmousedown={start}
    onmouseup={stop}
    onmouseleave={stop}
    ontouchstart={start}
    ontouchend={stop}
    style="user-select: none;"
>
    {label}
</button>
