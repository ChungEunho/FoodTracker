import type { FoodItem, NutritionTotals } from "@/lib/api/types";

interface NutritionTableProps {
  items: FoodItem[];
  total?: NutritionTotals;
  showDelete?: boolean;
  onDelete?: (index: number) => void;
}

const cellStyle: React.CSSProperties = {
  padding: "8px 10px",
  fontSize: 13,
  textAlign: "right",
  borderBottom: "1px solid #e5e7eb",
};

const headerCellStyle: React.CSSProperties = {
  ...cellStyle,
  fontWeight: 600,
  color: "#374151",
  background: "#f9fafb",
  textAlign: "right",
};

const firstCellStyle: React.CSSProperties = {
  ...cellStyle,
  textAlign: "left",
};

const firstHeaderCellStyle: React.CSSProperties = {
  ...headerCellStyle,
  textAlign: "left",
};

const totalCellStyle: React.CSSProperties = {
  ...cellStyle,
  fontWeight: 700,
  color: "#111827",
  background: "#f0f9ff",
  borderTop: "2px solid #bfdbfe",
  borderBottom: "none",
};

const totalFirstCellStyle: React.CSSProperties = {
  ...totalCellStyle,
  textAlign: "left",
};

function fmt(n: number): string {
  return Number.isFinite(n) ? n.toFixed(1) : "-";
}

export default function NutritionTable({
  items,
  total,
  showDelete = false,
  onDelete,
}: NutritionTableProps) {
  if (items.length === 0 && !total) {
    return (
      <p style={{ color: "#6b7280", fontSize: 14, margin: 0 }}>
        등록된 음식이 없습니다.
      </p>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
          minWidth: 500,
        }}
      >
        <thead>
          <tr>
            <th style={firstHeaderCellStyle}>음식명</th>
            <th style={headerCellStyle}>중량(g)</th>
            <th style={headerCellStyle}>칼로리(kcal)</th>
            <th style={headerCellStyle}>탄수(g)</th>
            <th style={headerCellStyle}>단백(g)</th>
            <th style={headerCellStyle}>지방(g)</th>
            {showDelete && <th style={headerCellStyle}></th>}
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx}>
              <td style={firstCellStyle}>{item.name}</td>
              <td style={cellStyle}>{fmt(item.weight_g)}</td>
              <td style={cellStyle}>{fmt(item.calories_kcal)}</td>
              <td style={cellStyle}>{fmt(item.carbs_g)}</td>
              <td style={cellStyle}>{fmt(item.protein_g)}</td>
              <td style={cellStyle}>{fmt(item.fat_g)}</td>
              {showDelete && (
                <td style={{ ...cellStyle, textAlign: "center" }}>
                  <button
                    onClick={() => onDelete?.(idx)}
                    aria-label={`${item.name} 삭제`}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "#ef4444",
                      fontSize: 16,
                      lineHeight: 1,
                      padding: "0 4px",
                    }}
                  >
                    ×
                  </button>
                </td>
              )}
            </tr>
          ))}
          {total && (
            <tr>
              <td style={totalFirstCellStyle}>합계</td>
              <td style={totalCellStyle}>{fmt(total.weight_g)}</td>
              <td style={totalCellStyle}>{fmt(total.calories_kcal)}</td>
              <td style={totalCellStyle}>{fmt(total.carbs_g)}</td>
              <td style={totalCellStyle}>{fmt(total.protein_g)}</td>
              <td style={totalCellStyle}>{fmt(total.fat_g)}</td>
              {showDelete && <td style={totalCellStyle}></td>}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
