import { apiUpload, apiRequest } from "./client";
import type { JobStatusResponse, MealCreate } from "./types";

export interface AnalyzeImageParams {
  file: File;
  meal_type: MealCreate["meal_type"];
  date: string; // YYYY-MM-DD
  meal_time?: string; // HH:MM
}

export interface SubmitImageResponse {
  job_id: string;
  status: string;
}

export const analyzeApi = {
  /**
   * Upload an image to the backend for async nutrition analysis.
   * Returns a job_id to poll with pollJob().
   */
  submitImage: ({
    file,
    meal_type,
    date,
    meal_time,
  }: AnalyzeImageParams): Promise<SubmitImageResponse> => {
    const form = new FormData();
    form.append("file", file);
    form.append("meal_type", meal_type);
    form.append("date", date);
    if (meal_time) form.append("meal_time", meal_time);
    return apiUpload<SubmitImageResponse>("/api/v1/analyze/image", form);
  },

  /**
   * Poll a job by ID. Call repeatedly (e.g. every 2 s) until
   * status is "done" or "failed".
   */
  pollJob: (jobId: string): Promise<JobStatusResponse> =>
    apiRequest<JobStatusResponse>("GET", `/api/v1/analyze/jobs/${jobId}`),
};
