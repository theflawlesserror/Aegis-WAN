- Ship Sidecar
    1. Router (Flask/Hono.js)
    2. Our actual AI app
    3. Logging (NodeExporter + Redis Cache) 

- Main System
    1. Prometheus and Grafana
    2. Mailer for events (nodemailer)
    3. Log parser engine to check for anomalies (custom, using syslog-ng)
    4. Cloudflare Radar/Cisco 1000eyes

- Tasks
    1. API [[Endpoints]]:
        1. Documentation
        2. Deployment (Flask)
    2. Logging and Monitoring (NodeExporter, Prometheur, Grafana)