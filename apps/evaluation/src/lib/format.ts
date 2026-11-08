export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`

export const scoreValue = (value: number | null | undefined) =>
  value == null ? "—" : value.toFixed(1)

export const methodLabel = (method: string) =>
  ({ vector: "Vector", keyword: "Keyword", hybrid_rrf: "Hybrid + RRF" })[
    method
  ] ?? method

export const runShort = (id: string) => `${id.slice(0, 8)} · ${id.slice(9, 15)}`
