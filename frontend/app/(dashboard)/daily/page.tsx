"use client";

import { useState, useCallback } from "react";
import NutritionTable from "@/components/NutritionTable";
import { mealsApi } from "@/lib/api/meals";
import type { MealOut, NutritionTotals } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type MealType = "아침" | "점심" | "저녁" | "간식";

const MEAL_TYPE_ORDER: MealType[] = ["아침", "점심", "저녁", "간식"];

const MEAL_TYPE_EMOJI: Record<MealType, string> = {
  아침: "🌅",
  점심: "☀️",
  저녁: "🌙",
  간식: "🍎",
};

function sumTotals(meals: MealOut[]): NutritionTotals {
  return meals.reduce(
    (acc, m) => ({
      weight_g: acc.weight_g + (m.total_json?.weight_g ?? 0),
      calories_kcal: acc.calories_kcal + (m.total_json?.calories_kcal ?? 0),
      carbs_g: acc.carbs_g + (m.total_json?.carbs_g ?? 0),
      protein_g: acc.protein_g + (m.total_json?.protein_g ?? 0),
      fat_g: acc.fat_g + (m.total_json?.fat_g ?? 0),
    }),
    { weight_g: 0, calories_kcal: 0, carbs_g: 0, protein_g: 0, fat_g: 0 },
  );
}

function fmt1(n: number): string {
  return Number.isFinite(n) ? n.toFixed(1) : "-";
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

const card: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  padding: 20,
  marginBottom: 16,
};

const inputStyle: React.CSSProperties = {
  height: 36,
  padding: "0 10px",
  border: "1px solid #e5e7eb",
  borderRadius: 6,
  fontSize: 14,
  color: "#111827",
  outline: "none",
};

const btnPrimary: React.CSSProperties = {
  height: 36,
  padding: "0 16px",
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  fontSize: 14,
  fontWeight: 500,
  cursor: "pointer",
};

const btnDanger: React.CSSProperties = {
  height: 28,
  padding: "0 10px",
  background: "none",
  color: "#ef4444",
  border: "1px solid #fecaca",
  borderRadius: 6,
  fontSize: 13,
  cursor: "pointer",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DailyPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [meals, setMeals] = useState<MealOut[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMeals = useCallback(async (d: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await mealsApi.listDaily(d);
      setMeals(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오는 중 오류가 발생했습니다.");
      setMeals(null);
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleDelete(id: number) {
    try {
      await mealsApi.delete(id);
      setMeals((prev) => prev?.filter((m) => m.id !== id) ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 중 오류가 발생했습니다.");
    }
  }

  // Group meals by meal_type in canonical order
  const grouped: Record<string, MealOut[]> = {};
  if (meals) {
    for (const meal of meals) {
      if (!grouped[meal.meal_type]) grouped[meal.meal_type] = [];
      grouped[meal.meal_type].push(meal);
    }
  }

  const dailyTotal = meals && meals.length > 0 ? sumTotals(meals) : null;

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", marginBottom: 20 }}>
        일별 조회
      </h1>

      {/* Date selector */}
      <div style={{ ...card, display: "flex", gap: 12, alignItems: "flex-end" }}>
        <div>
          <label
            style={{
              display: "block",
              fontSize: 13,
              fontWeight: 500,
              color: "#374151",
              marginBottom: 6,
            }}
          >
            날짜
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchMeals(date)}
            style={{ ...inputStyle, width: 160 }}
          />
        </div>
        <button onClick={() => fetchMeals(date)} style={btnPrimary}>
          조회
        </button>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            ...card,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#ef4444",
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#6b7280", fontSize: 14 }}>
          불러오는 중…
        </div>
      )}

      {/* Empty state */}
      {!loading && meals !== null && meals.length === 0 && (
        <div
          style={{
            ...card,
            textAlign: "center",
            color: "#6b7280",
            fontSize: 14,
            padding: 40,
          }}
        >
          선택한 날짜에 기록된 식사가 없습니다.
        </div>
      )}

      {/* Meal groups */}
      {!loading &&
        meals !== null &&
        MEAL_TYPE_ORDER.filter((mt) => grouped[mt]).map((mt) => {
          const group = grouped[mt];
          const groupTotal = sumTotals(group);

          return (
            <div key={mt} style={card}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 14,
                }}
              >
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#111827" }}>
                  {MEAL_TYPE_EMOJI[mt]} {mt}{" "}
                  <span style={{ fontWeight: 400, color: "#6b7280", fontSize: 14 }}>
                    ({group.reduce((n, m) => n + m.items_json.length, 0)}가지 음식)
                  </span>
                </h2>
              </div>

              {group.map((meal) => (
                <div
                  key={meal.id}
                  style={{
                    marginBottom: 16,
                    paddingBottom: 16,
                    borderBottom: "1px solid #f3f4f6",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 8,
                    }}
                  >
                    <span style={{ fontSize: 13, color: "#6b7280" }}>
                      {meal.meal_time ? `${meal.meal_time} 기록` : "시간 미기록"}
                    </span>
                    <button
                      onClick={() => handleDelete(meal.id)}
                      style={btnDanger}
                      aria-label="식사 기록 삭제"
                    >
                      삭제
                    </button>
                  </div>
                  <NutritionTable items={meal.items_json} />
                </div>
              ))}

              {/* Group subtotal */}
              <div
                style={{
                  display: "flex",
                  gap: 20,
                  background: "#f9fafb",
                  borderRadius: 6,
                  padding: "10px 14px",
                  fontSize: 13,
                }}
              >
                <span style={{ color: "#6b7280" }}>소계</span>
                <span>
                  칼로리 <strong>{fmt1(groupTotal.calories_kcal)} kcal</strong>
                </span>
                <span>
                  탄수 <strong>{fmt1(groupTotal.carbs_g)} g</strong>
                </span>
                <span>
                  단백 <strong>{fmt1(groupTotal.protein_g)} g</strong>
                </span>
                <span>
                  지방 <strong>{fmt1(groupTotal.fat_g)} g</strong>
                </span>
              </div>
            </div>
          );
        })}

      {/* Daily total */}
      {dailyTotal && !loading && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 8,
            padding: 20,
          }}
        >
          <h2
            style={{
              margin: "0 0 14px",
              fontSize: 16,
              fontWeight: 700,
              color: "#1e40af",
            }}
          >
            하루 합계
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: 12,
            }}
          >
            {[
              { label: "칼로리", value: `${fmt1(dailyTotal.calories_kcal)} kcal` },
              { label: "탄수화물", value: `${fmt1(dailyTotal.carbs_g)} g` },
              { label: "단백질", value: `${fmt1(dailyTotal.protein_g)} g` },
              { label: "지방", value: `${fmt1(dailyTotal.fat_g)} g` },
            ].map(({ label, value }) => (
              <div
                key={label}
                style={{
                  background: "#fff",
                  borderRadius: 6,
                  padding: "12px 16px",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#1e40af" }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
