set shell := ["bash", "-c"]

session := "app-stack"
root    := invocation_directory()

# Start everything in parallel across tmux windows
up:
    @tmux kill-session -t {{session}} 2>/dev/null || true
    
    # Main Services
    @tmux new-session -d -s {{session}} -n "router" -c "{{root}}" "just router_up"
    @tmux new-window -t {{session}} -n "gps" -c "{{root}}" "just gps_up"
    @tmux new-window -t {{session}} -n "frontend" "just frontend_up"
    @tmux new-window -t {{session}} -n "predictor" -c "{{root}}" "just predictor_up"
    
    # Exporters (Optional: split into their own windows for easier debugging)
    @tmux new-window -t {{session}} -n "router-exp" -c "{{root}}" "just router_exporter"
    @tmux new-window -t {{session}} -n "pred-exp" -c "{{root}}" "just predictor_exporter"
    
    # Infrastructure
    @tmux new-window -t {{session}} -n "docker" -c "{{root}}" "just docker_up"
    
    @tmux attach-session -t {{session}}

[working-directory: "router/apiserver"]
router_up:
    uv run main.py

[working-directory: "router/apiserver"]
router_exporter:
    uv run exporter.py

[working-directory: "vessel-gps"]
gps_up:
    uv run uvicorn main:app --port=8001

[working-directory: "frontend"]
frontend_up:
    pnpm run dev

[working-directory: "predictor"]
predictor_up:
    uv run app.py

[working-directory: "predictor"]
predictor_exporter:
    uv run aegis_exporter.py

[working-directory: "prometheus"]
docker_up:
    docker compose up

[working-directory: "prometheus"]
docker_down:
    docker compose down
