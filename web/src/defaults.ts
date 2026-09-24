import type { EndmemberRow } from "./types";

// Interior point of a tetrahedron: (1,1,1) = 1/4 of each A..D.
export const DEFAULT_ENDMEMBERS: EndmemberRow[] = [
  { id: "A", t0: "0", t1: "0", t2: "0", cost: "1" },
  { id: "B", t0: "4", t1: "0", t2: "0", cost: "1" },
  { id: "C", t0: "0", t1: "4", t2: "0", cost: "1" },
  { id: "D", t0: "0", t1: "0", t2: "4", cost: "1" },
  { id: "E", t0: "5", t1: "5", t2: "5", cost: "2" },
];

export const DEFAULT_TARGET: [string, string, string] = ["1", "1", "1"];
