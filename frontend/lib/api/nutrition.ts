import { apiRequest } from "./client";
import type { NutritionSearchResponse } from "./types";

export const nutritionApi = {
  /**
   * Look up nutrition data for a brand + menu item.
   * The backend handles multi-tier search (MFDS → SerpAPI → LLM estimate)
   * and holds all third-party API keys — none are exposed to the frontend.
   */
  search: (brand: string, menu: string): Promise<NutritionSearchResponse> =>
    apiRequest<NutritionSearchResponse>("POST", "/api/v1/nutrition/search", {
      brand,
      menu,
    }),
};
