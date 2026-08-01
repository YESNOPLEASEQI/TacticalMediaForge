export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function parseResponse(response: Response) {
  const contentType = response.headers.get("content-type");
  if (contentType?.includes("application/json")) {
    return response.json() as Promise<unknown>;
  }

  return response.text();
}

function errorMessageFromPayload(payload: unknown, fallback: string) {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }

  if (typeof payload === "string" && payload.length > 0) {
    return payload;
  }

  return fallback;
}

export const apiClient = {
  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${apiBaseUrl}${path}`);
    const payload = await parseResponse(response);

    if (!response.ok) {
      throw new ApiError(
        errorMessageFromPayload(payload, `Request failed with ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as T;
  },

  async post<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const payload = await parseResponse(response);

    if (!response.ok) {
      throw new ApiError(
        errorMessageFromPayload(payload, `Request failed with ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as TResponse;
  },

  async put<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const payload = await parseResponse(response);

    if (!response.ok) {
      throw new ApiError(
        errorMessageFromPayload(payload, `Request failed with ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as TResponse;
  },

  async patch<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const payload = await parseResponse(response);

    if (!response.ok) {
      throw new ApiError(
        errorMessageFromPayload(payload, `Request failed with ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as TResponse;
  },

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: "DELETE",
    });
    const payload = await parseResponse(response);

    if (!response.ok) {
      throw new ApiError(
        errorMessageFromPayload(payload, `Request failed with ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as T;
  },
};
