/**
 * API utility module providing typed wrapper for making authenticated backend requests.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  token?: string | null;
}

/**
 * Fetch a resource from the backend with Clerk Bearer token authentication.
 */
export async function fetchWithAuth(endpoint: string, options: RequestOptions = {}) {
  const { token, headers, ...rest } = options;
  
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }
  
  const config = {
    ...rest,
    headers: {
      ...authHeaders,
      ...headers,
    },
  };
  
  const response = await fetch(`${BACKEND_URL}${endpoint}`, config);
  
  if (response.status === 204) {
    return null;
  }
  
  if (!response.ok) {
    let errorDetail = "API Request failed";
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
    }
    throw {
      status: response.status,
      message: errorDetail,
    };
  }
  
  return response.json();
}
