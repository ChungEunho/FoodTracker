"use client";

import { useState, useEffect, useRef } from "react";
import NutritionTable from "@/components/NutritionTable";
import { analyzeApi } from "@/lib/api/analyze";
import { mealsApi } from "@/lib/api/meals";
import { nutritionApi } from "@/lib/api/nutrition";
import { RateLimitError } from "@/lib/api/client";
import type { FoodItem, NutritionTotals, MealCreate } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MealType = "아침" | "점심" | "저녁" | "간식";
type SubTab = "이미지 분석" | "브랜드·메뉴 검색" | "수동 입력";
type AnalysisPhase = "idle" | "uploading" | "polling" | "done" | "failed";
type SearchPhase = "idle" | "loading" | "done" | "error" | "notfound";

// ---------------------------------------------------------------------------
// Helper: compute totals from item array
// ---------------------------------------------------------------------------

function computeTotal(items: FoodItem[]): NutritionTotals {
  return items.reduce(
    (acc, item) => ({
      weight_g: acc.weight_g + item.weight_g,
      calories_kcal: acc.calories_kcal + item.calories_kcal,
      carbs_g: acc.carbs_g + item.carbs_g,
      protein_g: acc.protein_g + item.protein_g,
      fat_g: acc.fat_g + item.fat_g,
    }),
    { weight_g: 0, calories_kcal: 0, carbs_g: 0, protein_g: 0, fat_g: 0 },
  );
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

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 500,
  color: "#374151",
  marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  height: 36,
  padding: "0 10px",
  border: "1px solid #e5e7eb",
  borderRadius: 6,
  fontSize: 14,
  color: "#111827",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
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

const btnDanger: React.CSSProperties = {
  ...btnPrimary,
  background: "#ef4444",
};

const subTabBtn = (active: boolean): React.CSSProperties => ({
  padding: "8px 16px",
  fontSize: 14,
  fontWeight: active ? 600 : 400,
  color: active ? "#2563eb" : "#374151",
  background: "none",
  border: "none",
  borderBottom: active ? "2px solid #2563eb" : "2px solid transparent",
  cursor: "pointer",
});

function Spinner() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 18,
        height: 18,
        border: "2px solid #e5e7eb",
        borderTop: "2px solid #2563eb",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
        verticalAlign: "middle",
        marginRight: 8,
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Sub-tab A: 이미지 분석
// ---------------------------------------------------------------------------

interface ImageAnalysisTabProps {
  mealType: MealType;
  date: string;
  mealTime: string;
}

const MAX_POLL_ATTEMPTS = 30; // 30 × 2s = 60s timeout

function ImageAnalysisTab({ mealType, date, mealTime }: ImageAnalysisTabProps) {
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<AnalysisPhase>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<{
    items: FoodItem[];
    total: NutritionTotals;
  } | null>(null);
  const pollAttemptsRef = useRef(0);

  // Polling effect
  useEffect(() => {
    if (phase !== "polling" || !jobId) return;
    pollAttemptsRef.current = 0;

    const timer = setInterval(async () => {
      pollAttemptsRef.current += 1;

      if (pollAttemptsRef.current > MAX_POLL_ATTEMPTS) {
        clearInterval(timer);
        setError("분석 시간이 초과됐습니다 (60초). 다시 시도해주세요.");
        setPhase("failed");
        return;
      }

      try {
        const job = await analyzeApi.pollJob(jobId);
        if (job.status === "done" && job.result) {
          setAnalysisResult({
            items: job.result.items,
            total: job.result.total,
          });
          setPhase("done");
        } else if (job.status === "failed") {
          setError(job.error ?? "분석 중 오류가 발생했습니다.");
          setPhase("failed");
        }
      } catch (e) {
        if (e instanceof RateLimitError) {
          setError(
            `오늘 OpenRouter 요청 한도(50회)를 소진했습니다. ${e.resets_at_utc} 이후 초기화됩니다.`,
          );
        } else {
          setError(e instanceof Error ? e.message : "폴링 오류가 발생했습니다.");
        }
        setPhase("failed");
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [phase, jobId]);

  async function handleSubmit() {
    if (!file) return;
    setError(null);
    setPhase("uploading");

    try {
      const res = await analyzeApi.submitImage({
        file,
        meal_type: mealType,
        date,
        meal_time: mealTime || undefined,
      });
      setJobId(res.job_id);
      setPhase("polling");
    } catch (e) {
      if (e instanceof RateLimitError) {
        setError(
          `오늘 OpenRouter 요청 한도(50회)를 소진했습니다. ${e.resets_at_utc} 이후 초기화됩니다.`,
        );
      } else {
        setError(e instanceof Error ? e.message : "업로드 중 오류가 발생했습니다.");
      }
      setPhase("failed");
    }
  }

  function handleReset() {
    setFile(null);
    setPhase("idle");
    setJobId(null);
    setError(null);
    setAnalysisResult(null);
    pollAttemptsRef.current = 0;
  }

  return (
    <div>
      {(phase === "idle" || phase === "failed") && (
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>이미지 파일 선택</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              if (phase === "failed") {
                setPhase("idle");
                setError(null);
              }
            }}
            style={{ ...inputStyle, height: "auto", padding: "6px 10px" }}
          />
          {file && (
            <p style={{ fontSize: 13, color: "#6b7280", marginTop: 6 }}>
              선택된 파일: {file.name}
            </p>
          )}
        </div>
      )}

      {phase === "idle" && (
        <button
          onClick={handleSubmit}
          disabled={!file}
          style={file ? btnPrimary : btnDisabled}
        >
          분석 시작
        </button>
      )}

      {phase === "uploading" && (
        <p style={{ fontSize: 14, color: "#6b7280" }}>
          <Spinner />
          이미지 업로드 중…
        </p>
      )}

      {phase === "polling" && (
        <p style={{ fontSize: 14, color: "#6b7280" }}>
          <Spinner />
          AI 분석 중… (최대 60초 소요)
        </p>
      )}

      {phase === "done" && analysisResult && (
        <div>
          <div
            style={{
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 16,
              fontSize: 14,
              color: "#16a34a",
            }}
          >
            저장 완료 (식사 기록에 저장됐습니다.)
          </div>
          <NutritionTable items={analysisResult.items} total={analysisResult.total} />
          <button onClick={handleReset} style={{ ...btnPrimary, marginTop: 16 }}>
            새로 분석하기
          </button>
        </div>
      )}

      {phase === "failed" && (
        <div>
          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 16,
              fontSize: 14,
              color: "#ef4444",
            }}
          >
            {error || "분석 중 오류가 발생했습니다. 다시 시도해주세요."}
          </div>
          <button onClick={handleReset} style={btnPrimary}>
            다시 시도
          </button>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-tab B: 브랜드·메뉴 검색
// ---------------------------------------------------------------------------

interface BrandSearchTabProps {
  mealType: MealType;
  date: string;
  mealTime: string;
}

function BrandSearchTab({ mealType, date, mealTime }: BrandSearchTabProps) {
  const [brand, setBrand] = useState("");
  const [menu, setMenu] = useState("");
  const [phase, setPhase] = useState<SearchPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<{
    items: FoodItem[];
    total: NutritionTotals;
    remainingCalls?: number;
    resetsAt?: string;
  } | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSearch() {
    if (!brand.trim() && !menu.trim()) return;
    setPhase("loading");
    setError(null);
    setSaved(false);
    setSearchResult(null);

    try {
      const res = await nutritionApi.search(brand.trim(), menu.trim());
      if (!res.result || res.result.items.length === 0) {
        setPhase("notfound");
        return;
      }
      setSearchResult({
        items: res.result.items,
        total: res.result.total,
        remainingCalls: res.rate_limit?.remaining,
        resetsAt: res.rate_limit?.resets_at_utc,
      });
      setPhase("done");
    } catch (e) {
      if (e instanceof RateLimitError) {
        setError(
          `오늘 OpenRouter 요청 한도(50회)를 소진했습니다. ${e.resets_at_utc} 이후 초기화됩니다.`,
        );
      } else {
        setError(e instanceof Error ? e.message : "검색 중 오류가 발생했습니다.");
      }
      setPhase("error");
    }
  }

  async function handleSave() {
    if (!searchResult) return;
    try {
      const body: MealCreate = {
        date,
        meal_type: mealType,
        meal_time: mealTime || undefined,
        items_json: searchResult.items,
        total_json: searchResult.total,
      };
      await mealsApi.create(body);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 중 오류가 발생했습니다.");
    }
  }

  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div>
          <label style={labelStyle}>브랜드명</label>
          <input
            type="text"
            placeholder="예: 스타벅스"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            style={inputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>메뉴명</label>
          <input
            type="text"
            placeholder="예: 아이스 아메리카노 그란데"
            value={menu}
            onChange={(e) => setMenu(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            style={inputStyle}
          />
        </div>
      </div>

      <button
        onClick={handleSearch}
        disabled={phase === "loading"}
        style={phase === "loading" ? btnDisabled : btnPrimary}
      >
        {phase === "loading" ? (
          <>
            <Spinner />
            검색 중…
          </>
        ) : (
          "검색"
        )}
      </button>

      {phase === "notfound" && (
        <div
          style={{
            marginTop: 16,
            padding: "10px 14px",
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 6,
            fontSize: 14,
            color: "#d97706",
          }}
        >
          영양 정보를 찾을 수 없습니다. 브랜드명·메뉴명을 확인해주세요.
        </div>
      )}

      {phase === "error" && error && (
        <div
          style={{
            marginTop: 16,
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            fontSize: 14,
            color: "#ef4444",
          }}
        >
          {error}
        </div>
      )}

      {phase === "done" && searchResult && (
        <div style={{ marginTop: 16 }}>
          {typeof searchResult.remainingCalls === "number" &&
            searchResult.remainingCalls <= 5 && (
              <div
                style={{
                  padding: "8px 14px",
                  background: "#fffbeb",
                  border: "1px solid #fde68a",
                  borderRadius: 6,
                  fontSize: 13,
                  color: "#d97706",
                  marginBottom: 12,
                }}
              >
                오늘 AI 검색이 {searchResult.remainingCalls}회 남았습니다.
              </div>
            )}

          <NutritionTable items={searchResult.items} total={searchResult.total} />

          <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
            {!saved ? (
              <button onClick={handleSave} style={btnPrimary}>
                저장
              </button>
            ) : (
              <span
                style={{
                  fontSize: 14,
                  color: "#16a34a",
                  fontWeight: 500,
                }}
              >
                저장 완료
              </span>
            )}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-tab C: 수동 입력
// ---------------------------------------------------------------------------

interface ManualEntryTabProps {
  mealType: MealType;
  date: string;
  mealTime: string;
}

const emptyItem = (): Omit<FoodItem, "name"> & { name: string } => ({
  name: "",
  weight_g: 0,
  calories_kcal: 0,
  carbs_g: 0,
  protein_g: 0,
  fat_g: 0,
});

function ManualEntryTab({ mealType, date, mealTime }: ManualEntryTabProps) {
  const [items, setItems] = useState<FoodItem[]>([]);
  const [form, setForm] = useState(emptyItem());
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const total = computeTotal(items);

  function handleFormChange(field: keyof typeof form, value: string) {
    setForm((prev) => ({
      ...prev,
      [field]: field === "name" ? value : parseFloat(value) || 0,
    }));
  }

  function handleAdd() {
    if (!form.name.trim()) return;
    setItems((prev) => [...prev, { ...form }]);
    setForm(emptyItem());
    setSaved(false);
  }

  function handleDelete(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
    setSaved(false);
  }

  async function handleSave() {
    if (items.length === 0) return;
    setSaving(true);
    setError(null);

    try {
      const body: MealCreate = {
        date,
        meal_type: mealType,
        meal_time: mealTime || undefined,
        items_json: items,
        total_json: total,
      };
      await mealsApi.create(body);
      setSaved(true);
      setItems([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  }

  const numInputStyle: React.CSSProperties = { ...inputStyle, width: 90 };

  return (
    <div>
      {/* Add item form */}
      <div
        style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "flex-end",
          marginBottom: 16,
        }}
      >
        <div>
          <label style={labelStyle}>음식명</label>
          <input
            type="text"
            placeholder="예: 흰쌀밥"
            value={form.name}
            onChange={(e) => handleFormChange("name", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            style={{ ...inputStyle, width: 140 }}
          />
        </div>
        <div>
          <label style={labelStyle}>중량(g)</label>
          <input
            type="number"
            min={0}
            value={form.weight_g || ""}
            onChange={(e) => handleFormChange("weight_g", e.target.value)}
            style={numInputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>칼로리(kcal)</label>
          <input
            type="number"
            min={0}
            value={form.calories_kcal || ""}
            onChange={(e) => handleFormChange("calories_kcal", e.target.value)}
            style={numInputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>탄수(g)</label>
          <input
            type="number"
            min={0}
            value={form.carbs_g || ""}
            onChange={(e) => handleFormChange("carbs_g", e.target.value)}
            style={numInputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>단백(g)</label>
          <input
            type="number"
            min={0}
            value={form.protein_g || ""}
            onChange={(e) => handleFormChange("protein_g", e.target.value)}
            style={numInputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>지방(g)</label>
          <input
            type="number"
            min={0}
            value={form.fat_g || ""}
            onChange={(e) => handleFormChange("fat_g", e.target.value)}
            style={numInputStyle}
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={!form.name.trim()}
          style={form.name.trim() ? btnPrimary : btnDisabled}
        >
          + 추가
        </button>
      </div>

      {/* Item list */}
      {items.length > 0 && (
        <>
          <NutritionTable
            items={items}
            total={items.length > 0 ? total : undefined}
            showDelete
            onDelete={handleDelete}
          />

          <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
            <button
              onClick={handleSave}
              disabled={saving || items.length === 0}
              style={saving || items.length === 0 ? btnDisabled : btnPrimary}
            >
              {saving ? "저장 중…" : "저장"}
            </button>
            {saved && (
              <span style={{ fontSize: 14, color: "#16a34a", fontWeight: 500 }}>
                저장 완료
              </span>
            )}
          </div>
        </>
      )}

      {error && (
        <div
          style={{
            marginTop: 12,
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            fontSize: 14,
            color: "#ef4444",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page: 식사 기록
// ---------------------------------------------------------------------------

const SUB_TABS: SubTab[] = ["이미지 분석", "브랜드·메뉴 검색", "수동 입력"];

export default function LogPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("이미지 분석");
  const [mealType, setMealType] = useState<MealType>("점심");
  const [date, setDate] = useState(today);
  const [mealTime, setMealTime] = useState("");

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", marginBottom: 20 }}>
        식사 기록
      </h1>

      {/* Sub-tab bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid #e5e7eb",
          marginBottom: 20,
        }}
      >
        {SUB_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveSubTab(tab)}
            style={subTabBtn(activeSubTab === tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div style={card}>
        {activeSubTab === "이미지 분석" && (
          <ImageAnalysisTab mealType={mealType} date={date} mealTime={mealTime} />
        )}
        {activeSubTab === "브랜드·메뉴 검색" && (
          <BrandSearchTab mealType={mealType} date={date} mealTime={mealTime} />
        )}
        {activeSubTab === "수동 입력" && (
          <ManualEntryTab mealType={mealType} date={date} mealTime={mealTime} />
        )}
      </div>

      {/* Common controls */}
      <div style={{ ...card, marginTop: 0 }}>
        <p
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#374151",
            marginBottom: 12,
            marginTop: 0,
          }}
        >
          공통 설정
        </p>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div>
            <label style={labelStyle}>식사 유형</label>
            <select
              value={mealType}
              onChange={(e) => setMealType(e.target.value as MealType)}
              style={{ ...inputStyle, width: 100 }}
            >
              <option value="아침">아침</option>
              <option value="점심">점심</option>
              <option value="저녁">저녁</option>
              <option value="간식">간식</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>날짜</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              style={{ ...inputStyle, width: 150 }}
            />
          </div>
          <div>
            <label style={labelStyle}>시간 (선택)</label>
            <input
              type="time"
              value={mealTime}
              onChange={(e) => setMealTime(e.target.value)}
              style={{ ...inputStyle, width: 120 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
