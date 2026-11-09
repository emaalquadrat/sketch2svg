# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
"""Sketch2SVG — interfície gràfica (Tkinter).

Tot el càlcul és a `nucli.py`; aquí només hi ha la finestra.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import config_manager
import nucli

COLORS = {"Nexe_50": "#EFF1EF", "Nexe_100": "#DFE2DF", "Nexe_200": "#C4CAC4", "Nexe_400": "#8F9A8D",
          "Nexe_500": "#80947E", "Nexe_600": "#5B6959", "Nexe_700": "#485346", "Nexe_800": "#343D34",
          "Nexe_900": "#242923", "White": "#FFFFFF"}
FONTS = {"Title": ("Fraunces", 16, "bold"), "SectionTitle": ("Fraunces", 12, "bold"), "UI_Label": ("Inter", 10),
         "UI_Button": ("Inter", 10, "bold"), "UI_Small": ("Inter", 9), "UI_Tooltip": ("Inter", 9)}

TITOL = f"Sketch2SVG {nucli.VERSIO} · Trama Maker"


def recurs(rel):
    """Ruta a un fitxer de l'aplicació (també dins d'un executable de PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def entorn_del_sistema():
    """Entorn per obrir programes del sistema des de l'executable empaquetat.

    PyInstaller canvia LD_LIBRARY_PATH perquè el programa trobi les seves
    llibreries; l'explorador de fitxers ha de fer servir les del sistema.
    """
    entorn = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = entorn.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            entorn["LD_LIBRARY_PATH"] = original
        else:
            entorn.pop("LD_LIBRARY_PATH", None)
    return entorn


