import { apiRequest } from "./client";
import type { MealCreate, MealOut } from "./types";

export const mealsApi = {
  create: (body: MealCreate) =>
    apiRequest<MealOut>("POST", "/api/v1/meals/", body),

  listDaily: (date: string) =>
    apiRequest<MealOut[]>("GET", `/api/v1/meals/daily?date=${date}`),

  delete: (id: number) => apiRequest<void>("DELETE", `/api/v1/meals/${id}`),
};
