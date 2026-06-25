"use client";

import { useState } from "react";
import { mealsApi } from "@/lib/api/meals";
import type { MealOut } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

interface DaySummary {
  date: string;
  calories_kcal: number;
  carbs_g: number;
  protein_g: number;
  fat_g: number;
  meal_count: number;
}

function fmt1(n: number): string {
  return Number.isFinite(n) ? n.toFixed(1) : "-";
}

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

function buildDaySummary(date: string, meals: MealOut[]): DaySummary | null {
  if (meals.length === 0) return null;
  const totals = meals.reduce(
    (acc, m) => ({
      calories_kcal: acc.calories_kcal + (m.total_json?.calories_kcal ?? 0),
      carbs_g: acc.carbs_g + (m.total_json?.carbs_g ?? 0),
      protein_g: acc.protein_g + (m.total_json?.protein_g ?? 0),
      fat_g: acc.fat_g + (m.total_json?.fat_g ?? 0),
    }),
    { calories_kcal: 0, carbs_g: 0, protein_g: 0, fat_g: 0 },
  );
  return { date, ...totals, meal_count: meals.length };
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
  textAlign: "right",
  borderBottom: "1px solid #e5e7eb",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 13,
  color: "#111827",
  textAlign: "right",
  borderBottom: "1px solid #f3f4f6",
};

const tdTotalStyle: React.CSSProperties = {
  ...tdStyle,
  fontWeight: 700,
  color: "#1e40af",
  background: "#eff6ff",
  borderTop: "2px solid #bfdbfe",
  borderBottom: "none",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SummaryPage() {
  const today = new Date().toISOString().slice(0, 10);
  const sevenDaysAgo = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);

  const [fromDate, setFromDate] = useState(sevenDaysAgo);
  const [toDate, setToDate] = useState(today);
  const [summaries, setSummaries] = useState<DaySummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFetch() {
    if (!fromDate || !toDate) return;
    if (fromDate > toDate) {
      setError("시작일이 종료일보다 늦을 수 없습니다.");
      return;
    }

    const dates = getDatesInRange(fromDate, toDate);
    if (dates.length > 31) {
      setError("최대 31일 범위까지 조회할 수 있습니다.");
      return;
    }

    setLoading(true);
    setError(null);
    setSummaries(null);

    try {
      const results = await Promise.all(dates.map((d) => mealsApi.listDaily(d)));
      const built: DaySummary[] = [];
      results.forEach((meals, idx) => {
        const summary = buildDaySummary(dates[idx], meals);
        if (summary) built.push(summary);
      });
      setSummaries(built);
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  // Compute average
  const average: DaySummary | null =
    summaries && summaries.length > 0
      ? {
          date: "평균",
          calories_kcal:
            summaries.reduce((s, d) => s + d.calories_kcal, 0) / summaries.length,
          carbs_g: summaries.reduce((s, d) => s + d.carbs_g, 0) / summaries.length,
          protein_g: summaries.reduce((s, d) => s + d.protein_g, 0) / summaries.length,
          fat_g: summaries.reduce((s, d) => s + d.fat_g, 0) / summaries.length,
          meal_count:
            summaries.reduce((s, d) => s + d.meal_count, 0) / summaries.length,
        }
      : null;

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", marginBottom: 20 }}>
        기간 요약
      </h1>

      {/* Date range selector */}
      <div style={{ ...card, display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
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
          onClick={handleFetch}
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

      {/* Empty state */}
      {!loading && summaries !== null && summaries.length === 0 && (
        <div
          style={{
            ...card,
            textAlign: "center",
            color: "#6b7280",
            fontSize: 14,
            padding: 40,
          }}
        >
          선택한 기간에 기록된 식사가 없습니다.
        </div>
      )}

      {/* Summary table */}
      {summaries !== null && summaries.length > 0 && (
        <div style={card}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "#111827", margin: "0 0 16px" }}>
            일별 영양 요약
          </h2>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 500 }}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: "left" }}>날짜</th>
                  <th style={thStyle}>칼로리(kcal)</th>
                  <th style={thStyle}>탄수(g)</th>
                  <th style={thStyle}>단백(g)</th>
                  <th style={thStyle}>지방(g)</th>
                  <th style={thStyle}>식사 수</th>
                </tr>
              </thead>
              <tbody>
                {summaries.map((row) => (
                  <tr key={row.date}>
                    <td style={{ ...tdStyle, textAlign: "left" }}>{row.date}</td>
                    <td style={tdStyle}>{fmt1(row.calories_kcal)}</td>
                    <td style={tdStyle}>{fmt1(row.carbs_g)}</td>
                    <td style={tdStyle}>{fmt1(row.protein_g)}</td>
                    <td style={tdStyle}>{fmt1(row.fat_g)}</td>
                    <td style={tdStyle}>{row.meal_count}</td>
                  </tr>
                ))}
                {average && (
                  <tr>
                    <td style={{ ...tdTotalStyle, textAlign: "left" }}>평균</td>
                    <td style={tdTotalStyle}>{fmt1(average.calories_kcal)}</td>
                    <td style={tdTotalStyle}>{fmt1(average.carbs_g)}</td>
                    <td style={tdTotalStyle}>{fmt1(average.protein_g)}</td>
                    <td style={tdTotalStyle}>{fmt1(average.fat_g)}</td>
                    <td style={tdTotalStyle}>{fmt1(average.meal_count)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
