"""Scrollable print preview with front/back selection and physical dimensions."""
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk, ImageDraw


def open_preview(parent, theme, front, back=None):
    win = theme.toplevel(parent, "Проверка перед печатью")
    win.geometry("1100x800")
    toolbar = ttk.Frame(win)
    toolbar.pack(fill="x", padx=12, pady=12)
    side = tk.StringVar(value="Лицевая")
    scale = tk.DoubleVar(value=30)
    dimensions = f"{front.width / 300 * 25.4:.1f} × {front.height / 300 * 25.4:.1f} мм · 300 dpi"
    ttk.Label(toolbar, text=dimensions).pack(side="left", padx=8)
    options = ttk.Combobox(toolbar, textvariable=side, state="readonly", width=15,
                          values=["Лицевая", "Оборотная"] if back else ["Лицевая"])
    options.pack(side="left", padx=8)
    canvas = tk.Canvas(win, bg="#d5d8dc", highlightthickness=0)
    vertical = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    horizontal = ttk.Scrollbar(win, orient="horizontal", command=canvas.xview)
    vertical.pack(side="right", fill="y")
    horizontal.pack(side="bottom", fill="x")
    canvas.pack(fill="both", expand=True)
    canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    def redraw(*_):
        source = back if side.get() == "Оборотная" and back is not None else front
        factor = scale.get() / 100
        image = source.resize((max(1, int(source.width * factor)), max(1, int(source.height * factor))))
        # A 5 mm guide; the actual printer's unprintable area may differ.
        margin = round(5 / 25.4 * 300 * factor)
        ImageDraw.Draw(image).rectangle((margin, margin, image.width-margin, image.height-margin),
                                        outline="#777777", width=1)
        photo = ImageTk.PhotoImage(image)
        canvas.delete("all")
        canvas.create_image(20, 20, image=photo, anchor="nw")
        canvas.image = photo
        canvas.configure(scrollregion=(0, 0, image.width + 40, image.height + 40))
    ttk.Scale(toolbar, from_=15, to=100, variable=scale, command=redraw).pack(side="right", padx=8)
    ttk.Label(toolbar, text="Масштаб · рамка 5 мм").pack(side="right")
    options.bind("<<ComboboxSelected>>", redraw)
    win.bind("<Escape>", lambda _: win.destroy())
    redraw()
