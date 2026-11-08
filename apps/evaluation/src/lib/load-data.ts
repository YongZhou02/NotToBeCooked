import type { DashboardData } from "../types"

export interface LoadedData {
  data: DashboardData
  /** PDF file names found in the documents folder. */
  files: string[]
}

async function getJson<T>(name: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}${name}`)
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`)
  return (await response.json()) as T
}

/**
 * dashboard_data.json is the only data source. The list of PDFs is a
 * convenience: if it cannot be read the app still works with the documents
 * the data names.
 */
export async function loadData(): Promise<LoadedData> {
  const data = await getJson<DashboardData>("dashboard_data.json")
  let files: string[] = []
  try {
    const listed = await getJson<unknown>("documents/index.json")
    if (Array.isArray(listed))
      files = listed.filter((x): x is string => typeof x === "string")
  } catch {
    files = []
  }
  return { data, files }
}
