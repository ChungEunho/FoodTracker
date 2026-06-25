"use client";

import { useState, useEffect, useCallback } from "react";
import { mealsApi } from "@/lib/api/meals";
import type { MealOut } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type MealType = "아침" | "점심" | "저녁" | "간식";

const MEAL_TYPE_ORDER: Record<MealType, number> = {
  아침: 0,
  점심: 1,
  저녁: 2,
  간식: 3,
};

function getDatesInRange(from: string, to: string): string[] {
  const dates: string[] = [];
  const current = new Date(from);
  const end = new Date(to);
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

function sortMeals(meals: MealOut[]): MealOut[] {
  return [...meals].sort((a, b) => {
    if (b.date !== a.date) return b.date.localeCompare(a.date); // date desc
    const aOrder = MEAL_TYPE_ORDER[a.meal_type as MealType] ?? 99;
    const bOrder = MEAL_TYPE_ORDER[b.meal_type as MealType] ?? 99;
    return aOrder - bOrder;
  });
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

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 500,
  color: "#374151",
  marginBottom: 6,
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

const btnDisabled: React.CSSProperties = {
  ...btnPrimary,
  background: "#93c5fd",
  cursor: "not-allowed",
};

const thStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 13,
  fontWeight: 600,
  color: "#374151",
  background: "#f9fafb",
  textAlign: "left",
  borderBottom: "1px solid #e5e7eb",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 13,
  color: "#111827",
  borderBottom: "1px solid #f3f4f6",
  verticalAlign: "middle",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RecordsPage() {
  const today = new Date().toISOString().slice(0, 10);

  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [meals, setMeals] = useState<MealOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRange = useCallback(async (from: string, to: string) => {
    if (from > to) {
      setError("시작일이 종료일보다 늦을 수 없습니다.");
      return;
    }
    const dates = getDatesInRange(from, to);
    if (dates.length > 31) {
      setError("최대 31일 범위까지 조회할 수 있습니다.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const results = await Promise.all(dates.map((d) => mealsApi.listDaily(d)));
      const all = results.flat();
      setMeals(sortMeals(all));
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load today's meals on mount
  useEffect(() => {
    fetchRange(today, today);
  }, [fetchRange, today]);

  async function handleDelete(id: number) {
    try {
      await mealsApi.delete(id);
      setMeals((prev) => prev.filter((m) => m.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 중 오류가 발생했습니다.");
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", marginBottom: 20 }}>
        기록 관리
      </h1>

      {/* Date range filter */}
      <div
        style={{
          ...card,
          display: "flex",
          gap: 16,
          alignItems: "flex-end",
          flexWrap: "wrap",
        }}
      >
        <div>
          <label style={labelStyle}>시작일</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            style={{ ...inputStyle, width: 160 }}
          />
        </div>
        <div>
          <label style={labelStyle}>종료일</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            style={{ ...inputStyle, width: 160 }}
          />
        </div>
        <button
          onClick={() => fetchRange(fromDate, toDate)}
          disabled={loading}
          style={loading ? btnDisabled : btnPrimary}
        >
          {loading ? "조회 중…" : "조회"}
        </button>
        <span style={{ fontSize: 13, color: "#6b7280", alignSelf: "center" }}>
          최대 31일 범위
        </span>
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

      {/* Records table */}
      <div style={card}>
        {loading && (
          <div style={{ textAlign: "center", padding: 40, color: "#6b7280", fontSize: 14 }}>
            불러오는 중…
          </div>
        )}

        {!loading && meals.length === 0 && (
          <div
            style={{ textAlign: "center", padding: 40, color: "#6b7280", fontSize: 14 }}
          >
            기록이 없습니다.
          </div>
        )}

        {!loading && meals.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 600 }}>
              <thead>
                <tr>
                  <th style={thStyle}>날짜</th>
                  <th style={thStyle}>식사유형</th>
                  <th style={{ ...thStyle, width: "40%" }}>음식 목록</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>칼로리(kcal)</th>
                  <th style={{ ...thStyle, textAlign: "center" }}>삭제</th>
                </tr>
              </thead>
              <tbody>
                {meals.map((meal) => (
                  <tr
                    key={meal.id}
                    style={{ transition: "background 0.1s" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.background = "#f9fafb";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.background = "";
                    }}
                  >
                    <td style={tdStyle}>{meal.date}</td>
                    <td style={tdStyle}>{meal.meal_type}</td>
                    <td
                      style={{
                        ...tdStyle,
                        color: "#6b7280",
                        maxWidth: 300,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={meal.items_json.map((i) => i.name).join(", ")}
                    >
                      {meal.items_json.map((i) => i.name).join(", ")}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {fmt1(meal.total_json?.calories_kcal ?? 0)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>
                      <button
                        onClick={() => handleDelete(meal.id)}
                        aria-label={`${meal.date} ${meal.meal_type} 기록 삭제`}
                        style={{
                          background: "none",
                          border: "1px solid #fecaca",
                          borderRadius: 4,
                          color: "#ef4444",
                          fontSize: 13,
                          padding: "2px 8px",
                          cursor: "pointer",
                        }}
                      >
                        삭제
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && meals.length > 0 && (
          <p style={{ fontSize: 13, color: "#6b7280", margin: "12px 0 0" }}>
            총 {meals.length}건
          </p>
        )}
      </div>
    </div>
  );
}
