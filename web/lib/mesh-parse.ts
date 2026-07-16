/**
 * Client-side geometry parsing for the pre-flight upload. Reads STL (binary or
 * ASCII) and derives real mesh statistics — triangle count, open edges
 * (watertightness), and duplicate faces — that feed the setup validator's
 * mesh_watertight / cell-count checks. No dependencies, runs in the browser.
 */
export interface ParsedMesh {
  format: string;
  total_cells: number;      // triangles (surface facets)
  open_edges: number;       // non-manifold / boundary edges → not watertight
  duplicate_faces: number;
  watertight: boolean;
}

function quant(x: number): number {
  return Math.round(x * 1e5); // 1e-5 tolerance for shared-vertex matching
}

function analyze(tris: Float32Array, n: number, format: string): ParsedMesh {
  const edgeCount = new Map<string, number>();
  const faceKeys = new Set<string>();
  let duplicate = 0;
  for (let t = 0; t < n; t++) {
    const o = t * 9;
    const v = [
      [tris[o], tris[o + 1], tris[o + 2]],
      [tris[o + 3], tris[o + 4], tris[o + 5]],
      [tris[o + 6], tris[o + 7], tris[o + 8]],
    ].map((p) => `${quant(p[0])},${quant(p[1])},${quant(p[2])}`);
    const fkey = [...v].sort().join("|");
    if (faceKeys.has(fkey)) duplicate++;
    else faceKeys.add(fkey);
    for (let e = 0; e < 3; e++) {
      const a = v[e], b = v[(e + 1) % 3];
      const key = a < b ? `${a}~${b}` : `${b}~${a}`;
      edgeCount.set(key, (edgeCount.get(key) ?? 0) + 1);
    }
  }
  let open = 0;
  for (const c of edgeCount.values()) if (c !== 2) open++;
  return { format, total_cells: n, open_edges: open, duplicate_faces: duplicate, watertight: open === 0 };
}

function parseBinary(buf: ArrayBuffer): ParsedMesh {
  const dv = new DataView(buf);
  const n = dv.getUint32(80, true);
  const tris = new Float32Array(n * 9);
  let off = 84;
  for (let t = 0; t < n; t++) {
    off += 12; // skip normal
    for (let i = 0; i < 9; i++) { tris[t * 9 + i] = dv.getFloat32(off, true); off += 4; }
    off += 2; // attribute byte count
  }
  return analyze(tris, n, "stl-binary");
}

function parseAscii(text: string): ParsedMesh {
  const nums: number[] = [];
  const re = /vertex\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) nums.push(+m[1], +m[2], +m[3]);
  const n = Math.floor(nums.length / 9);
  return analyze(Float32Array.from(nums.slice(0, n * 9)), n, "stl-ascii");
}

export async function parseMeshFile(file: File): Promise<ParsedMesh | { error: string }> {
  const name = file.name.toLowerCase();
  if (name.endsWith(".json")) {
    try {
      const obj = JSON.parse(await file.text());
      const stats = obj.mesh ?? obj;
      return {
        format: "json",
        total_cells: Number(stats.total_cells ?? 0),
        open_edges: Number(stats.open_edges ?? 0),
        duplicate_faces: Number(stats.duplicate_faces ?? 0),
        watertight: (stats.open_edges ?? 0) === 0,
      };
    } catch {
      return { error: "Could not parse JSON mesh stats." };
    }
  }
  if (!name.endsWith(".stl")) {
    return { error: "Upload an .stl mesh or a .json mesh-stats file. (VTK/OpenFOAM/CGNS: export stats to JSON.)" };
  }
  const buf = await file.arrayBuffer();
  // ASCII STL starts with "solid" and has no binary triangle payload sized to header.
  const head = new TextDecoder().decode(buf.slice(0, 80)).trim().toLowerCase();
  const dv = new DataView(buf);
  const asciiLike = head.startsWith("solid") && buf.byteLength < 84 + 50 * (buf.byteLength > 84 ? dv.getUint32(80, true) : 0);
  try {
    return asciiLike ? parseAscii(new TextDecoder().decode(buf)) : parseBinary(buf);
  } catch {
    return { error: "Could not parse the STL file." };
  }
}
