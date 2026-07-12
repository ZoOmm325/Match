const DEFAULT_API_BASE_URL = "http://localhost:8000/api";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(
  /\/+$/,
  ""
);

export interface ApiResponse<T> {
  code: number;
  data: T | null;
  message: string;
}

export interface ApiErrorPayload {
  code?: number;
  data?: unknown;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: number;
  readonly data: unknown;

  constructor(message: string, options: { status?: number; code?: number; data?: unknown } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.code = options.code ?? this.status;
    this.data = options.data ?? null;
  }
}

export interface MatchRequest {
  jd_text: string;
  skill_top_k?: number;
  major_top_n?: number;
  skill_threshold?: number;
  generate_reasons?: boolean;
}

export interface MatchRecommendation {
  rank: number;
  major_id: number | null;
  major_name: string;
  major_code: string | null;
  final_score: number;
  skill_similarity_score: number;
  skill_coverage_score: number;
  employment_alignment_score: number;
  matched_skills: string[];
  missing_skills: string[];
  recommendation_reason: string;
  score_details: Record<string, unknown>;
}

export interface MatchResponseData {
  jd_id: number | null;
  extracted_skill_count: number;
  persisted_count: number;
  already_processed: boolean;
  recommendations: MatchRecommendation[];
}

export interface MatchHistoryData {
  jd_id: number;
  recommendations: MatchRecommendation[];
}

export interface SkillMatchInput {
  name: string;
  category?: string;
  proficiency_required?: string;
  embedding?: number[];
}

export interface MatchBySkillsRequest {
  skills: SkillMatchInput[];
  top_n?: number;
  generate_reasons?: boolean;
}

export interface JdSkill {
  id: number;
  skill_id: number;
  name: string;
  normalized_name: string;
  category: string | null;
  proficiency_required: string;
  relevance_score: number;
  extraction_method: string;
}

export interface JdDetail {
  id: number;
  raw_text: string;
  title: string | null;
  company: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
  skills: JdSkill[];
}

export interface JdListItem extends Omit<JdDetail, "skills"> {
  skill_count: number;
}