class Sketch2SVGApp:
    def __init__(self, master):
        self.master = master
        master.title(TITOL)
        master.geometry("1100x750")
        master.minsize(850, 600)
        master.configure(bg=COLORS["Nexe_50"])
        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=0, minsize=400)
        master.grid_columnconfigure(1, weight=1)

        self.image_files = []
        self.current_image_index = -1
        self.folder = ""
        self.img_tk = None
        self._generacio = 0  # descarta previsualitzacions antigues

        self._init_vars()
        self._build_ui()
        self.master.after(100, self._load_initial_config)
        if not nucli.potrace_disponible():
            self.master.after(300, lambda: self.set_status(
                "Avís: no s'ha trobat «potrace». El mode Contorn no funcionarà fins que l'instal·lis."))

    # --- Variables -------------------------------------------------------------

    def _init_vars(self):
        d = config_manager.DEFAULT_STANDARD_SETTINGS
        tipus = {bool: tk.BooleanVar, int: tk.IntVar, float: tk.DoubleVar, str: tk.StringVar}
        self.var_names = [k for k in d if k.endswith("_var")]
        for nom in self.var_names:
            setattr(self, nom, tipus[type(d[nom])](value=d[nom]))
        self.preset_profile_var = tk.StringVar()
        self.vector_preview_var = tk.BooleanVar(value=True)

    def _params(self):
        """Còpia dels paràmetres actuals (es llegeix al fil principal)."""
        p = config_manager.get_default_standard_settings()
        for nom in self.var_names:
            try:
                p[nom] = getattr(self, nom).get()
            except (tk.TclError, ValueError):
                pass  # valor escrit a mig fer: mantenim el per defecte
        return p

    # --- Interfície -------------------------------------------------------------

    def _build_ui(self):
        esquerra = ttk.Frame(self.master)
        esquerra.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        esquerra.grid_rowconfigure(0, weight=1)
        esquerra.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(esquerra, bg=COLORS["Nexe_50"], highlightthickness=0, width=380)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(esquerra, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.control_frame = ttk.Frame(self.canvas, padding="15")
        finestra = self.canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.control_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(finestra, width=e.width))
        self._activa_roda(self.canvas)

        ttk.Label(self.control_frame, text="Sketch2SVG", font=FONTS["Title"], foreground=COLORS["Nexe_800"]).pack(fill="x")
        ttk.Label(self.control_frame, text="De l'esbós al vector", font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"]).pack(fill="x", pady=(0, 10))
        self._create_general_config_section()
        self._create_preprocessing_section()
        self._create_centerline_params_section()
        self._create_svg_units_section()
        self._create_actions_section()

        dreta = ttk.Frame(self.master, padding="10", style="Preview.TFrame")
        dreta.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        dreta.grid_rowconfigure(1, weight=1)
        dreta.grid_columnconfigure(0, weight=1)
        nav = ttk.Frame(dreta, style="Preview.TFrame")
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(nav, text="◀ Anterior", command=lambda: self.canvia_imatge(-1)).pack(side="left")
        ttk.Button(nav, text="Següent ▶", command=lambda: self.canvia_imatge(1)).pack(side="right")
        self.nom_imatge = ttk.Label(nav, text="", anchor="center", style="Preview.TLabel")
        self.nom_imatge.pack(side="left", fill="x", expand=True)
        self.preview_canvas = tk.Canvas(dreta, bg=COLORS["White"], highlightthickness=0)
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.create_text(20, 20, anchor="nw", text="Tria una carpeta amb fotos d'esbossos per començar.", fill=COLORS["Nexe_800"])
        self.preview_canvas.bind("<Configure>", lambda e: self.preview_image())
        self.master.bind("<Left>", lambda e: self.canvia_imatge(-1))
        self.master.bind("<Right>", lambda e: self.canvia_imatge(1))

        self.status_bar = ttk.Label(self.master, text="Estat: esperant...", relief=tk.SUNKEN, anchor=tk.W,
                                    background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"], padding=(6, 3))
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _activa_roda(self, widget):
        def roda(e):
            if e.num == 4:
                pas = -1
            elif e.num == 5:
                pas = 1
            else:
                pas = -1 if e.delta > 0 else 1
            self.canvas.yview_scroll(pas, "units")

        def entra(_):
            self.master.bind_all("<MouseWheel>", roda)
            self.master.bind_all("<Button-4>", roda)
            self.master.bind_all("<Button-5>", roda)

        def surt(_):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.master.unbind_all(seq)

        widget.bind("<Enter>", entra)
        widget.bind("<Leave>", surt)

    def _add_section_title(self, parent, text):
        ttk.Label(parent, text=text, font=FONTS["SectionTitle"], foreground=COLORS["Nexe_700"]).pack(fill="x", pady=(15, 2), anchor="w")
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 5))

    def _create_general_config_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor="w")
        self._add_section_title(frame, "Configuració general")
        ttk.Label(frame, text="Perfil d'ús:").pack(fill="x")
        noms = config_manager.get_preset_names()
        ttk.OptionMenu(frame, self.preset_profile_var, noms[0], *noms, command=self.apply_preset).pack(fill="x", pady=(0, 5))
        ttk.Button(frame, text="Restaura els valors del perfil", command=self.reset_current_profile_settings).pack(fill="x", pady=(0, 10))
        ttk.Button(frame, text="Tria la carpeta d'esbossos...", command=self.select_folder).pack(fill="x")
        self.folder_path_label = ttk.Label(frame, text="Cap carpeta seleccionada", wraplength=340, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"])
        self.folder_path_label.pack(fill="x", pady=2)
        ttk.Label(frame, text="Mode de vectorització:").pack(fill="x", pady=(10, 2))
        ttk.Radiobutton(frame, text="Contorn (tall làser, modelat 3D)", variable=self.mode_var, value="outline", command=self.update_parameters_visibility).pack(anchor="w")
        ttk.Radiobutton(frame, text="Traç únic (gravat, plotter, brodat)", variable=self.mode_var, value="centerline", command=self.update_parameters_visibility).pack(anchor="w")
        ttk.Checkbutton(frame, text="Només la silueta exterior (tall làser)", variable=self.silhouette_var, command=self.preview_image).pack(anchor="w", pady=(5, 0))

    def _create_preprocessing_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor="w")
        self._add_section_title(frame, "Preprocés d'imatge")
        self.add_slider(frame, "Correcció il·luminació:", self.illum_sigma_var, 0, 200, 1, "Compensa les ombres i la llum desigual de la foto. 0 = desactivat.")
        ttk.Checkbutton(frame, text="Filtre de mediana (redueix soroll)", variable=self.median_filter_var, command=self.preview_image).pack(anchor="w")
        ttk.Checkbutton(frame, text="CLAHE (millora el contrast)", variable=self.clahe_var, command=self.preview_image).pack(anchor="w")
        ttk.Label(frame, text="Tipus de binarització:").pack(fill="x", pady=(10, 2))
        ttk.Radiobutton(frame, text="Combinada (recomanada: llapis fluix i traç gruixut)", variable=self.bin_method_var, value="combinat", command=self.preview_image).pack(anchor="w")
        ttk.Radiobutton(frame, text="Automàtica (traç fosc i net)", variable=self.bin_method_var, value="otsu", command=self.preview_image).pack(anchor="w")
        ttk.Radiobutton(frame, text="Adaptativa (traços molt fins, llum molt desigual)", variable=self.bin_method_var, value="adaptive", command=self.preview_image).pack(anchor="w")
        ttk.Radiobutton(frame, text="Global (escanejats nets)", variable=self.bin_method_var, value="global", command=self.preview_image).pack(anchor="w")
        self.add_slider(frame, "Llindar global:", self.threshold_var, 0, 255, 1, "Nivell de gris que separa traç i fons (només binarització global).")
        self.add_slider(frame, "Mida de la zona:", self.block_size_var, 3, 51, 2, "Mida de la regió per calcular el llindar adaptatiu.")
        self.add_slider(frame, "Contrast (adapt.):", self.C_var, -20, 20, 1, "Valors alts deixen menys traç; baixos, més.")
        ttk.Checkbutton(frame, text="Inverteix colors (traç clar sobre fons fosc)", variable=self.invert_var, command=self.preview_image).pack(anchor="w", pady=(10, 0))
        self.add_slider(frame, "Neteja (obertura):", self.opening_radius_var, 0, 10, 1, "Elimina punts de soroll petits. Valors alts poden trencar traços fins.")
        self.add_slider(frame, "Àrea mínima:", self.min_area_var, 0, 1000, 10, "Elimina taques més petites que aquests píxels.")

    def _create_centerline_params_section(self):
        self.centerline_params_frame = ttk.Frame(self.control_frame)
        self._add_section_title(self.centerline_params_frame, "Paràmetres de traç únic")
        self.add_slider(self.centerline_params_frame, "Poda traços curts (px):", self.prune_short_var, 0, 50, 0.5, "Elimina línies més curtes que aquesta llargada.")
        self.add_slider(self.centerline_params_frame, "Simplificació (px):", self.simplification_epsilon_var, 0, 10, 0.1, "Treu punts redundants. 0 = sense simplificar.")
        self.add_slider(self.centerline_params_frame, "Gruix del traç (mm):", self.stroke_mm_var, 0.01, 2.0, 0.01, "Gruix de la línia a l'SVG.")
        self.add_slider(self.centerline_params_frame, "Llargada puntada (mm):", self.stitch_length_mm_var, 0.1, 5.0, 0.1, "Distància entre puntades al CSV de brodat.")

    def _create_svg_units_section(self):
        self.units_frame = ttk.Frame(self.control_frame)
        self.units_frame.pack(fill="x", pady=5, anchor="w")
        self._add_section_title(self.units_frame, "Mida del resultat")
        self.add_slider(self.units_frame, "Resolució (DPI):", self.dpi_var, 50, 600, 1, "Píxels per polzada de la foto. Només s'usa si l'escala és «Cap».")
        ttk.Label(self.units_frame, text="Mida final:").pack(anchor="w")
        opcions = list(nucli.ESCALES)
        ttk.OptionMenu(self.units_frame, self.scale_preset_var, opcions[0], *opcions).pack(fill="x")

    def _create_actions_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor="w")
        self._add_section_title(frame, "Accions")
        ttk.Checkbutton(frame, text="Mostra els vectors sobre la imatge", variable=self.vector_preview_var, command=self.preview_image).pack(anchor="w", pady=5)
        self.export_button = ttk.Button(frame, text="Exporta totes les imatges", command=self.export_batch)
        self.export_button.pack(fill="x", pady=10, ipady=5)
        ttk.Label(frame, text="Els fitxers es desen a la subcarpeta «output_vector».", wraplength=340, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"]).pack(fill="x")

    def add_slider(self, parent_frame, label_text, var_obj, from_, to, resolution, tooltip=""):
        f = ttk.Frame(parent_frame)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label_text, width=22).pack(side="left")
        entry = ttk.Entry(f, textvariable=var_obj, width=6)
        entry.pack(side="right", padx=(5, 0))
        scale = ttk.Scale(f, from_=from_, to=to, orient="horizontal",
                          command=lambda s: var_obj.set(round(from_ + round((float(s) - from_) / resolution) * resolution, 3)))
        scale.pack(side="right", fill="x", expand=True)
        var_obj.trace_add("write", lambda *a: self._sincronitza_scale(scale, var_obj))
        entry.bind("<FocusOut>", lambda e: self.preview_image(), "+")
        entry.bind("<Return>", lambda e: self.preview_image(), "+")
        scale.bind("<ButtonRelease-1>", lambda e: self.preview_image(), "+")
        if tooltip:
            ToolTip(f, tooltip)

    @staticmethod
    def _sincronitza_scale(scale, var_obj):
        try:
            scale.set(float(var_obj.get()))
        except (tk.TclError, ValueError):
            pass

    # --- Configuració -------------------------------------------------------------

    def set_status(self, text):
        self.status_bar.config(text=text)

    def on_closing(self):
        config_manager.save_config(self._get_current_settings())
        self.master.destroy()

    def apply_preset(self, preset_name=None):
        if preset_name is None:
            preset_name = self.preset_profile_var.get()
        for key, value in config_manager.get_preset_settings(preset_name).items():
            if key in self.var_names:
                getattr(self, key).set(value)
        self.update_parameters_visibility()

    def _load_initial_config(self):
        settings = config_manager.load_config()
        noms = config_manager.get_preset_names()
        preset = settings.get("last_preset_profile")
        self.preset_profile_var.set(preset if preset in noms else noms[0])
        self.apply_preset()
        last_folder = settings.get("last_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self.select_folder(last_folder)

    def _get_current_settings(self):
        settings = self._params()
        settings["last_folder"] = self.folder
        settings["last_preset_profile"] = self.preset_profile_var.get()
        return settings

    def reset_current_profile_settings(self):
        self.apply_preset()

    def update_parameters_visibility(self):
        if self.mode_var.get() == "centerline":
            self.centerline_params_frame.pack(fill="x", pady=5, anchor="w", before=self.units_frame)
        else:
            self.centerline_params_frame.pack_forget()
        self.preview_image()

    # --- Imatges i previsualització --------------------------------------------------

    def select_folder(self, folder_path=None):
        if folder_path is None:
            folder_path = filedialog.askdirectory()
        if not folder_path or not os.path.isdir(folder_path):
            return
        self.folder = folder_path
        self.folder_path_label.config(text=folder_path)
        self.image_files = nucli.llista_imatges(folder_path)
        if self.image_files:
            self.current_image_index = 0
            self.preview_image()
        else:
            self.current_image_index = -1
            self.nom_imatge.config(text="")
            self.set_status("No hi ha cap imatge (PNG, JPG, BMP, TIFF) a la carpeta.")

    def canvia_imatge(self, pas):
        if self.image_files:
            self.current_image_index = (self.current_image_index + pas) % len(self.image_files)
            self.preview_image()

    def preview_image(self):
        if not self.image_files:
            return
        path = self.image_files[self.current_image_index]
        self.nom_imatge.config(text=f"{os.path.basename(path)}  ({self.current_image_index + 1}/{len(self.image_files)})")
        self._generacio += 1
        params = self._params()
        mostra_vectors = self.vector_preview_var.get()
        self.set_status(f"Processant {os.path.basename(path)}...")
        threading.Thread(target=self._process_and_update_thread,
                         args=(path, params, mostra_vectors, self._generacio), daemon=True).start()

    def _process_and_update_thread(self, path, params, mostra_vectors, generacio):
        img, camins, error = None, [], None
        try:
            img = nucli.preprocessa(nucli.llegeix_gris(path), params)
            if mostra_vectors:
                camins, _ = nucli.vectoritza(img, params)
        except nucli.Sketch2SVGError as e:
            error = str(e)
        except Exception as e:  # noqa: BLE001 — l'error s'ensenya a la barra d'estat
            error = f"Error inesperat: {e}"
        self.master.after(0, self._update_preview_display, img, path, camins, error, generacio)

    def _update_preview_display(self, img_np, path, vector_paths, error, generacio):
        if generacio != self._generacio:
            return  # ja s'ha demanat una previsualització més nova
        self.preview_canvas.delete("all")
        if img_np is None:
            self.preview_canvas.create_text(20, 20, anchor="nw", text=error or "Error", fill="#B00020", width=500)
            self.set_status(error or "Error")
            return
        cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        if cw < 20 or ch < 20:
            return
        ih, iw = img_np.shape
        ratio = min((cw - 20) / iw, (ch - 20) / ih)
        dw, dh = max(1, int(iw * ratio)), max(1, int(ih * ratio))
        # Mostrem el traç en negre sobre blanc, com es veurà el resultat.
        visible = Image.fromarray(255 - img_np).resize((dw, dh), Image.LANCZOS)
        if vector_paths:
            visible = visible.point(lambda v: 200 + v * 55 // 255)  # traç més clar per veure els vectors
        self.img_tk = ImageTk.PhotoImage(visible)
        self.preview_canvas.create_image(cw / 2, ch / 2, anchor="center", image=self.img_tk)
        ox, oy = (cw - dw) / 2, (ch - dh) / 2
        for cami in vector_paths:
            punts = [coord for x, y in cami for coord in (x * ratio + ox, y * ratio + oy)]
            if len(punts) >= 4:
                self.preview_canvas.create_line(punts, fill="#D1006F", width=1.5)
        text = f"Previsualitzant {os.path.basename(path)}"
        if vector_paths:
            text += f" · {len(vector_paths)} camins"
        if error:
            text = error
        self.set_status(text)

    # --- Exportació ----------------------------------------------------------------

    def export_batch(self):
        if not self.image_files:
            self.set_status("Primer tria una carpeta amb imatges.")
            return
        params = self._params()
        if params["mode_var"] == "outline" and not nucli.potrace_disponible():
            messagebox.showerror(TITOL, "Per al mode Contorn cal instal·lar «potrace».\n\n"
                                        "Linux: sudo apt install potrace\n"
                                        "Windows: potrace.sourceforge.net (afegeix-lo al PATH)")
            return
        output_dir = os.path.join(self.folder, "output_vector")
        self.export_button.config(state=tk.DISABLED)
        threading.Thread(target=self._export_batch_thread,
                         args=(list(self.image_files), params, self.preset_profile_var.get(), output_dir),
                         daemon=True).start()

    def _export_batch_thread(self, fitxers, params, preset, output_dir):
        fets, errors = 0, []
        for i, path in enumerate(fitxers, 1):
            nom = os.path.basename(path)
            self.master.after(0, self.set_status, f"Exportant {i}/{len(fitxers)}: {nom}")
            try:
                nucli.processa_fitxer(path, params, output_dir, preset)
                fets += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"{nom}: {e}")
        self.master.after(0, self._finish_batch_export, fets, len(fitxers), output_dir, errors)

    def _finish_batch_export(self, fets, total, out_dir, errors):
        self.export_button.config(state=tk.NORMAL)
        self.set_status(f"Exportació acabada: {fets}/{total} imatges a {out_dir}")
        if errors:
            messagebox.showwarning(TITOL, "Algunes imatges no s'han pogut convertir:\n\n" + "\n".join(errors[:10]))
        if fets:
            try:
                if sys.platform == "win32":
                    os.startfile(out_dir)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", out_dir])
                else:
                    subprocess.Popen(["xdg-open", out_dir], env=entorn_del_sistema())
            except Exception:  # noqa: BLE001 — obrir la carpeta és opcional
                pass


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip, "+")
        widget.bind("<Leave>", self.hide_tip, "+")

    def show_tip(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip_window, text=self.text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID,
                 borderwidth=1, font=FONTS["UI_Tooltip"], wraplength=300).pack(ipadx=4, ipady=4)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None


