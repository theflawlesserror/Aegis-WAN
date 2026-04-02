import type { VesselGPSData } from "./helpers/globe";

export const sampleVessels: VesselGPSData[] = [
  {
    id: "ever-given",
    name: "Ever Given",
    pos: [20.0, 39.0],
    path: [
      [1.27, 103.54], // Port of Tanjung Pelepas, Malaysia
      [5.5, 98.5], // Strait of Malacca
      [5.9, 80.0], // South of Sri Lanka
      [12.5, 43.3], // Bab el-Mandeb Strait
      [20.0, 39.0], // Red Sea
      [30.0, 32.5], // Suez Canal
      [34.0, 20.0], // Mediterranean Sea
      [35.9, -5.5], // Strait of Gibraltar
      [49.5, -4.0], // English Channel
      [51.9, 4.1], // Port of Rotterdam, Netherlands
    ],
  },
  {
    id: "hmm-algeciras",
    name: "HMM Algeciras",
    pos: [45.0, 170.0],
    path: [
      [35.1, 129.0], // Port of Busan, South Korea
      [41.4, 140.5], // Tsugaru Strait (Japan)
      [45.0, 170.0], // North Pacific crossing
      [34.0, -120.0], // Approach California coast
      [33.7, -118.2], // Port of Long Beach, USA
    ],
  },
  {
    id: "madrid-maersk",
    name: "Madrid Maersk",
    pos: [45.0, -30.0],
    path: [
      [53.5, 8.5], // Port of Bremerhaven, Germany
      [50.0, -2.0], // English Channel
      [45.0, -30.0], // North Atlantic crossing
      [44.0, -60.0], // South of Halifax, Canada
      [40.7, -74.1], // Port of Newark, USA
    ],
  },
  {
    id: "mozah",
    name: "Mozah",
    pos: [26.5, 54.5],
    path: [
      [25.9, 51.6], // Ras Laffan Industrial City, Qatar
      [26.5, 54.5], // Persian Gulf
      [26.6, 56.3], // Strait of Hormuz
      [24.5, 59.0], // Gulf of Oman
      [15.0, 65.0], // Arabian Sea
      [9.9, 76.3], // Port of Kochi, India
    ],
  },
];
