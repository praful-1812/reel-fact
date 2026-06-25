/**
 * API client — talks to the Reel Fact FastAPI backend.
 *
 * The backend base URL is configurable at runtime (see HomeScreen settings)
 * because it differs by environment:
 *   • Android emulator → http://10.0.2.2:8000   (host machine alias)
 *   • Physical device  → http://<your-LAN-ip>:8000
 *   • iOS simulator    → http://localhost:8000
 */
import Constants from "expo-constants";

export type Verdict = "true" | "false" | "misleading" | "unverifiable";
export type JobStatus = "queued" | "processing" | "done" | "failed";

export interface ClaimResult {
  claim: string;
  verdict: Verdict;
  confidence: number;
  explanation: string;
  what_to_check: string;
}

export interface OverallResult {
  verdict: Verdict;
  confidence: number;
  summary: string;
  whats_wrong: string[];
}

export interface ReelSource {
  url: string;
  uploader?: string | null;
  title?: string | null;
  caption?: string | null;
  duration?: number | null;
  thumbnail_url?: string | null;
}

export interface Job {
  id: number;
  status: JobStatus;
  stage: string;
  stage_index: number;
  stage_total: number;
  error?: string | null;
  source: ReelSource;
  transcript?: string | null;
  claims: ClaimResult[];
  overall?: OverallResult | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface Health {
  status: string;
  default_model: string;
  transcription_backend: string;
  ffmpeg_installed: boolean;
}

/** Default backend URL pulled from app.json → expo.extra.apiBaseUrl. */
export const DEFAULT_API_BASE: string =
  (Constants.expoConfig?.extra?.apiBaseUrl as string) || "http://10.0.2.2:8000";

function normalizeBase(base: string): string {
  return base.trim().replace(/\/+$/, "");
}

async function request<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const url = `${normalizeBase(base)}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch (e) {
    throw new Error(
      `Can't reach the backend at ${normalizeBase(base)}. Is it running and is the URL correct?`
    );
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

/** Submit a reel URL for fact-checking. Returns the freshly-created (queued) job. */
export function submitReel(base: string, url: string, model?: string): Promise<Job> {
  return request<Job>(base, "/api/factcheck", {
    method: "POST",
    body: JSON.stringify({ url, model: model || null }),
  });
}

/** Fetch a single job by id (used for polling). */
export function getJob(base: string, id: number): Promise<Job> {
  return request<Job>(base, `/api/factcheck/${id}`);
}

/** Recent jobs (history). */
export function listJobs(base: string, limit = 20): Promise<Job[]> {
  return request<Job[]>(base, `/api/factcheck?limit=${limit}`);
}

/** Backend health/capability probe. */
export function checkHealth(base: string): Promise<Health> {
  return request<Health>(base, "/health");
}

export function isTerminal(status: JobStatus): boolean {
  return status === "done" || status === "failed";
}