def aplica_estil(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TButton", font=FONTS["UI_Button"], background=COLORS["Nexe_500"], foreground=COLORS["White"],
                    padding=6, relief="flat", focusthickness=0, focuscolor="none")
    style.map("TButton", background=[("active", COLORS["Nexe_600"]), ("pressed", COLORS["Nexe_700"])])
    style.configure("TEntry", fieldbackground=COLORS["White"], foreground=COLORS["Nexe_900"])
    style.configure("TScale", troughcolor=COLORS["Nexe_200"])
    style.configure("Preview.TFrame", background=COLORS["Nexe_100"])
    style.configure("Preview.TLabel", background=COLORS["Nexe_100"])
    style.configure("TMenubutton", background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"], arrowcolor=COLORS["Nexe_800"])


def main():
    root = tk.Tk(className="Sketch2SVG")
    try:
        root.iconphoto(True, tk.PhotoImage(file=recurs(os.path.join("icons", "trama_pont_2d.png"))))
    except tk.TclError:
        pass  # la icona és opcional
    aplica_estil(root)
    Sketch2SVGApp(root)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Amb arguments, el mateix executable fa de versió de terminal
        # (així es pot provar l'executable empaquetat sense obrir la finestra).
        if sys.stdout is None:  # executable de Windows sense consola
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")
        import cli
        sys.exit(cli.main())
    main()
