export interface SimOverview {
  [vesselName: string]: {
    active_color: "cellular" | "biz-internet";
    active_policy: string;
    links: {
      [color: string]: {
        accumulated_tx_drops: number;
        health: string;
        live_metrics: string;
      };
    };
  };
}

export interface VesselDevice {
  device_id: string;
  host_name: string;
  reachability: string;
  status: string;
  system_ip: string;
}

// http://localhost:8000/dataservice/device
export interface DeviceQuery {
  data: VesselDevice[];
}

export interface VQoEMetrics {
  actual_vqoe: number;
  predicted_vqoe: number;
  rx_kbps: number;
  tx_kbps: number;
}

export interface NetworkLinks {
  "5G": VQoEMetrics;
  Satellite: VQoEMetrics;
}

export interface LogEntry {
  step: number;
  links: NetworkLinks;
  routing_update: string | null;
  active_link: "5G" | "Satellite";
}

export interface SwitchingSystemResponse {
  system_ip: string;
  active_link: "5G" | "Satellite";
  logs: LogEntry[];
}