export interface JdListData {
  items: JdListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface JdTrendPoint {
  date: string;
  count: number;
}

export interface JdTrendData {
  days: number;
  total: number;
  points: JdTrendPoint[];
}

export interface JobMarketTrendPoint {
  year: number;
  count: number;
}

export interface JobMarketTrendData {
  keyword: string;
  years: number;
  total: number;
  data_source: string;
  source_url: string | null;
  points: JobMarketTrendPoint[];
}

export interface JdFetchRequest {
  keyword: string;
  city?: string;
  source_url?: string;
  max_results?: number;
}

export interface JdFetchData {
  keyword: string;
  title: string | null;
  company: string | null;
  source_url: string | null;
  source_domain: string | null;
  jd_text: string;
  inspected_urls: string[];
  from_cache: boolean;
}

export interface Major {
  id: number;
  name: string;
  code: string | null;
  category: string | null;
  description: string | null;
  curriculum: Record<string, unknown> | unknown[] | null;
  embedding: number[] | null;
  created_at: string;
}

export interface MajorListData {
  items: Major[];
  total: number;
  limit: number;
  offset: number;
}

export interface MajorSearchResult extends Major {
  similarity_score: number;
}

export interface MajorSearchData {
  query: string;
  results: MajorSearchResult[];
}

export interface SkillSummary {
  id: number;
  name: string;
  normalized_name: string;
  category: string | null;
  created_at: string;
}

export interface Skill extends SkillSummary {
  embedding: number[] | null;
}

export interface SkillListData {
  items: SkillSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface SkillCategoriesData {
  categories: string[];
}

export interface PaginationOptions {
  limit?: number;
  offset?: number;
}

export interface MajorListOptions extends PaginationOptions {
  category?: string;
  keyword?: string;
}

export interface SkillListOptions extends PaginationOptions {
  category?: string;
  keyword?: string;
}

export async function submitJD(
  jdText: string,
  options: Omit<MatchRequest, "jd_text"> = {}
): Promise<MatchResponseData> {
  return apiRequest<MatchResponseData>(
    "/match",
    {
      method: "POST",
      body: JSON.stringify({ jd_text: jdText, ...options }),
    },
    isMatchResponseData
  );
}

export async function matchBySkills(payload: MatchBySkillsRequest): Promise<MatchResponseData> {
  return apiRequest<MatchResponseData>(
    "/match/by-skills",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    isMatchResponseData
  );
}

export async function getMatchResult(jdId: number): Promise<MatchHistoryData> {
  return apiRequest<MatchHistoryData>(`/match/${encodeURIComponent(jdId)}`, {}, isMatchHistoryData);
}

export async function getJds(options: PaginationOptions = {}): Promise<JdListData> {
  return apiRequest<JdListData>(withQuery("/jd", options), {}, isJdListData);
}

export async function getJdTrend(days = 30): Promise<JdTrendData> {
  return apiRequest<JdTrendData>(withQuery("/jd/trend", { days }), {}, isJdTrendData);
}

export async function getJobMarketTrend(
  keyword: string,
  years = 5,
  sourceUrl?: string
): Promise<JobMarketTrendData> {
  return apiRequest<JobMarketTrendData>(
    withQuery("/jd/market-trend", { keyword, years, source_url: sourceUrl }),
    {},
    isJobMarketTrendData
  );
}

export async function fetchPublicJd(payload: JdFetchRequest): Promise<JdFetchData> {
  return apiRequest<JdFetchData>(
    "/jd/fetch",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    isJdFetchData
  );
}

export async function getJd(jdId: number): Promise<JdDetail> {
  return apiRequest<JdDetail>(`/jd/${encodeURIComponent(jdId)}`, {}, isJdDetail);
}

export async function deleteJd(jdId: number): Promise<void> {
  await apiRequest<null>(
    `/jd/${encodeURIComponent(jdId)}`,
    {
      method: "DELETE",
    },
    (value): value is null => value === null
  );
}

export async function getMajors(options: MajorListOptions = {}): Promise<MajorListData> {
  return apiRequest<MajorListData>(withQuery("/majors", options), {}, isMajorListData);
}

export async function getMajor(majorId: number): Promise<Major> {
  return apiRequest<Major>(`/majors/${encodeURIComponent(majorId)}`, {}, isMajor);
}

export async function searchMajors(query: string, topK = 10): Promise<MajorSearchData> {
  return apiRequest<MajorSearchData>(
    withQuery("/majors/search", { query, top_k: topK }),
    {},
    isMajorSearchData
  );
}

export async function getSkills(options: SkillListOptions = {}): Promise<SkillListData> {
  return apiRequest<SkillListData>(withQuery("/skills", options), {}, isSkillListData);
}

export async function getSkill(skillId: number): Promise<Skill> {
  return apiRequest<Skill>(`/skills/${encodeURIComponent(skillId)}`, {}, isSkill);
}

export async function getSkillCategories(): Promise<string[]> {
  const data = await apiRequest<SkillCategoriesData>(
    "/skills/categories",
    {},
    isSkillCategoriesData
  );
  return data.categories;
}

type ResponseDataValidator<T> = (value: unknown) => value is T;

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  validate: ResponseDataValidator<T>
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${normalizePath(path)}`, {
      ...init,
      headers,
    });
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? `Network request failed: ${error.message}` : "Network request failed"
    );
  }

  const payload = await parseResponse(response);
  if (!response.ok || payload.code !== 0) {
    throw new ApiError(payload.message || `Request failed with status ${response.status}`, {
      status: response.status,
      code: payload.code,
      data: payload.data,
    });
  }
  if (!validate(payload.data)) {
    throw new ApiError("Server returned data that does not match the API contract", {
      status: response.status,
      code: response.status,
      data: payload.data,
    });
  }
  return payload.data;
}

type QueryValue = string | number | boolean | null | undefined;

function withQuery<T extends object>(path: string, params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const queryValue = value as QueryValue;
    if (queryValue !== undefined && queryValue !== null && queryValue !== "") {
      search.set(key, String(queryValue));
    }
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function normalizePath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

async function parseResponse(response: Response): Promise<ApiResponse<unknown>> {
  try {
    const payload: unknown = await response.json();
    if (
      !isRecord(payload) ||
      typeof payload.code !== "number" ||
      typeof payload.message !== "string" ||
      !("data" in payload)
    ) {
      throw new Error("invalid envelope");
    }
    return {
      code: payload.code,
      data: payload.data,
      message: payload.message,
    };
  } catch {
    throw new ApiError("Server returned an invalid JSON response", {
      status: response.status,
      code: response.status,
    });
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isMatchRecommendation(value: unknown): value is MatchRecommendation {
  return (
    isRecord(value) &&
    typeof value.rank === "number" &&
    (value.major_id === null || typeof value.major_id === "number") &&
    typeof value.major_name === "string" &&
    (value.major_code === null || typeof value.major_code === "string") &&
    typeof value.final_score === "number" &&
    typeof value.skill_similarity_score === "number" &&
    typeof value.skill_coverage_score === "number" &&
    typeof value.employment_alignment_score === "number" &&
    isStringArray(value.matched_skills) &&
    isStringArray(value.missing_skills) &&
    typeof value.recommendation_reason === "string" &&
    isRecord(value.score_details)
  );
}

function isMatchResponseData(value: unknown): value is MatchResponseData {
  return (
    isRecord(value) &&
    typeof value.extracted_skill_count === "number" &&
    typeof value.persisted_count === "number" &&
    typeof value.already_processed === "boolean" &&
    Array.isArray(value.recommendations) &&
    value.recommendations.every(isMatchRecommendation)
  );
}

function isMatchHistoryData(value: unknown): value is MatchHistoryData {
  return (
    isRecord(value) &&
    typeof value.jd_id === "number" &&
    Array.isArray(value.recommendations) &&
    value.recommendations.every(isMatchRecommendation)
  );
}

function isJdSkill(value: unknown): value is JdSkill {
  return isRecord(value) && typeof value.id === "number" && typeof value.name === "string";
}

function isJdDetail(value: unknown): value is JdDetail {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    typeof value.raw_text === "string" &&
    Array.isArray(value.skills) &&
    value.skills.every(isJdSkill)
  );
}

function isJdListData(value: unknown): value is JdListData {
  return (
    isRecord(value) &&
    typeof value.total === "number" &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.id === "number" &&
        typeof item.raw_text === "string" &&
        typeof item.skill_count === "number"
    )
  );
}

function isJdTrendPoint(value: unknown): value is JdTrendPoint {
  return isRecord(value) && typeof value.date === "string" && typeof value.count === "number";
}

function isJdTrendData(value: unknown): value is JdTrendData {
  return (
    isRecord(value) &&
    typeof value.days === "number" &&
    typeof value.total === "number" &&
    Array.isArray(value.points) &&
    value.points.every(isJdTrendPoint)
  );
}

function isJobMarketTrendPoint(value: unknown): value is JobMarketTrendPoint {
  return isRecord(value) && typeof value.year === "number" && typeof value.count === "number";
}

function isJobMarketTrendData(value: unknown): value is JobMarketTrendData {
  return (
    isRecord(value) &&
    typeof value.keyword === "string" &&
    typeof value.years === "number" &&
    typeof value.total === "number" &&
    typeof value.data_source === "string" &&
    (value.source_url === null || typeof value.source_url === "string") &&
    Array.isArray(value.points) &&
    value.points.every(isJobMarketTrendPoint)
  );
}

function isJdFetchData(value: unknown): value is JdFetchData {
  return (
    isRecord(value) &&
    typeof value.keyword === "string" &&
    typeof value.jd_text === "string" &&
    (value.title === null || typeof value.title === "string") &&
    (value.company === null || typeof value.company === "string") &&
    (value.source_url === null || typeof value.source_url === "string") &&
    (value.source_domain === null || typeof value.source_domain === "string") &&
    isStringArray(value.inspected_urls) &&
    typeof value.from_cache === "boolean"
  );
}

function isMajor(value: unknown): value is Major {
  return isRecord(value) && typeof value.id === "number" && typeof value.name === "string";
}

function isMajorListData(value: unknown): value is MajorListData {
  return (
    isRecord(value) &&
    typeof value.total === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isMajor)
  );
}

function isMajorSearchData(value: unknown): value is MajorSearchData {
  return (
    isRecord(value) &&
    typeof value.query === "string" &&
    Array.isArray(value.results) &&
    value.results.every(
      (item) => isRecord(item) && isMajor(item) && typeof item.similarity_score === "number"
    )
  );
}

function isSkillSummary(value: unknown): value is SkillSummary {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    typeof value.name === "string" &&
    typeof value.normalized_name === "string"
  );
}

function isSkill(value: unknown): value is Skill {
  return isSkillSummary(value) && "embedding" in value;
}

function isSkillListData(value: unknown): value is SkillListData {
  return (
    isRecord(value) &&
    typeof value.total === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isSkillSummary)
  );
}

function isSkillCategoriesData(value: unknown): value is SkillCategoriesData {
  return isRecord(value) && isStringArray(value.categories);
}
