# los-jalapenos

Intelligent Multi-WAN Routing — Los Jalapeños | Code Recet powered by Armada

This project simulates an intelligent multi-WAN routing system. It consists of several microservices that work together to predict network performance and make routing decisions.

## Prerequisites

Before you begin, ensure you have the following tools installed:

-   [**Just**](https://just.systems/man/en/): A command runner.
-   [**Node.js**](https://nodejs.org/) (which includes `npm`) and [**pnpm**](https://pnpm.io/): For the frontend.
-   [**Python**](https://www.python.org/) and [**uv**](https://github.com/astral-sh/uv): For the Python services.
-   [**Docker**](https://www.docker.com/): For running Prometheus and Grafana.

## Installation

1.  **Install Frontend Dependencies:**

    ```bash
    cd frontend
    pnpm install
    cd ..
    ```

2.  **Install Python Dependencies:**

    You'll need to sync the dependencies for each Python service using `uv`.

    ```bash
    # For the router
    cd router/apiserver
    uv sync
    cd ../..

    # For the predictor
    cd predictor
    uv sync
    cd ..

    # For the vessel-gps
    cd vessel-gps
    uv sync
    cd ..
    ```

## Running the Application

Once the dependencies are installed, you can start all the services using `just`.

```bash
just up
```

This will start all the services in a `tmux` session.

## Service Port Mappings

| Service      | Port | Description                               |
| :----------- | :--- | :---------------------------------------- |
| Router       | 8000 | Main API server for routing logic.        |
| Vessel GPS   | 8001 | GPS service for the vessels.              |
| Prometheus   | 8003 | Metrics collection.                       |
| Grafana      | 8004 | Metrics visualization dashboard.          |
| Frontend     | 8005 | The web interface for the application.    |
| Predictor    | 8080 | Predicts network performance.             |
