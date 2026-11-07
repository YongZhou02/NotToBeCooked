/** Keep loopback development requests on the page's site so refresh cookies work. */
export function resolveApiBaseUrl(configured?: string, pageOrigin?: string): string {
    const base = configured || "http://localhost:8000"
    if (!pageOrigin || !/^https?:\/\//.test(base)) return base

    try {
        const api = new URL(base)
        const page = new URL(pageOrigin)
        const loopback = new Set(["localhost", "127.0.0.1"])
        if (
            loopback.has(api.hostname) &&
            loopback.has(page.hostname) &&
            api.protocol === page.protocol
        ) {
            api.hostname = page.hostname
            return api.toString().replace(/\/$/, "")
        }
    } catch {
        // Preserve the configured value; request handling reports invalid URLs.
    }
    return base
}
