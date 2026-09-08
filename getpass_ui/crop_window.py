"""Редактор кадрирования фотографии для бейджа."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from getpass_core.crop import compute_crop_from_state
from getpass_core.dpi import fit_to_screen, scaled

from .widgets import F

#: желаемый размер области просмотра; ужимается, если экран меньше
CANVAS_W, CANVAS_H = 700, 700
#: минимальный зум = 1.0: фото обязано полностью закрывать рамку кадра
MIN_SCALE, MAX_SCALE = 1.0, 6.0
#: сколько по высоте занимают панели кнопок и подсказка
CHROME_H = 250


def open_crop_window(parent, image_path, on_apply, scale=1.0):
    try:
        im = Image.open(image_path).convert("RGB")
    except Exception as exc:
        messagebox.showerror("Ошибка", f"Не удалось открыть фото:\n{exc}", parent=parent)
        return None
    return CropWindow(parent, im, on_apply, scale)


class CropWindow:
    def __init__(self, parent, im, on_apply, scale=1.0):
        self.im = im
        self.on_apply = on_apply
        self.orig_w, self.orig_h = im.size

        self.win = tk.Toplevel(parent)
        self.win.title("Кадрирование — колесо мыши: масштаб, ЛКМ: перемещение")
        self.win.transient(parent)
        self.win.configure(bg="#22303C")

        # Раньше окно было жёстко 760x920. На ноутбуке с рабочей областью
        # ниже этого нижняя панель с кнопками «Сохранить и применить»
        # уезжала под панель задач и добраться до неё было нельзя.
        want_w = scaled(760, scale)
        want_h = scaled(CANVAS_H + CHROME_H, scale)
        win_w, win_h = fit_to_screen(parent, want_w, want_h, margin=100)
        self.canvas_w = max(320, win_w - scaled(60, scale))
        self.canvas_h = max(320, win_h - scaled(CHROME_H, scale))
        self.win.geometry(f"{win_w}x{win_h}")
        self.win.minsize(min(win_w, scaled(560, scale)), min(win_h, scaled(520, scale)))
        self._center_on(parent, win_w, win_h)

        frame_h = int(self.canvas_h * 0.88)
        frame_w = int(frame_h * (3 / 4))
        if frame_w > self.canvas_w * 0.92:
            frame_w = int(self.canvas_w * 0.92)
            frame_h = int(frame_w * 4 / 3)
        self.frame_box = ((self.canvas_w - frame_w) // 2, (self.canvas_h - frame_h) // 2,
                          frame_w, frame_h)
        base_scale = max(frame_w / self.orig_w, frame_h / self.orig_h)
        self.state = {"scale": 1.0, "offset_x": 0, "offset_y": 0, "is_dragging": False,
                      "last_x": 0, "last_y": 0, "photo_tk": None, "base_scale": base_scale}

        self._build()
        self.win.grab_set()
        self.redraw()
        self.draw_frame_overlay()

    def _center_on(self, parent, win_w, win_h):
        """Разместить окно по центру родителя, не вылезая за края экрана."""
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            x = px + max(0, (pw - win_w) // 2)
            y = py + max(0, (ph - win_h) // 2)
            x = max(0, min(x, parent.winfo_screenwidth() - win_w))
            y = max(0, min(y, parent.winfo_screenheight() - win_h))
            self.win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        except Exception:
            pass

    def _build(self):
        self.btn_bar = tk.Frame(self.win, bg="#22303C")
        self.btn_bar.pack(side="bottom", fill="x", padx=16, pady=(6, 14))
        self.zoom_bar = tk.Frame(self.win, bg="#22303C")
        self.zoom_bar.pack(side="bottom", fill="x", padx=16, pady=4)
        tk.Label(self.win,
                 text="🖱 Колесо — масштаб  •  ЛКМ и тяните — перемещение  •  "
                      "Лицо должно быть в красной рамке",
                 bg="#22303C", fg="#E8EEF4", font=F(10)).pack(side="bottom", fill="x",
                                                              pady=(8, 4))
        self.c = tk.Canvas(self.win, width=self.canvas_w, height=self.canvas_h,
                           bg="#141A20", highlightthickness=0)
        self.c.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 0))
        self.zoom_lbl = tk.Label(self.win, text="Масштаб: 100%", bg="#22303C",
                                 fg="#FFD54F", font=F(10, True), width=16)

        self.c.bind("<MouseWheel>", self._on_wheel)
        self.c.bind("<Button-4>", lambda e: self.zoom(1.12))
        self.c.bind("<Button-5>", lambda e: self.zoom(0.89))
        self.c.bind("<ButtonPress-1>", self._on_press)
        self.c.bind("<B1-Motion>", self._on_drag)
        self.c.bind("<ButtonRelease-1>", self._on_release)

        for text, cmd, color in (("➖  Уменьшить", lambda: self.zoom(0.85), "#C0392B"),
                                 ("↺  Сброс", self.reset, "#546E7A"),
                                 ("➕  Увеличить", lambda: self.zoom(1.15), "#27AE60")):
            tk.Button(self.zoom_bar, text=text, command=cmd, bg=color, fg="white",
                      font=F(10, True), padx=12, pady=5, relief="flat",
                      cursor="hand2").pack(side="left", padx=3)
        self.zoom_lbl.pack(side="left", padx=10)

        tk.Button(self.btn_bar, text="💾  СОХРАНИТЬ И ПРИМЕНИТЬ", command=self.save_and_apply,
                  bg="#27AE60", fg="white", font=F(12, True), pady=11, relief="flat",
                  cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(self.btn_bar, text="📁  Сохранить как файл...", command=self.save_as_file,
                  bg="#1565C0", fg="white", font=F(11, True), pady=11, padx=14,
                  relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(self.btn_bar, text="❌  Отмена", command=self.win.destroy,
                  bg="#455A64", fg="white", font=F(11), pady=11, padx=14,
                  relief="flat", cursor="hand2").pack(side="right")

    # ------------------------------------------------------ рисование

    def redraw(self):
        self.c.delete("photo")
        cur = self.state["base_scale"] * self.state["scale"]
        sw = max(1, int(self.orig_w * cur))
        sh = max(1, int(self.orig_h * cur))
        try:
            disp = self.im.resize((sw, sh), Image.Resampling.LANCZOS)
            self.state["photo_tk"] = ImageTk.PhotoImage(disp)
            dx = self.canvas_w / 2 + self.state["offset_x"] - sw / 2
            dy = self.canvas_h / 2 + self.state["offset_y"] - sh / 2
            self.c.create_image(dx, dy, image=self.state["photo_tk"],
                                anchor="nw", tags="photo")
            self.c.tag_lower("photo")
        except Exception:
            pass
        self.zoom_lbl.config(text=f"Масштаб: {int(self.state['scale'] * 100)}%")

    def draw_frame_overlay(self):
        self.c.delete("frame")
        fx, fy, fw, fh = self.frame_box
        shade = "#0B1116"
        for box in ((0, 0, self.canvas_w, fy), (0, fy + fh, self.canvas_w, self.canvas_h),
                    (0, fy, fx, fy + fh), (fx + fw, fy, self.canvas_w, fy + fh)):
            self.c.create_rectangle(*box, fill=shade, stipple="gray50",
                                    outline="", tags="frame")
        self.c.create_rectangle(fx, fy, fx + fw, fy + fh, outline="#E53935",
                                width=4, tags="frame")
        for i in (1, 2):
            self.c.create_line(fx + i * fw / 3, fy, fx + i * fw / 3, fy + fh,
                               fill="#FFFFFF", width=1, tags="frame")
            self.c.create_line(fx, fy + i * fh / 3, fx + fw, fy + i * fh / 3,
                               fill="#FFFFFF", width=1, tags="frame")
        self.c.create_text(self.canvas_w // 2, max(14, fy - 18),
                           text="ОБЛАСТЬ ФОТО НА БЕЙДЖЕ (3:4)", fill="#FF8A80",
                           font=F(10, True), tags="frame")

    # ------------------------------------------------------- события

    def zoom(self, factor):
        self.state["scale"] = max(MIN_SCALE, min(self.state["scale"] * factor, MAX_SCALE))
        self.redraw()

    def reset(self):
        self.state.update({"scale": 1.0, "offset_x": 0, "offset_y": 0})
        self.redraw()

    def _on_wheel(self, event):
        self.zoom(1.12 if event.delta > 0 else 0.89)
        return "break"

    def _on_press(self, event):
        self.state.update({"is_dragging": True, "last_x": event.x, "last_y": event.y})

    def _on_drag(self, event):
        if self.state["is_dragging"]:
            self.state["offset_x"] += event.x - self.state["last_x"]
            self.state["offset_y"] += event.y - self.state["last_y"]
            self.state["last_x"], self.state["last_y"] = event.x, event.y
            self.redraw()

    def _on_release(self, _event):
        self.state["is_dragging"] = False

    # ------------------------------------------------------ сохранение

    def _crop(self):
        return compute_crop_from_state(self.im, self.orig_w, self.orig_h,
                                       self.state, self.frame_box,
                                       (self.canvas_w, self.canvas_h))

    def save_and_apply(self):
        cropped, box = self._crop()
        try:
            self.on_apply(cropped, box)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить кадр:\n{exc}",
                                 parent=self.win)
            return
        self.win.destroy()

    def save_as_file(self):
        cropped, box = self._crop()
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")],
            initialfile="foto_sotrudnika_3x4.jpg")
        if not path:
            return
        try:
            if path.lower().endswith(".png"):
                cropped.save(path, dpi=(300, 300))
            else:
                cropped.save(path, "JPEG", quality=95, dpi=(300, 300))
            messagebox.showinfo("Сохранено",
                                f"Фотография сохранена:\n{path}\n\n"
                                f"Размер кадра: {box[2]}×{box[3]} px (3:4)",
                                parent=self.win)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{exc}",
                                 parent=self.win)


def store_photo(cropped, photo_dir, tab_num=""):
    """Сохранить кадр в архив фотографий и вернуть путь.

    Раньше кадр писался в общий _temp_cropped_photo.jpg, который затирался
    следующим сотрудником — перевыпустить бейдж было невозможно.
    """
    os.makedirs(photo_dir, exist_ok=True)
    safe = "".join(ch for ch in (tab_num or "") if ch.isalnum()) or "photo"
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(photo_dir, f"{safe}_{stamp}.jpg")
    cropped.save(path, "JPEG", quality=95, dpi=(300, 300))
    return path
