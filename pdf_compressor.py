# -*- coding: utf-8 -*-
"""
PDF 압축 프로그램 (순수 Python / GUI) - 여러 파일 일괄 처리 지원
- pikepdf 로 PDF 구조 최적화 (스트림 재압축, 중복 객체 제거)
- Pillow 로 내부 이미지 다운샘플 + JPEG 재압축
- tkinter GUI: 여러 파일 선택, 압축 강도, 출력 폴더, 진행 상황 표시
"""

import io
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pikepdf
from PIL import Image

# 압축 강도별 설정: (이미지 최대 가로/세로 픽셀, JPEG 품질)
QUALITY_PRESETS = {
    "낮음 (고화질 유지)":   {"max_dim": 2200, "jpeg_quality": 85},
    "보통 (권장)":         {"max_dim": 1600, "jpeg_quality": 70},
    "높음 (용량 최소화)":   {"max_dim": 1000, "jpeg_quality": 55},
}


def human_size(num_bytes):
    """바이트를 사람이 읽기 좋은 단위로 변환."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def compress_images_in_pdf(pdf, max_dim, jpeg_quality, progress_cb=None):
    """PDF 내부의 이미지를 찾아 다운샘플 + JPEG 재압축한다."""
    pages = list(pdf.pages)
    total = len(pages)

    for page_idx, page in enumerate(pages):
        resources = page.get("/Resources")
        if resources is None:
            continue
        xobjects = resources.get("/XObject")
        if xobjects is None:
            continue

        for name, xobj in list(xobjects.items()):
            try:
                if xobj.get("/Subtype") != "/Image":
                    continue

                pdf_image = pikepdf.PdfImage(xobj)
                try:
                    pil_img = pdf_image.as_pil_image()
                except Exception:
                    # 디코딩 불가한 이미지는 건너뛴다
                    continue

                orig_w, orig_h = pil_img.size

                # 다운샘플 (긴 변 기준)
                scale = min(1.0, max_dim / max(orig_w, orig_h))
                if scale < 1.0:
                    new_size = (max(1, int(orig_w * scale)),
                                max(1, int(orig_h * scale)))
                    pil_img = pil_img.resize(new_size, Image.LANCZOS)

                # 알파 채널 / 팔레트 / CMYK 정리 (JPEG는 RGB만)
                if pil_img.mode in ("RGBA", "LA", "P"):
                    pil_img = pil_img.convert("RGB")
                elif pil_img.mode == "CMYK":
                    pil_img = pil_img.convert("RGB")

                # JPEG로 재인코딩
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=jpeg_quality,
                             optimize=True)
                new_data = buf.getvalue()

                # 원본보다 작을 때만 교체
                try:
                    old_len = len(xobj.read_raw_bytes())
                except Exception:
                    old_len = None

                if old_len is None or len(new_data) < old_len:
                    new_w, new_h = pil_img.size
                    xobj.write(new_data,
                               filter=pikepdf.Name("/DCTDecode"))
                    xobj.ColorSpace = pikepdf.Name("/DeviceRGB")
                    xobj.BitsPerComponent = 8
                    xobj.Width = new_w
                    xobj.Height = new_h
                    for key in ("/SMask", "/Decode", "/DecodeParms"):
                        if key in xobj:
                            del xobj[key]
            except Exception:
                # 개별 이미지 실패는 무시하고 계속 진행
                continue

        if progress_cb:
            progress_cb(page_idx + 1, total)


def compress_pdf(input_path, output_path, preset, progress_cb=None):
    """PDF 파일을 압축하여 저장한다. (입력크기, 출력크기) 반환."""
    in_size = os.path.getsize(input_path)

    with pikepdf.open(input_path) as pdf:
        compress_images_in_pdf(
            pdf,
            max_dim=preset["max_dim"],
            jpeg_quality=preset["jpeg_quality"],
            progress_cb=progress_cb,
        )
        pdf.save(
            output_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=True,
            linearize=True,
        )

    out_size = os.path.getsize(output_path)
    return in_size, out_size


class PDFCompressorApp:
    def __init__(self, root):
        self.root = root
        root.title("PDF 압축기 — 일괄 처리")
        root.geometry("640x560")
        root.minsize(560, 480)

        self.files = []                       # 선택된 파일 경로 목록
        self.quality = tk.StringVar(value="보통 (권장)")
        self.out_dir = tk.StringVar()         # 비우면 원본 폴더에 저장
        self.suffix = tk.StringVar(value="_compressed")
        self.running = False

        pad = {"padx": 12, "pady": 6}

        # ── 파일 목록 ──────────────────────────────
        frm_files = tk.LabelFrame(root, text="압축할 PDF 파일 (여러 개 선택 가능)")
        frm_files.pack(fill="both", expand=True, **pad)

        list_wrap = tk.Frame(frm_files)
        list_wrap.pack(fill="both", expand=True, padx=8, pady=8)
        scrollbar = tk.Scrollbar(list_wrap)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_wrap, selectmode=tk.EXTENDED,
                                  yscrollcommand=scrollbar.set,
                                  activestyle="none")
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        btns = tk.Frame(frm_files)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btns, text="파일 추가...", command=self.add_files).pack(side="left")
        tk.Button(btns, text="선택 제거", command=self.remove_selected).pack(side="left", padx=6)
        tk.Button(btns, text="전체 비우기", command=self.clear_files).pack(side="left")
        self.count_label = tk.Label(btns, text="0개", fg="#666")
        self.count_label.pack(side="right")

        # ── 옵션 ──────────────────────────────────
        frm_opt = tk.LabelFrame(root, text="옵션")
        frm_opt.pack(fill="x", **pad)

        row1 = tk.Frame(frm_opt)
        row1.pack(fill="x", padx=8, pady=6)
        tk.Label(row1, text="압축 강도:").pack(side="left")
        for label in QUALITY_PRESETS:
            tk.Radiobutton(row1, text=label, variable=self.quality,
                           value=label).pack(side="left", padx=4)

        row2 = tk.Frame(frm_opt)
        row2.pack(fill="x", padx=8, pady=6)
        tk.Label(row2, text="저장 폴더:").pack(side="left")
        tk.Entry(row2, textvariable=self.out_dir).pack(
            side="left", fill="x", expand=True, padx=6)
        tk.Button(row2, text="폴더 선택...", command=self.choose_outdir).pack(side="left")
        tk.Button(row2, text="원본 폴더", command=lambda: self.out_dir.set("")).pack(side="left", padx=4)

        row3 = tk.Frame(frm_opt)
        row3.pack(fill="x", padx=8, pady=6)
        tk.Label(row3, text="파일명 뒤에 붙일 말:").pack(side="left")
        tk.Entry(row3, textvariable=self.suffix, width=18).pack(side="left", padx=6)
        tk.Label(row3, text="(예: 문서_compressed.pdf)", fg="#888").pack(side="left")

        # ── 실행 ──────────────────────────────────
        self.btn_run = tk.Button(root, text="전체 압축 시작", height=2,
                                 font=("", 11, "bold"), command=self.start_batch)
        self.btn_run.pack(fill="x", **pad)

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(2, 0))

        self.status = tk.Label(root, text="PDF 파일을 추가하세요.",
                               anchor="w", justify="left", fg="#333")
        self.status.pack(fill="x", padx=12, pady=8)

    # ── 파일 목록 관리 ─────────────────────────────
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="PDF 선택 (여러 개 가능)",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                size = human_size(os.path.getsize(p))
                self.listbox.insert(tk.END, f"{os.path.basename(p)}  ({size})")
                added += 1
        self.refresh_count()
        if added:
            self.status.config(text=f"{added}개 파일 추가됨.")

    def remove_selected(self):
        for idx in sorted(self.listbox.curselection(), reverse=True):
            self.listbox.delete(idx)
            del self.files[idx]
        self.refresh_count()

    def clear_files(self):
        self.listbox.delete(0, tk.END)
        self.files.clear()
        self.refresh_count()

    def refresh_count(self):
        self.count_label.config(text=f"{len(self.files)}개")

    def choose_outdir(self):
        d = filedialog.askdirectory(title="저장할 폴더 선택")
        if d:
            self.out_dir.set(d)

    # ── 상태/진행 표시 (스레드 → UI) ────────────────
    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def set_progress(self, value, maximum):
        def update():
            self.progress["maximum"] = maximum
            self.progress["value"] = value
        self.root.after(0, update)

    # ── 일괄 실행 ─────────────────────────────────
    def start_batch(self):
        if self.running:
            return
        if not self.files:
            messagebox.showwarning("알림", "먼저 PDF 파일을 추가하세요.")
            return

        out_dir = self.out_dir.get().strip()
        if out_dir and not os.path.isdir(out_dir):
            messagebox.showerror("오류", "저장 폴더가 존재하지 않습니다.")
            return

        self.running = True
        self.btn_run.config(state="disabled", text="압축 중...")
        preset = QUALITY_PRESETS[self.quality.get()]
        suffix = self.suffix.get().strip()

        t = threading.Thread(
            target=self._run_batch,
            args=(list(self.files), out_dir, suffix, preset),
            daemon=True)
        t.start()

    def _run_batch(self, files, out_dir, suffix, preset):
        total_files = len(files)
        total_in = total_out = 0
        ok = fail = skipped = 0
        errors = []

        self.set_progress(0, total_files)

        for i, in_path in enumerate(files, start=1):
            name = os.path.basename(in_path)
            self.set_status(f"[{i}/{total_files}] 압축 중: {name}")

            try:
                base, _ = os.path.splitext(os.path.basename(in_path))
                folder = out_dir if out_dir else os.path.dirname(in_path)
                out_path = os.path.join(folder, f"{base}{suffix}.pdf")

                # 입력과 출력 경로가 같아지지 않도록 보호
                if os.path.abspath(out_path) == os.path.abspath(in_path):
                    out_path = os.path.join(folder, f"{base}{suffix}_out.pdf")

                in_size, out_size = compress_pdf(in_path, out_path, preset)
                total_in += in_size
                total_out += out_size
                ok += 1
            except Exception as e:
                fail += 1
                errors.append(f"• {name}: {e}")

            self.set_progress(i, total_files)

        # 결과 요약
        if total_in:
            ratio = (1 - total_out / total_in) * 100
            summary = (f"완료: 성공 {ok} / 실패 {fail}\n\n"
                       f"전체 원본:   {human_size(total_in)}\n"
                       f"전체 압축본: {human_size(total_out)}\n"
                       f"전체 절감률: {ratio:.1f}%")
            status_line = (f"완료 — 성공 {ok}, 실패 {fail} · "
                           f"{human_size(total_in)} → {human_size(total_out)} "
                           f"({ratio:.1f}% 절감)")
        else:
            summary = f"완료: 성공 {ok} / 실패 {fail}"
            status_line = f"완료 — 성공 {ok}, 실패 {fail}"

        if errors:
            summary += "\n\n[실패 목록]\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                summary += f"\n... 외 {len(errors) - 10}건"

        self.set_status(status_line)

        def finish():
            self.running = False
            self.btn_run.config(state="normal", text="전체 압축 시작")
            if fail and not ok:
                messagebox.showerror("압축 실패", summary)
            else:
                messagebox.showinfo("압축 완료", summary)

        self.root.after(0, finish)


def main():
    root = tk.Tk()
    PDFCompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
