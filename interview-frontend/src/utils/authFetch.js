// Simple wrapper around fetch that includes credentials and JSON handling for authenticated API calls.
// Adjust as needed for your backend authentication scheme.
export async function authFetch(url, options = {}) {
  const defaults = {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
  };
  const opts = {
    ...defaults,
    ...options,
    // Merge headers preserving defaults
    headers: { ...defaults.headers, ...(options.headers || {}) },
  };
  const response = await fetch(url, opts);
  if (!response.ok) {
    const errorText = await response.text();
    const err = new Error(`Request failed with status ${response.status}`);
    err.status = response.status;
    err.body = errorText;
    throw err;
  }
  // Assume JSON response; fallback to plain text if parsing fails
  try {
    return await response.json();
  } catch {
    return await response.text();
  }
}
