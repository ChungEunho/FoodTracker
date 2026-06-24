"""\napp.py — 식사 영양 트래커 GUI\n"""
import json
import queue
import threading
import tkinter as tk
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

from step1_recognize import recognize
from step2_nutrition import analyze
from step3_history import get_conn, MEAL_TYPES
from nutrition_search import search_nutrition

# ── 컬러 팔레트 ──────────────────────────────────────────────────────────────
C = {
    "bg":         "#F7F8FA",
    "surface":    "#FFFFFF",
    "border":     "#E2E5EA",
    "primary":    "#2D7DD2",
    "primary_dk": "#1F5FAA",
    "accent":     "#4CAF50",
    "danger":     "#E53935",
    "text":       "#1A1A2E",
    "text_sub":   "#6B7280",
    "row_even":   "#F9FAFB",
    "row_odd":    "#FFFFFF",
    "header_bg":  "#EEF2FF",
    "avg_bg":     "#F0FDF4",
    "total_bg":   "#FFF8E7",
}

_NUTR_COLS = ("name", "weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
_NUTR_HDRS = ("음식", "중량(g)", "칼로리", "탄수(g)", "단백(g)", "지방(g)", "당류(g)")
_NUTR_WIDS = (210, 65, 65, 65, 65, 65, 65)


def _tree(parent, cols, headers, widths, height=12):
    wrap = ttk.Frame(parent)
    wrap.pack(fill="both", expand=True, padx=10, pady=5)

    tv = ttk.Treeview(wrap, columns=cols, show="headings", height=height)
    for col, h, w in zip(cols, headers, widths):
        tv.heading(col, text=h)
        tv.column(col, width=w, anchor="center")
    tv.column(cols[0], anchor="w")

    tv.tag_configure("odd", background=C["row_odd"])
    tv.tag_configure("even", background=C["row_even"])

    sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return tv


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("식사 영양 트래커")
        self.geometry("880x720")
        self.minsize(800, 600)

        self._q: queue.Queue = queue.Queue()
        self._preview_ref = None

        self._pending_items: list[dict] = []
        self._pending_total: dict = {}
        self._pending_image_path: str = ""
        self._show_meal_map: dict[str, int] = {}

        self._apply_theme()

        header = tk.Frame(self, bg=C["primary"], height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="🥗  NutriTrack",
            bg=C["primary"], fg="white",
            font=("Helvetica Neue", 18, "bold"),
        ).pack(side="left", padx=20, pady=10)
        tk.Label(
            header,
            text="AI 기반 식사 영양 트래커",
            bg=C["primary"], fg="#A8C8F0",
            font=("Helvetica Neue", 11),
        ).pack(side="left", pady=14)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_log(nb)
        self._build_show(nb)
        self._build_summary(nb)
        self._build_records(nb)

        self._poll()

    def _apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        self.configure(bg=C["bg"])
        style.configure("TFrame", background=C["bg"])
        style.configure("TLabel", background=C["bg"], foreground=C["text"], font=("Helvetica Neue", 12))
        style.configure("TLabelframe", background=C["bg"], bordercolor=C["border"], font=("Helvetica Neue", 11, "bold"), foreground=C["text"])
        style.configure("TLabelframe.Label", background=C["bg"], foreground=C["text"], font=("Helvetica Neue", 11, "bold"))
        style.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", font=("Helvetica Neue", 12), padding=[18, 8], background=C["border"], foreground=C["text_sub"])
        style.map("TNotebook.Tab", background=[("selected", C["surface"]), ("active", "#D9E4F5")], foreground=[("selected", C["primary"]), ("active", C["text"])], expand=[("selected", [1, 1, 1, 0])])
        style.configure("TButton", font=("Helvetica Neue", 11), padding=[12, 6], relief="flat", background=C["border"], foreground=C["text"])
        style.map("TButton", background=[("active", "#C8D0DC"), ("disabled", "#E5E7EB")], foreground=[("disabled", "#9CA3AF")])
        style.configure("Primary.TButton", font=("Helvetica Neue", 11, "bold"), padding=[14, 7], background=C["primary"], foreground="white")
        style.map("Primary.TButton", background=[("active", C["primary_dk"]), ("disabled", "#93B8E0")], foreground=[("disabled", "white")])
        style.configure("Danger.TButton", font=("Helvetica Neue", 11), padding=[12, 6], background="#FEE2E2", foreground=C["danger"])
        style.map("Danger.TButton", background=[("active", "#FECACA"), ("disabled", "#F5F5F5")], foreground=[("disabled", "#D1D5DB")])
        style.configure("Small.TButton", font=("Helvetica Neue", 10), padding=[6, 4], background=C["border"], foreground=C["text_sub"])
        style.map("Small.TButton", background=[("active", "#C8D0DC")])
        style.configure("TEntry", fieldbackground=C["surface"], foreground=C["text"], bordercolor=C["border"], lightcolor=C["border"], darkcolor=C["border"], font=("Helvetica Neue", 11), padding=[6, 4])
        style.configure("TCombobox", fieldbackground=C["surface"], foreground=C["text"], font=("Helvetica Neue", 11))
        style.configure("TProgressbar", troughcolor=C["border"], background=C["primary"], thickness=6)
        style.configure("Treeview", background=C["surface"], foreground=C["text"], fieldbackground=C["surface"], font=("Helvetica Neue", 11), rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=C["bg"], foreground=C["text_sub"], font=("Helvetica Neue", 10, "bold"), relief="flat", padding=[0, 6])
        style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", C["primary_dk"])])
        style.map("Treeview.Heading", background=[("active", C["border"])])
        style.configure("TScrollbar", troughcolor=C["bg"], background=C["border"], width=8, arrowsize=0)

    def _poll(self):
        try:
            while True:
                self._q.get_nowait()()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _post(self, fn):
        self._q.put(fn)

    def _build_log(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  식사 기록  ")
        self._method_nb = ttk.Notebook(f)
        self._method_nb.pack(fill="x", padx=12, pady=(12, 4))
        tab_img = ttk.Frame(self._method_nb, padding=(10, 8))
        self._method_nb.add(tab_img, text="  이미지 분석  ")
        self._build_log_image_tab(tab_img)
        tab_srch = ttk.Frame(self._method_nb, padding=(10, 8))
        self._method_nb.add(tab_srch, text="  브랜드·메뉴 검색  ")
        self._build_log_search_tab(tab_srch)
        tab_man = ttk.Frame(self._method_nb, padding=(10, 8))
        self._method_nb.add(tab_man, text="  직접 입력  ")
        self._build_log_manual_tab(tab_man)
        self._method_nb.bind("<<NotebookTabChanged>>", self._on_method_tab_change)
        opt_f = ttk.LabelFrame(f, text="식사 정보", padding=12)
        opt_f.pack(fill="x", padx=12, pady=(4, 4))
        ttk.Label(opt_f, text="식사 종류:").grid(row=0, column=0, sticky="w")
        self._meal_var = tk.StringVar(value="점심")
        ttk.Combobox(opt_f, textvariable=self._meal_var, values=list(MEAL_TYPES), state="readonly", width=8).grid(row=0, column=1, padx=(4, 24), sticky="w")
        ttk.Label(opt_f, text="날짜 (YYYY-MM-DD):").grid(row=0, column=2, sticky="w")
        self._log_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(opt_f, textvariable=self._log_date, width=13).grid(row=0, column=3, padx=(4, 4), sticky="w")
        ttk.Button(opt_f, text="오늘", width=4, style="Small.TButton", command=lambda: self._log_date.set(date.today().isoformat())).grid(row=0, column=4, padx=(0, 2), sticky="w")
        ttk.Button(opt_f, text="어제", width=4, style="Small.TButton", command=lambda: self._log_date.set((date.today() - timedelta(days=1)).isoformat())).grid(row=0, column=5, padx=(0, 12), sticky="w")
        ttk.Label(opt_f, text="시간 (HH:MM):").grid(row=0, column=6, sticky="w")
        self._log_time = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        ttk.Entry(opt_f, textvariable=self._log_time, width=7).grid(row=0, column=7, padx=(4, 0), sticky="w")
        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=12, pady=(2, 2))
        self._log_pb = ttk.Progressbar(ctrl, mode="indeterminate", length=120)
        self._log_pb.pack(side="left")
        self._log_status = tk.StringVar(value="입력 방법을 선택하세요.")
        self._log_status_lbl = ttk.Label(ctrl, textvariable=self._log_status, foreground=C["text_sub"], font=("Helvetica Neue", 11))
        self._log_status_lbl.pack(side="left", padx=8)
        self._log_tree = _tree(f, _NUTR_COLS, _NUTR_HDRS, _NUTR_WIDS, height=7)
        self._log_tree.tag_configure("total", font=("Helvetica Neue", 11, "bold"), background=C["total_bg"])
        self._log_save_bar = ttk.Frame(f)
        self._log_save_bar.pack(fill="x", padx=12, pady=(0, 6))
        self._log_save_btn = ttk.Button(self._log_save_bar, text="저장", style="Primary.TButton", command=self._do_save_result, state="disabled")
        self._log_save_btn.pack(side="left")
        ttk.Button(self._log_save_bar, text="초기화", style="Small.TButton", command=self._clear_log_tree).pack(side="left", padx=8)
        self._on_method_tab_change(None)

    def _build_log_image_tab(self, f):
        row = ttk.Frame(f)
        row.pack(fill="x")
        self._img_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._img_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기…", command=self._pick_image).pack(side="left", padx=(6, 0))
        self._preview_lbl = ttk.Label(f, text="이미지를 선택하면 미리보기가 표시됩니다", foreground=C["text_sub"], font=("Helvetica Neue", 11), background=C["bg"])
        self._preview_lbl.pack(pady=(6, 2))
        self._log_btn = ttk.Button(f, text="분석 & 저장", style="Primary.TButton", command=self._do_analyze)
        self._log_btn.pack(anchor="w", pady=(4, 0))

    def _build_log_search_tab(self, f):
        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Label(row, text="브랜드명:").pack(side="left")
        self._srch_brand = tk.StringVar()
        ttk.Entry(row, textvariable=self._srch_brand, width=16).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="메뉴명:").pack(side="left")
        self._srch_menu = tk.StringVar()
        ttk.Entry(row, textvariable=self._srch_menu, width=22).pack(side="left", padx=(4, 12))
        self._srch_btn = ttk.Button(row, text="검색", style="Primary.TButton", command=self._do_search)
        self._srch_btn.pack(side="left")
        ttk.Label(f, text="인터넷에서 칼로리 및 영양 정보를 검색합니다. 검색 후 결과를 확인하고 '저장'을 누르세요.", foreground=C["text_sub"], font=("Helvetica Neue", 10), background=C["bg"]).pack(anchor="w", pady=(6, 0))

    def _build_log_manual_tab(self, f):
        fields_f = ttk.Frame(f)
        fields_f.pack(fill="x")
        labels = ["음식명", "중량(g)", "칼로리", "탄수(g)", "단백(g)", "지방(g)", "당류(g)"]
        widths = [18, 7, 7, 7, 7, 7, 7]
        self._manual_vars = []
        for col, (lbl, w) in enumerate(zip(labels, widths)):
            ttk.Label(fields_f, text=lbl, font=("Helvetica Neue", 10)).grid(row=0, column=col, padx=(0 if col == 0 else 4, 0), sticky="w")
            var = tk.StringVar()
            self._manual_vars.append(var)
            ttk.Entry(fields_f, textvariable=var, width=w).grid(row=1, column=col, padx=(0 if col == 0 else 4, 0), sticky="ew")
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="항목 추가", style="Primary.TButton", command=self._do_add_manual).pack(side="left")
        ttk.Label(btn_row, text="항목을 하나씩 추가한 뒤 '저장'을 누르세요.", foreground=C["text_sub"], font=("Helvetica Neue", 10), background=C["bg"]).pack(side="left", padx=10)

    def _on_method_tab_change(self, _event):
        idx = self._method_nb.index("current") if _event else 0
        if idx == 0:
            self._log_save_bar.pack_forget()
        else:
            self._log_save_bar.pack(fill="x", padx=12, pady=(0, 6))

    def _pick_image(self):
        path = filedialog.askopenfilename(title="음식 이미지 선택", filetypes=[("모든 파일", "*.*")])
        if not path:
            return
        self._img_var.set(path)
        if _PIL:
            try:
                img = Image.open(path)
                img.thumbnail((240, 160))
                self._preview_ref = ImageTk.PhotoImage(img)
                self._preview_lbl.configure(image=self._preview_ref, text="", background=C["bg"])
            except Exception:
                self._preview_lbl.configure(image="", text=Path(path).name, foreground=C["text_sub"], font=("Helvetica Neue", 11))
        else:
            self._preview_lbl.configure(text=Path(path).name, foreground=C["text_sub"], font=("Helvetica Neue", 11))

    def _do_analyze(self):
        path = self._img_var.get()
        if not path:
            messagebox.showwarning("경고", "이미지를 먼저 선택해주세요.")
            return
        meal = self._meal_var.get()
        meal_date = self._log_date.get()
        meal_time = self._log_time.get()
        self._log_btn.state(["disabled"])
        self._log_pb.start(12)
        self._log_status_fg(C["text_sub"])
        self._log_status.set("🔍 [1/2] 이미지에서 음식을 인식하는 중…")
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        def worker():
            try:
                step1 = recognize(path)
                self._post(lambda: (self._log_status_fg(C["text_sub"]), self._log_status.set("📊 [2/2] 영양 정보를 계산하는 중…")))
                result = analyze(step1)
                self._post(lambda r=result: self._analyze_done(r, path, meal, meal_date, meal_time))
            except Exception as e:
                self._post(lambda err=str(e): self._log_error(err))
        threading.Thread(target=worker, daemon=True).start()

    def _analyze_done(self, result, path, meal, meal_date, meal_time):
        self._log_pb.stop()
        items = result.get("items", [])
        total = result.get("total", {})
        for idx, it in enumerate(items):
            tag = "even" if idx % 2 == 0 else "odd"
            self._log_tree.insert("", "end", tags=(tag,), values=(it.get("name", ""), it.get("weight_g", 0), it.get("calories_kcal", 0), it.get("carbs_g", 0), it.get("protein_g", 0), it.get("fat_g", 0), it.get("sugar_g", 0)))
        if total:
            self._log_tree.insert("", "end", tags=("total",), values=("── 합계 ──", total.get("weight_g", 0), total.get("calories_kcal", 0), total.get("carbs_g", 0), total.get("protein_g", 0), total.get("fat_g", 0), total.get("sugar_g", 0)))
        try:
            with closing(get_conn()) as conn, conn:
                conn.execute("INSERT INTO meals (date, meal_type, image_path, items_json, total_json, created_at, meal_time) VALUES (?,?,?,?,?,?,?)", (meal_date, meal, path, json.dumps(items, ensure_ascii=False), json.dumps(total, ensure_ascii=False), datetime.now().isoformat(), meal_time))
            self._log_status_fg(C["accent"])
            self._log_status.set(f"✅ 저장 완료 ({meal_date} {meal} {meal_time})")
        except Exception as e:
            self._log_status_fg(C["danger"])
            self._log_status.set(f"❌ 오류: DB 저장 실패 — {e}")
        self._log_btn.state(["!disabled"])
        self._load_records()

    def _do_search(self):
        brand = self._srch_brand.get().strip()
        menu = self._srch_menu.get().strip()
        if not brand and not menu:
            messagebox.showwarning("경고", "브랜드명 또는 메뉴명을 입력해주세요.")
            return
        self._srch_btn.state(["disabled"])
        self._log_pb.start(12)
        self._log_status_fg(C["text_sub"])
        self._log_status.set(f"🔍 '{brand} {menu}' 영양 정보를 검색하는 중…")
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        def _on_progress(msg: str):
            self._post(lambda m=msg: self._log_status.set(m))
        def worker():
            try:
                result, found_name, is_exact = search_nutrition(brand, menu, progress_cb=_on_progress)
                self._post(lambda r=result, fn=found_name, ie=is_exact: self._search_done(r, fn, ie, brand, menu))
            except Exception as e:
                self._post(lambda err=str(e): self._log_error(err))
        threading.Thread(target=worker, daemon=True).start()

    def _search_done(self, result, found_name, is_exact, brand, menu):
        self._log_pb.stop()
        self._srch_btn.state(["!disabled"])
        if result is None:
            self._log_status_fg(C["danger"])
            self._log_status.set(f"❌ '{brand} {menu}' 영양 정보를 찾을 수 없습니다.")
            return
        if not is_exact:
            ok = messagebox.askyesno("검색 결과 확인", f"'{brand} {menu}'를 정확히 찾지 못했습니다.\n\n대신 아래 제품의 영양 정보를 사용하시겠습니까?\n\n  ▶  {found_name}")
            if not ok:
                self._log_status_fg(C["text_sub"])
                self._log_status.set("검색이 취소되었습니다.")
                return
        self._pending_items = result.get("items", [])
        self._pending_total = result.get("total", {})
        self._pending_image_path = ""
        self._update_log_tree()
        self._log_status_fg(C["accent"])
        self._log_status.set(f"✅ '{found_name}' 정보를 불러왔습니다. '저장'을 눌러 기록하세요.")
        self._log_save_btn.state(["!disabled"])

    def _do_add_manual(self):
        keys = ("name", "weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
        raw = [v.get().strip() for v in self._manual_vars]
        if not raw[0]:
            messagebox.showwarning("경고", "음식명을 입력해주세요.")
            return
        item: dict = {"name": raw[0]}
        for key, val in zip(keys[1:], raw[1:]):
            try:
                item[key] = int(val) if val else 0
            except ValueError:
                messagebox.showwarning("경고", f"'{key}' 값은 숫자로 입력해주세요.")
                return
        self._pending_items.append(item)
        keys_num = ("weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
        self._pending_total = {k: sum(it.get(k, 0) for it in self._pending_items) for k in keys_num}
        self._pending_image_path = ""
        self._update_log_tree()
        for var in self._manual_vars[1:]:
            var.set("")
        self._manual_vars[0].set("")
        self._log_status_fg(C["text_sub"])
        self._log_status.set(f"항목이 추가되었습니다. 계속 추가하거나 '저장'을 누르세요.")
        self._log_save_btn.state(["!disabled"])

    def _update_log_tree(self):
        for child in self._log_tree.get_children():
            self._log_tree.delete(child)
        for idx, it in enumerate(self._pending_items):
            tag = "even" if idx % 2 == 0 else "odd"
            self._log_tree.insert("", "end", tags=(tag,), values=(it.get("name", ""), it.get("weight_g", 0), it.get("calories_kcal", 0), it.get("carbs_g", 0), it.get("protein_g", 0), it.get("fat_g", 0), it.get("sugar_g", 0)))
        t = self._pending_total
        if t:
            self._log_tree.insert("", "end", tags=("total",), values=("── 합계 ──", t.get("weight_g", 0), t.get("calories_kcal", 0), t.get("carbs_g", 0), t.get("protein_g", 0), t.get("fat_g", 0), t.get("sugar_g", 0)))

    def _clear_log_tree(self):
        self._pending_items = []
        self._pending_total = {}
        self._pending_image_path = ""
        for child in self._log_tree.get_children():
            self._log_tree.delete(child)
        self._log_save_btn.state(["disabled"])
        self._log_status_fg(C["text_sub"])
        self._log_status.set("초기화되었습니다.")

    def _do_save_result(self):
        if not self._pending_items:
            messagebox.showwarning("경고", "저장할 항목이 없습니다.")
            return
        meal = self._meal_var.get()
        meal_date = self._log_date.get()
        meal_time = self._log_time.get()
        try:
            with closing(get_conn()) as conn, conn:
                conn.execute("INSERT INTO meals (date, meal_type, image_path, items_json, total_json, created_at, meal_time) VALUES (?,?,?,?,?,?,?)", (meal_date, meal, self._pending_image_path, json.dumps(self._pending_items, ensure_ascii=False), json.dumps(self._pending_total, ensure_ascii=False), datetime.now().isoformat(), meal_time))
            self._log_status_fg(C["accent"])
            self._log_status.set(f"✅ 저장 완료 ({meal_date} {meal} {meal_time})")
            self._log_save_btn.state(["disabled"])
            self._pending_items = []
            self._pending_total = {}
            self._pending_image_path = ""
        except Exception as e:
            self._log_status_fg(C["danger"])
            self._log_status.set(f"❌ DB 저장 실패 — {e}")
            messagebox.showerror("저장 오류", str(e))
        self._load_records()

    def _log_status_fg(self, color: str):
        self._log_status_lbl.configure(foreground=color)

    def _log_error(self, msg):
        self._log_pb.stop()
        self._log_status_fg(C["danger"])
        self._log_status.set(f"❌ 오류: {msg}")
        try:
            self._log_btn.state(["!disabled"])
        except Exception:
            pass
        try:
            self._srch_btn.state(["!disabled"])
        except Exception:
            pass
        messagebox.showerror("오류", msg)

    def _build_show(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  일별 조회  ")
        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=12, pady=10)
        ttk.Label(ctrl, text="날짜:").pack(side="left")
        self._show_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(ctrl, textvariable=self._show_date, width=13).pack(side="left", padx=(4, 4))
        ttk.Button(ctrl, text="오늘", width=4, style="Small.TButton", command=lambda: self._show_date.set(date.today().isoformat())).pack(side="left", padx=(0, 2))
        ttk.Button(ctrl, text="어제", width=4, style="Small.TButton", command=lambda: self._show_date.set((date.today() - timedelta(days=1)).isoformat())).pack(side="left", padx=(0, 10))
        ttk.Button(ctrl, text="조회", style="Primary.TButton", command=self._do_show).pack(side="left", padx=(0, 10))
        self._show_del_btn = ttk.Button(ctrl, text="선택 식사 삭제", style="Danger.TButton", command=self._do_delete_show_meal, state="disabled")
        self._show_del_btn.pack(side="left")
        self._show_summary = tk.StringVar()
        ttk.Label(f, textvariable=self._show_summary, foreground=C["primary"], font=("Helvetica Neue", 12, "bold"), background=C["bg"]).pack(padx=12, pady=(4, 8), anchor="w")
        self._show_tree = _tree(f, _NUTR_COLS, _NUTR_HDRS, _NUTR_WIDS, height=16)
        self._show_tree.tag_configure("meal_header", background=C["header_bg"], font=("Helvetica Neue", 11, "bold"))
        self._show_tree.tag_configure("subtotal", font=("Helvetica Neue", 11, "bold"), background=C["total_bg"])
        self._show_tree.tag_configure("empty", foreground=C["text_sub"])
        self._show_tree.tag_configure("time_row", foreground=C["text_sub"], font=("Helvetica Neue", 10, "italic"))
        self._show_tree.bind("<<TreeviewSelect>>", self._on_show_select)

    def _do_show(self):
        for item in self._show_tree.get_children():
            self._show_tree.delete(item)
        self._show_summary.set("")
        self._show_meal_map.clear()
        self._show_del_btn.state(["disabled"])
        with closing(get_conn()) as conn:
            rows = conn.execute("SELECT * FROM meals WHERE date = ? ORDER BY meal_type, created_at", (self._show_date.get(),)).fetchall()
        if not rows:
            self._show_tree.insert("", "end", tags=("empty",), values=("기록이 없습니다. '식사 기록' 탭에서 추가하세요.", "", "", "", "", "", ""))
            return
        day = {k: 0 for k in ("calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")}
        grouped = defaultdict(list)
        for r in rows:
            grouped[r["meal_type"]].append(r)
        data_row_idx = 0
        for mt in MEAL_TYPES:
            self._show_tree.insert("", "end", tags=("meal_header",), values=(f"▶  {mt}", "", "", "", "", "", ""))
            meal_rows = grouped.get(mt, [])
            if not meal_rows:
                self._show_tree.insert("", "end", tags=("empty",), values=("   기록 없음", "", "", "", "", "", ""))
                continue
            for row in meal_rows:
                meal_id = row["id"]
                t = row["meal_time"] or row["created_at"][11:16]
                iid_time = self._show_tree.insert("", "end", tags=("time_row",), values=(f"   · {t}", "", "", "", "", "", ""))
                self._show_meal_map[iid_time] = meal_id
                items = json.loads(row["items_json"])
                total = json.loads(row["total_json"])
                for it in items:
                    tag = "even" if data_row_idx % 2 == 0 else "odd"
                    data_row_idx += 1
                    iid = self._show_tree.insert("", "end", tags=(tag,), values=(f"     {it.get('name', '')}", it.get("weight_g", 0), it.get("calories_kcal", 0), it.get("carbs_g", 0), it.get("protein_g", 0), it.get("fat_g", 0), it.get("sugar_g", 0)))
                    self._show_meal_map[iid] = meal_id
                iid_sub = self._show_tree.insert("", "end", tags=("subtotal",), values=("   소계", total.get("weight_g", 0), total.get("calories_kcal", 0), total.get("carbs_g", 0), total.get("protein_g", 0), total.get("fat_g", 0), total.get("sugar_g", 0)))
                self._show_meal_map[iid_sub] = meal_id
                for k in day:
                    day[k] += total.get(k, 0)
        self._show_summary.set(f"하루 합계:  {day['calories_kcal']} kcal  |  탄수 {day['carbs_g']}g   단백 {day['protein_g']}g   지방 {day['fat_g']}g   당류 {day['sugar_g']}g")

    def _on_show_select(self, _event):
        sel = self._show_tree.selection()
        has_meal = any(iid in self._show_meal_map for iid in sel)
        self._show_del_btn.state(["!disabled"] if has_meal else ["disabled"])

    def _do_delete_show_meal(self):
        sel = self._show_tree.selection()
        meal_ids = {self._show_meal_map[iid] for iid in sel if iid in self._show_meal_map}
        if not meal_ids:
            return
        count = len(meal_ids)
        if not messagebox.askyesno("삭제 확인", f"선택한 식사 기록 {count}건을 삭제하시겠습니까?\n\n삭제된 기록은 복구할 수 없습니다."):
            return
        with closing(get_conn()) as conn, conn:
            conn.executemany("DELETE FROM meals WHERE id = ?", [(i,) for i in meal_ids])
        self._do_show()
        self._load_records()

    def _build_summary(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  기간 요약  ")
        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=12, pady=10)
        ttk.Label(ctrl, text="시작일:").pack(side="left")
        self._from_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(ctrl, textvariable=self._from_var, width=13).pack(side="left", padx=(4, 4))
        ttk.Button(ctrl, text="어제", width=4, style="Small.TButton", command=lambda: self._from_var.set((date.today() - timedelta(days=1)).isoformat())).pack(side="left", padx=(0, 12))
        ttk.Label(ctrl, text="종료일:").pack(side="left")
        self._to_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(ctrl, textvariable=self._to_var, width=13).pack(side="left", padx=(4, 4))
        ttk.Button(ctrl, text="오늘", width=4, style="Small.TButton", command=lambda: self._to_var.set(date.today().isoformat())).pack(side="left", padx=(0, 12))
        ttk.Button(ctrl, text="요약", style="Primary.TButton", command=self._do_summary).pack(side="left")
        sum_cols = ("date", "calories_kcal", "carbs_g", "protein_g", "fat_g")
        sum_hdrs = ("날짜", "칼로리", "탄수(g)", "단백(g)", "지방(g)")
        sum_wids = (140, 90, 90, 90, 90)
        self._sum_tree = _tree(f, sum_cols, sum_hdrs, sum_wids, height=18)
        self._sum_tree.tag_configure("avg", font=("Helvetica Neue", 11, "bold"), background=C["avg_bg"])

    def _do_summary(self):
        for item in self._sum_tree.get_children():
            self._sum_tree.delete(item)
        with closing(get_conn()) as conn:
            rows = conn.execute("SELECT date, total_json FROM meals WHERE date BETWEEN ? AND ? ORDER BY date", (self._from_var.get(), self._to_var.get())).fetchall()
        day_map: dict[str, dict] = {}
        for row in rows:
            d = row["date"]
            t = json.loads(row["total_json"])
            if d not in day_map:
                day_map[d] = {"calories_kcal": 0, "carbs_g": 0, "protein_g": 0, "fat_g": 0}
            for k in day_map[d]:
                day_map[d][k] += t.get(k, 0)
        if not day_map:
            self._sum_tree.insert("", "end", values=("해당 기간의 기록이 없습니다.", "", "", "", ""))
            return
        totals = {"calories_kcal": 0, "carbs_g": 0, "protein_g": 0, "fat_g": 0}
        for idx, (d, t) in enumerate(sorted(day_map.items())):
            tag = "even" if idx % 2 == 0 else "odd"
            self._sum_tree.insert("", "end", tags=(tag,), values=(d, t["calories_kcal"], t["carbs_g"], t["protein_g"], t["fat_g"]))
            for k in totals:
                totals[k] += t[k]
        n = len(day_map)
        self._sum_tree.insert("", "end", tags=("avg",), values=("평균", round(totals["calories_kcal"] / n, 1), round(totals["carbs_g"] / n, 1), round(totals["protein_g"] / n, 1), round(totals["fat_g"] / n, 1)))

    def _build_records(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  기록 관리  ")
        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=12, pady=10)
        ttk.Button(ctrl, text="새로 고침", command=self._load_records).pack(side="left")
        self._del_btn = ttk.Button(ctrl, text="선택 삭제", style="Danger.TButton", command=self._do_delete, state="disabled")
        self._del_btn.pack(side="left", padx=8)
        rec_cols = ("id", "date", "meal_type", "meal_time", "calories_kcal", "created_at")
        rec_hdrs = ("ID", "날짜", "식사", "식사 시각", "칼로리", "기록 시각")
        rec_wids = (40, 100, 55, 70, 65, 155)
        self._rec_tree = _tree(f, rec_cols, rec_hdrs, rec_wids, height=20)
        self._rec_tree.configure(selectmode="extended")
        self._rec_tree.bind("<<TreeviewSelect>>", self._on_rec_select)
        self._load_records()

    def _load_records(self):
        for item in self._rec_tree.get_children():
            self._rec_tree.delete(item)
        with closing(get_conn()) as conn:
            rows = conn.execute("SELECT id, date, meal_type, meal_time, total_json, created_at FROM meals ORDER BY date DESC, meal_time, created_at DESC").fetchall()
        for idx, row in enumerate(rows):
            total = json.loads(row["total_json"])
            tag = "even" if idx % 2 == 0 else "odd"
            self._rec_tree.insert("", "end", tags=(tag,), values=(row["id"], row["date"], row["meal_type"], row["meal_time"] or "", total.get("calories_kcal", 0), row["created_at"][:19]))

    def _on_rec_select(self, _event):
        has_sel = bool(self._rec_tree.selection())
        self._del_btn.state(["!disabled"] if has_sel else ["disabled"])

    def _do_delete(self):
        sel = self._rec_tree.selection()
        if not sel:
            return
        rows_info = [self._rec_tree.item(s, "values") for s in sel]
        ids = [v[0] for v in rows_info]
        _MAX_SHOWN = 5
        lines = [f"  • {v[1]} {v[2]} ({v[4]} kcal)" for v in rows_info[:_MAX_SHOWN]]
        if len(rows_info) > _MAX_SHOWN:
            lines.append(f"  외 {len(rows_info) - _MAX_SHOWN}개")
        if not messagebox.askyesno("삭제 확인", f"다음 기록을 삭제하시겠습니까?\n\n" + "\n".join(lines)):
            return
        with closing(get_conn()) as conn, conn:
            conn.executemany("DELETE FROM meals WHERE id = ?", [(i,) for i in ids])
        self._load_records()
        self._del_btn.state(["disabled"])


if __name__ == "__main__":
    App().mainloop()
