// --- Types ---
export interface VesselGPSData {
  id: string;
  name: string;
  pos: [number, number];
  path: [number, number][];
}

export interface VisualVessel {
  id: string;
  currentPos: [number, number];
  targetPos: [number, number];
}

/**
 * Normalizes a longitude value to stay within the range [-180, 180].
 * Handles edge cases where longitude might exceed these bounds due to
 * calculations crossing the antimeridian (date line).
 *
 * @param lon - The longitude value to normalize (in degrees)
 * @returns The normalized longitude value between -180 and 180
 */
export function wrapLon(lon: number): number {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

/**
 * Smooths a route by applying Chaikin's corner-cutting algorithm.
 * This creates a visually smoother curve by adding intermediate points
 * along each segment of the route.
 *
 * The algorithm works by:
 * 1. For each segment, calculating two new points at 25% and 75% along the segment
 * 2. Replacing sharp corners with smooth transitions
 * 3. Repeating for the specified number of iterations
 *
 * Also handles antimeridian crossing by normalizing longitude differences.
 *
 * @param route - Array of [latitude, longitude] coordinates representing the route waypoints
 * @param iterations - Number of smoothing iterations (default: 4). More iterations = smoother curve
 * @returns A new array of [latitude, longitude] coordinates with additional interpolated points
 *
 * @example
 * ```ts
 * const route = [[51.885, 4.2867], [40.6677, -74.0407]];
 * const smoothed = smoothRoute(route, 4);
 * // Returns route with many more points forming a smooth curve
 * ```
 */
export function smoothRoute(
  route: [number, number][],
  iterations = 4,
): [number, number][] {
  let currentPath = [...route];

  for (let iter = 0; iter < iterations; iter++) {
    const newPath: [number, number][] = [];
    newPath.push(currentPath[0]);

    for (let i = 0; i < currentPath.length - 1; i++) {
      const p0 = currentPath[i];
      const p1 = currentPath[i + 1];

      const lat0 = p0[0],
        lon0 = p0[1];
      let lat1 = p1[0],
        lon1 = p1[1];

      if (lon1 - lon0 > 180) lon1 -= 360;
      if (lon1 - lon0 < -180) lon1 += 360;

      const q0Lat = lat0 * 0.75 + lat1 * 0.25;
      const q0Lon = wrapLon(lon0 * 0.75 + lon1 * 0.25);

      const q1Lat = lat0 * 0.25 + lat1 * 0.75;
      const q1Lon = wrapLon(lon0 * 0.25 + lon1 * 0.75);

      newPath.push([q0Lat, q0Lon]);
      newPath.push([q1Lat, q1Lon]);
    }
    newPath.push(currentPath[currentPath.length - 1]);
    currentPath = newPath;
  }
  return currentPath;
}

/**
 * Interpolates a position along a route based on progress (0 to 1).
 * Uses simple linear interpolation between waypoints, handling
 * antimeridian crossing for routes that cross the date line.
 *
 * @param route - Array of [latitude, longitude] coordinates representing the route
 * @param progress - Progress value between 0 (start) and 1 (end)
 * @returns The interpolated [latitude, longitude] position on the route
 *
 * @example
 * ```ts
 * const route = [[51.885, 4.2867], [40.6677, -74.0407], [33.7292, -118.262]];
 * const pos = getPositionOnRoute(route, 0.5);
 * // Returns position halfway along the route
 * ```
 */
export function getPositionOnRoute(
  route: [number, number][],
  progress: number,
): [number, number] {
  if (progress >= 1) return route[route.length - 1];
  if (progress <= 0) return route[0];

  const totalSegments = route.length - 1;
  const exactSegment = progress * totalSegments;
  const segmentIndex = Math.floor(exactSegment);
  const segmentProgress = exactSegment - segmentIndex;

  const start = route[segmentIndex];
  const end = route[segmentIndex + 1];

  const lat = start[0] + (end[0] - start[0]) * segmentProgress;
  let lonDiff = end[1] - start[1];

  if (lonDiff > 180) lonDiff -= 360;
  if (lonDiff < -180) lonDiff += 360;

  const lon = start[1] + lonDiff * segmentProgress;
  return [lat, lon];
}

/**
 * Converts a smoothed route into a list of arc segments for COBE globe rendering.
 * Each segment becomes a from/to pair that COBE can render as connected arcs.
 *
 * @param route - Array of [latitude, longitude] coordinates (typically smoothed)
 * @returns Array of arc objects with 'from' and 'to' properties
 *
 * @example
 * ```ts
 * const route = smoothRoute([[51.885, 4.2867], [40.6677, -74.0407]], 4);
 * const arcs = getGroundedArcs(route);
 * // Returns [{from: [...], to: [...]}, ...] for each segment
 * ```
 */
export function getGroundedArcs(
  route: [number, number][],
): { from: [number, number]; to: [number, number] }[] {
  const arcs: { from: [number, number]; to: [number, number] }[] = [];
  for (let i = 0; i < route.length - 1; i++) {
    arcs.push({
      from: route[i],
      to: route[i + 1],
    });
  }
  return arcs;
}
