export type SimulationType = "aerodynamics" | "fluid_dynamics" | "structural" | "thermodynamics" | "robotics" | string;
export interface ValidateOptions {
    simulationType?: SimulationType;
    conditions?: Record<string, number>;
    jobId?: string;
    runAi?: boolean;
}
export interface ValidationIssue {
    name: string;
    status: string;
    detail: string;
    category?: string;
}
export interface ValidationResult {
    job_id: string;
    status: "passed" | "warning" | "failed";
    confidence: "high" | "medium" | "low";
    trials_submitted: number;
    trials_valid: number;
    trials_excluded: number;
    training_ready: boolean;
    all_checks: number;
    passed: number;
    warnings: number;
    failed: number;
    issues: ValidationIssue[];
    processing_ms: number;
    ai_status: string;
    [key: string]: unknown;
}
export declare class SimAPIError extends Error {
    code: string;
    status: number;
    requestId?: string;
    constructor(message: string, code: string, status: number, requestId?: string);
}
export interface SimAPIConfig {
    apiKey?: string;
    baseUrl?: string;
    timeoutMs?: number;
}
export declare class SimAPI {
    private apiKey?;
    private baseUrl;
    private timeoutMs;
    constructor(apiKeyOrConfig?: string | SimAPIConfig);
    /** Validate an array of trial records. */
    validate(data: Record<string, unknown>[], options?: ValidateOptions): Promise<ValidationResult>;
    /** Validate a JSON file of trial records on disk. */
    validateFile(path: string, options?: ValidateOptions): Promise<ValidationResult>;
    /** Fetch a previously computed job by id. */
    getJob(jobId: string): Promise<ValidationResult>;
    /** Server health and facts. */
    health(): Promise<Record<string, unknown>>;
    private request;
}
export default SimAPI;
