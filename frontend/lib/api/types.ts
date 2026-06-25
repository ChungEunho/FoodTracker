export interface FoodItem {
  name: string;
  weight_g: number;
  calories_kcal: number;
  carbs_g: number;
  protein_g: number;
  fat_g: number;
  sugar_g?: number;
}

export interface NutritionTotals {
  weight_g: number;
  calories_kcal: number;
  carbs_g: number;
  protein_g: number;
  fat_g: number;
  sugar_g?: number;
}

export interface MealCreate {
  date: string; // YYYY-MM-DD
  meal_type: "아침" | "점심" | "저녁" | "간식";
  meal_time?: string; // HH:MM, optional
  image_path?: string; // Supabase Storage URL, optional
  items_json: FoodItem[];
  total_json: NutritionTotals;
}

export interface MealOut extends MealCreate {
  id: number;
  user_id: string;
  created_at: string;
}

export type JobStatus = "pending" | "running" | "done" | "failed";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  result?: {
    meal_id: number;
    items: FoodItem[];
    total: NutritionTotals;
    image_url: string;
  };
  error?: string;
  created_at: string;
}

export interface NutritionSearchResponse {
  result: { items: FoodItem[]; total: NutritionTotals };
  found_name: string;
  is_exact: boolean;
  rate_limit: RateLimitInfo;
}

export interface RateLimitInfo {
  calls_today: number;
  limit: number;
  remaining: number;
  resets_at_utc: string;
}
