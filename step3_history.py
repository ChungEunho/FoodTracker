import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from step1_recognize import recognize
from step2_nutrition import analyze, print_table
from _paths import data_dir

DB_PATH = data_dir() / "history.db"
MEAL_TYPES = ("아침", "점심", "저녁", "간식")


# ── DB 초기화 ──────────────────────────────────────────────────────────────────

_db_initialized = False


def get_conn() -> sqlite3.Connection:
    global _db_initialized
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if not _db_initialized:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                meal_type   TEXT NOT NULL,
                image_path  TEXT,
                items_json  TEXT NOT NULL,
                total_json  TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                meal_time   TEXT
            )
        """)
        # 기존 DB 마이그레이션
        try:
            conn.execute("ALTER TABLE meals ADD COLUMN meal_time TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        _db_initialized = True
    return conn


# ── 서브커맨드: log ────────────────────────────────────────────────────────────

def cmd_log(args):
    meal_date = args.date or date.today().isoformat()
    try:
        datetime.strptime(meal_date, "%Y-%m-%d")
    except ValueError:
        print("날짜 형식 오류: YYYY-MM-DD 형식으로 입력해주세요.")
        sys.exit(1)

    if args.meal not in MEAL_TYPES:
        print(f"식사 종류 오류: 아침 / 점심 / 저녁 / 간식 중 하나를 입력해주세요.")
        sys.exit(1)

    meal_time = args.time or datetime.now().strftime("%H:%M")
    try:
        datetime.strptime(meal_time, "%H:%M")
    except ValueError:
        print("시간 형식 오류: HH:MM 형식으로 입력해주세요.")
        sys.exit(1)

    print(f"[1단계] 이미지 인식 중...")
    step1 = recognize(args.image)
    print(f"[2단계] 영양 정보 분석 중...")
    result = analyze(step1)

    print(f"\n{meal_date} {args.meal} ({meal_time}) 분석 결과")
    print_table(result)

    conn = get_conn()
    conn.execute(
        "INSERT INTO meals (date, meal_type, image_path, items_json, total_json, created_at, meal_time) VALUES (?,?,?,?,?,?,?)",
        (
            meal_date,
            args.meal,
            args.image,
            json.dumps(result.get("items", []), ensure_ascii=False),
            json.dumps(result.get("total", {}), ensure_ascii=False),
            datetime.now().isoformat(),
            meal_time,
        ),
    )
    conn.commit()
    conn.close()
    print(f"\n기록 저장 완료 ({meal_date} {args.meal} {meal_time})")


# ── 서브커맨드: show ───────────────────────────────────────────────────────────

def cmd_show(args):
    show_date = args.date or date.today().isoformat()
    try:
        datetime.strptime(show_date, "%Y-%m-%d")
    except ValueError:
        print("날짜 형식 오류: YYYY-MM-DD 형식으로 입력해주세요.")
        sys.exit(1)

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM meals WHERE date = ? ORDER BY meal_type",
        (show_date,),
    ).fetchall()
    conn.close()

    sep = "━" * 62
    print(sep)
    print(f" {show_date} 식사 기록")
    print(sep)

    day_total = {"calories_kcal": 0, "carbs_g": 0, "protein_g": 0, "fat_g": 0, "sugar_g": 0}
    recorded = set()

    for meal_type in MEAL_TYPES:
        print(f"\n [{meal_type}]")
        meal_rows = [r for r in rows if r["meal_type"] == meal_type]
        if not meal_rows:
            print("   기록 없음")
            continue
        for row in meal_rows:
            recorded.add(meal_type)
            t = row["meal_time"] or row["created_at"][11:16]
            items = json.loads(row["items_json"])
            total = json.loads(row["total_json"])
            print(f"   [{t}]")
            for it in items:
                print(
                    f"   {it['name']:<16} {it.get('weight_g', 0):>4}g  "
                    f"{it.get('calories_kcal', 0):>4}kcal  "
                    f"탄{it.get('carbs_g', 0)}g 단{it.get('protein_g', 0)}g "
                    f"지{it.get('fat_g', 0)}g 당{it.get('sugar_g', 0)}g"
                )
            print(
                f"   소계: {total.get('weight_g', 0)}g | {total.get('calories_kcal', 0)}kcal | "
                f"탄{total.get('carbs_g', 0)} 단{total.get('protein_g', 0)} "
                f"지{total.get('fat_g', 0)} 당{total.get('sugar_g', 0)}"
            )
            for k in day_total:
                day_total[k] += total.get(k, 0)

    print(f"\n {'─' * 58}")
    print(
        f" 하루 합계: {day_total['calories_kcal']}kcal | "
        f"탄{day_total['carbs_g']}g 단{day_total['protein_g']}g "
        f"지{day_total['fat_g']}g 당{day_total['sugar_g']}g"
    )
    print(sep)


# ── 서브커맨드: summary ────────────────────────────────────────────────────────

def cmd_summary(args):
    try:
        datetime.strptime(args.from_date, "%Y-%m-%d")
        datetime.strptime(args.to_date, "%Y-%m-%d")
    except ValueError:
        print("날짜 형식 오류: YYYY-MM-DD 형식으로 입력해주세요.")
        sys.exit(1)

    conn = get_conn()
    rows = conn.execute(
        "SELECT date, total_json FROM meals WHERE date BETWEEN ? AND ? ORDER BY date",
        (args.from_date, args.to_date),
    ).fetchall()
    conn.close()

    # 날짜별 합산
    day_map: dict[str, dict] = {}
    for row in rows:
        d = row["date"]
        total = json.loads(row["total_json"])
        if d not in day_map:
            day_map[d] = {"calories_kcal": 0, "carbs_g": 0, "protein_g": 0, "fat_g": 0}
        for k in day_map[d]:
            day_map[d][k] += total.get(k, 0)

    sep = "━" * 54
    print(sep)
    print(f" {args.from_date} ~ {args.to_date} 요약")
    print(sep)
    print(f" {'날짜':<12} {'칼로리':>7} {'탄수':>6} {'단백':>6} {'지방':>6}")
    print(f" {'─' * 50}")

    if not day_map:
        print(" 해당 기간의 기록이 없습니다.")
        print(sep)
        return

    totals = {"calories_kcal": 0, "carbs_g": 0, "protein_g": 0, "fat_g": 0}
    for d, t in sorted(day_map.items()):
        print(f" {d:<12} {t['calories_kcal']:>6}  {t['carbs_g']:>5}g {t['protein_g']:>5}g {t['fat_g']:>5}g")
        for k in totals:
            totals[k] += t[k]

    n = len(day_map)
    print(f" {'─' * 50}")
    print(
        f" {'평균':<12} {totals['calories_kcal']//n:>6}  "
        f"{totals['carbs_g']//n:>5}g {totals['protein_g']//n:>5}g {totals['fat_g']//n:>5}g"
    )
    print(sep)


# ── 서브커맨드: delete ─────────────────────────────────────────────────────────

def cmd_delete(args):
    conn = get_conn()
    row = conn.execute("SELECT * FROM meals WHERE id = ?", (args.id,)).fetchone()
    if not row:
        print(f"ID {args.id}에 해당하는 기록이 없습니다.")
        conn.close()
        sys.exit(1)

    print(f"삭제할 기록: [{row['date']}] {row['meal_type']} (ID={row['id']})")
    confirm = input("삭제하시겠습니까? (y/N): ").strip().lower()
    if confirm != "y":
        print("취소되었습니다.")
        conn.close()
        return

    conn.execute("DELETE FROM meals WHERE id = ?", (args.id,))
    conn.commit()
    conn.close()
    print("삭제 완료.")


# ── 진입점 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="식사 히스토리 관리")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="식사 기록 저장")
    p_log.add_argument("image", help="음식 이미지 경로")
    p_log.add_argument("--meal", required=True, choices=MEAL_TYPES, help="식사 종류")
    p_log.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD, 기본: 오늘)")
    p_log.add_argument("--time", default=None, help="식사 시각 (HH:MM, 기본: 현재 시각)")

    # show
    p_show = sub.add_parser("show", help="일별 조회")
    p_show.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD, 기본: 오늘)")

    # summary
    p_sum = sub.add_parser("summary", help="기간별 요약")
    p_sum.add_argument("--from", dest="from_date", required=True, help="시작일 (YYYY-MM-DD)")
    p_sum.add_argument("--to", dest="to_date", required=True, help="종료일 (YYYY-MM-DD)")

    # delete
    p_del = sub.add_parser("delete", help="기록 삭제")
    p_del.add_argument("--id", type=int, required=True, help="삭제할 기록 ID")

    args = parser.parse_args()
    {"log": cmd_log, "show": cmd_show, "summary": cmd_summary, "delete": cmd_delete}[args.command](args)


if __name__ == "__main__":
    main()
