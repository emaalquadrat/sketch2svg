import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import os
import cv2
import numpy as np
import config_manager
import threading
import subprocess
import tempfile
import shutil
import json
from bs4 import BeautifulSoup
import ezdxf
import re
import csv

from skimage.morphology import skeletonize as sk_skeletonize
from svg.path import parse_path, Line, CubicBezier, QuadraticBezier, Arc # Importem tipus de segments per a parsing

# --- Colors Corporatius emaalquadrat Nexe ---
COLORS = {
    "Nexe_50": "#EFF1EF",
    "Nexe_100": "#DFE2DF",
    "Nexe_200": "#C4CAC4",
    "Nexe_300": "#A9B2A8",
    "Nexe_400": "#8F9A8D",
    "Nexe_500": "#80947E",
    "Nexe_600": "#5B6959",
    "Nexe_700": "#485346",
    "Nexe_800": "#343D34",
    "Nexe_900": "#242923",
    "Black": "#111111",
    "White": "#FFFFFF"
}

# --- Configuració de Tipografies Corporatives ---
FONTS = {
    "Title": ("Fraunces", 16, "bold"),
    "SectionTitle": ("Fraunces", 12, "bold"),
    "UI_Label": ("Inter", 10),
    "UI_Button": ("Inter", 10, "bold"),
    "UI_Small": ("Inter", 9),
    "UI_Tooltip": ("Inter", 8, "normal")
}

class Sketch2SVGApp:
    def __init__(self, master):
        self.master = master
        master.title("Sketch2SVG")
        master.geometry("1000x700")
        master.configure(bg=COLORS["Nexe_50"])

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=3)

        # --- Inicialització de totes les variables de control ---
        self.mode_var = tk.StringVar()
        self.batch_aggressive_var = tk.BooleanVar()
        self.preset_profile_var = tk.StringVar()

        self.bin_method_var = tk.StringVar()
        self.threshold_var = tk.IntVar()
        self.block_size_var = tk.IntVar()
        self.C_var = tk.IntVar()
        self.illum_sigma_var = tk.DoubleVar()
        self.clahe_var = tk.BooleanVar()
        self.median_filter_var = tk.BooleanVar()
        self.opening_radius_var = tk.IntVar()
        self.min_area_var = tk.IntVar()
        self.invert_var = tk.BooleanVar()

        self.prune_short_var = tk.DoubleVar()
        self.simplification_epsilon_var = tk.DoubleVar()
        self.stroke_mm_var = tk.DoubleVar()
        self.stitch_length_mm_var = tk.DoubleVar()

        self.dpi_var = tk.IntVar()
        self.scale_preset_var = tk.StringVar()
        self.scale_preset_options = [
            "Cap", "Alçada 20mm", "Alçada 25mm", "Alçada 30mm",
            "Amplada 20mm", "Amplada 25mm", "Amplada 30mm"
        ]
        self.scale_preset_values = {
            "Cap": None,
            "Alçada 20mm": ("height", 20),
            "Alçada 25mm": ("height", 25),
            "Alçada 30mm": ("height", 30),
            "Amplada 20mm": ("width", 20),
            "Amplada 25mm": ("width", 25),
            "Amplada 30mm": ("width", 30),
        }
        # --- Fi de la inicialització de variables de control ---


        # --- Frame esquerre per controls (Panell de configuració) ---
        self.canvas = tk.Canvas(master, bg=COLORS["Nexe_50"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.control_frame = ttk.Frame(self.canvas, padding="15")
        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.control_frame, anchor="nw")

        self.scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=0, sticky="nse", padx=10, pady=10)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.control_frame.bind("<Configure>", self._on_frame_configure)
        
        self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind_all("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind_all("<Button-5>", self._on_mouse_wheel)
        
        self.control_frame.grid_rowconfigure(99, weight=1)
        
        self.control_frame.grid_columnconfigure(0, weight=2) 
        self.control_frame.grid_columnconfigure(1, weight=3)
        self.control_frame.grid_columnconfigure(2, weight=0, minsize=50)


        ttk.Label(self.control_frame, text="Controls de Sketch2SVG", font=FONTS["Title"], foreground=COLORS["Nexe_800"]).grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="ew")

        self.add_section_title(self.control_frame, "Configuració General", 1)

        ttk.Label(self.control_frame, text="Perfil d'ús (Preset):").grid(row=2, column=0, sticky="w", pady=(5,0), columnspan=2)
        preset_names = list(config_manager.PRESETS.keys())
        self.preset_profile_var.set(preset_names[0])
        self.preset_profile_menu = ttk.OptionMenu(self.control_frame, self.preset_profile_var, self.preset_profile_var.get(), *preset_names, command=self.apply_preset)
        self.preset_profile_menu.grid(row=2, column=2, sticky="ew", padx=5)
        
        self.reset_profile_button = ttk.Button(self.control_frame, text="Restaurar configuració del perfil", command=self.reset_current_profile_settings)
        self.reset_profile_button.grid(row=3, column=0, columnspan=3, pady=(5, 15), sticky="ew")

        ttk.Label(self.control_frame, text="Carpeta d'esbossos:").grid(row=4, column=0, sticky="w", pady=(5,0), columnspan=3)
        self.folder_path_label = ttk.Label(self.control_frame, text="Cap carpeta seleccionada", wraplength=350, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"])
        self.folder_path_label.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5)
        self.select_folder_button = ttk.Button(self.control_frame, text="Tria carpeta...", command=self.select_folder)
        self.select_folder_button.grid(row=6, column=0, columnspan=3, pady=(5, 15), sticky="ew")

        ttk.Label(self.control_frame, text="Mode de vectorització:").grid(row=7, column=0, sticky="w", pady=5, columnspan=3)
        self.outline_radio = ttk.Radiobutton(self.control_frame, text="Contorn omplert (per Extrusió 3D / Tall Làser)", variable=self.mode_var, value="outline", command=self.update_parameters_visibility)
        self.outline_radio.grid(row=8, column=0, sticky="w", columnspan=3)
        self.centerline_radio = ttk.Radiobutton(self.control_frame, text="Traç únic (per Gravat Làser / Plotter / Brodat)", variable=self.mode_var, value="centerline", command=self.update_parameters_visibility)
        self.centerline_radio.grid(row=9, column=0, sticky="w", columnspan=3)

        self.batch_aggressive_check = ttk.Checkbutton(self.control_frame, text="Mode Batch agressiu (Força paràmetres més durs)", variable=self.batch_aggressive_var, command=self.preview_image)
        self.batch_aggressive_check.grid(row=10, column=0, columnspan=3, sticky="w", pady=(10, 20))

        self.add_section_title(self.control_frame, "Preprocés d'Imatge (Correcció de la imatge d'entrada)", 11)
        self.create_image_preprocessing_controls(self.control_frame, 12)

        # --- Panell de Paràmetres de Traç Únic (Centerline) ---
        self.centerline_params_frame = ttk.LabelFrame(self.control_frame, text="Paràmetres Traç Únic (Esquelet del dibuix)", padding="10")
        self.centerline_params_frame.grid_columnconfigure(0, weight=2)
        self.centerline_params_frame.grid_columnconfigure(1, weight=3)
        self.centerline_params_frame.grid_columnconfigure(2, weight=0, minsize=50)

        self.add_slider(self.centerline_params_frame, "Poda segments curts (px):", self.prune_short_var, 0, 50, 0.5, row=0, tooltip="Elimina les línies de l'esquelet molt petites o sorolloses, que podrien ser errors o detalls indesitjats. Utilitza valors baixos per mantenir els detalls.")
        self.add_slider(self.centerline_params_frame, "Simplificació línies ε (px):", self.simplification_epsilon_var, 0, 10, 0.1, row=1, tooltip="Simplifica les línies del dibuix eliminant punts redundants. Un valor més alt crea línies més suaus però menys precises. Ajuda a reduir la complexitat de l'SVG.")
        self.add_slider(self.centerline_params_frame, "Gruix de traç (mm):", self.stroke_mm_var, 0.01, 2.0, 0.01, row=2, tooltip="Defineix el gruix de la línia per a la visualització al fitxer SVG final. Aquest valor és només per mostrar el dibuix, no afecta el procés de vectorització.")
        self.add_slider(self.centerline_params_frame, "Llargada de punt (mm):", self.stitch_length_mm_var, 0.1, 5.0, 0.1, row=3, tooltip="Llargada mitjana de cada punt de brodat. Afecta la densitat dels punts exportats al CSV. Valors més petits generen més punts i més detall.")

        # --- Panell de Unitats SVG ---
        self.add_section_title(self.control_frame, "Unitats i Escalats SVG (Mida del resultat)", 90)
        self.create_svg_units_controls(self.control_frame, 91)

        # --- Secció d'Accions ---
        self.add_section_title(self.control_frame, "Accions", 95)
        self.export_button = ttk.Button(self.control_frame, text="Exporta lot a SVG", command=self.export_batch)
        self.export_button.grid(row=96, column=0, columnspan=3, pady=(5, 10), sticky="ew")

        # --- Frame dret per previsualització i missatges ---
        self.preview_frame = ttk.Frame(master, relief="sunken", padding="10", width=600, height=600, style="Preview.TFrame")
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        self.preview_label = ttk.Label(self.preview_frame, text="Selecciona una carpeta amb imatges d'esbossos per començar.", background=COLORS["White"], anchor="center", justify="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Barra d'estat
        self.status_bar = ttk.Label(master, text="Estat: Esperant...", relief=tk.SUNKEN, anchor=tk.W, background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"])
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.image_files = []
        self.current_image_index = -1
        self.display_image_data = None

        self._load_initial_config()
    
    def _on_canvas_configure(self, event):
        """Actualitza la mida de la finestra del frame dins del canvas quan el canvas canvia de mida."""
        self.canvas.itemconfig(self.canvas_frame_id, width=self.canvas.winfo_width())

    def _on_frame_configure(self, event):
        """Actualitza la regió de scroll del canvas quan el frame de controls canvia de mida."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mouse_wheel(self, event):
        """Gestiona els esdeveniments de la rodeta del ratolí per al scroll."""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _load_initial_config(self, initial_load=True):
        """Carrega la configuració guardada o la per defecte i l'aplica a les variables de control."""
        settings = config_manager.load_config()
        
        self.mode_var.set(settings.get("mode_var", config_manager.DEFAULT_STANDARD_SETTINGS["mode_var"]))
        self.batch_aggressive_var.set(settings.get("batch_aggressive_var", config_manager.DEFAULT_STANDARD_SETTINGS["batch_aggressive_var"]))
        
        self.bin_method_var.set(settings.get("bin_method_var", config_manager.DEFAULT_STANDARD_SETTINGS["bin_method_var"]))
        self.threshold_var.set(settings.get("threshold_var", config_manager.DEFAULT_STANDARD_SETTINGS["threshold_var"]))
        self.block_size_var.set(settings.get("block_size_var", config_manager.DEFAULT_STANDARD_SETTINGS["block_size_var"]))
        self.C_var.set(settings.get("C_var", config_manager.DEFAULT_STANDARD_SETTINGS["C_var"]))
        self.illum_sigma_var.set(settings.get("illum_sigma_var", config_manager.DEFAULT_STANDARD_SETTINGS["illum_sigma_var"]))
        self.clahe_var.set(settings.get("clahe_var", config_manager.DEFAULT_STANDARD_SETTINGS["clahe_var"]))
        self.median_filter_var.set(settings.get("median_filter_var", config_manager.DEFAULT_STANDARD_SETTINGS["median_filter_var"]))
        self.opening_radius_var.set(settings.get("opening_radius_var", config_manager.DEFAULT_STANDARD_SETTINGS["opening_radius_var"]))
        self.min_area_var.set(settings.get("min_area_var", config_manager.DEFAULT_STANDARD_SETTINGS["min_area_var"]))
        self.invert_var.set(settings.get("invert_var", config_manager.DEFAULT_STANDARD_SETTINGS["invert_var"]))

        self.prune_short_var.set(settings.get("prune_short_var", config_manager.DEFAULT_STANDARD_SETTINGS["prune_short_var"]))
        self.simplification_epsilon_var.set(settings.get("simplification_epsilon_var", config_manager.DEFAULT_STANDARD_SETTINGS["simplification_epsilon_var"]))
        self.stroke_mm_var.set(settings.get("stroke_mm_var", config_manager.DEFAULT_STANDARD_SETTINGS["stroke_mm_var"]))
        self.stitch_length_mm_var.set(settings.get("stitch_length_mm_var", config_manager.DEFAULT_STANDARD_SETTINGS["stitch_length_mm_var"]))

        last_preset = settings.get("last_preset_profile", list(config_manager.PRESETS.keys())[0])
        self.preset_profile_var.set(last_preset)

        last_folder = settings.get("last_folder", "")
        if os.path.isdir(last_folder):
            self.folder_path_label.config(text=last_folder)
            self.image_files = [os.path.join(last_folder, f) for f in os.listdir(last_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')) and not f.startswith('.')]
            self.image_files.sort()
            if self.image_files:
                self.current_image_index = 0
                self.status_bar.config(text=f"Carpeta carregada. Trobades {len(self.image_files)} imatges.")
                self.apply_preset(self.preset_profile_var.get())
            else:
                self.status_bar.config(text="Carpeta carregada, però no s'han trobat imatges suportades.")
                self.preview_label.config(image='', text="Selecciona una carpeta amb imatges d'esbossos per començar.")
                self.display_image_data = None
                self.folder_path_label.config(text="Cap carpeta seleccionada")
        else:
            self.folder_path_label.config(text="Cap carpeta seleccionada")
            self.apply_preset(self.preset_profile_var.get())

    def _get_current_settings(self):
        """Recull la configuració actual de la UI en un diccionari."""
        settings = {
            "mode_var": self.mode_var.get(),
            "batch_aggressive_var": self.batch_aggressive_var.get(),
            "bin_method_var": self.bin_method_var.get(),
            "threshold_var": self.threshold_var.get(),
            "block_size_var": self.block_size_var.get(),
            "C_var": self.C_var.get(),
            "illum_sigma_var": self.illum_sigma_var.get(),
            "clahe_var": self.clahe_var.get(),
            "median_filter_var": self.median_filter_var.get(),
            "opening_radius_var": self.opening_radius_var.get(),
            "min_area_var": self.min_area_var.get(),
            "invert_var": self.invert_var.get(),
            "prune_short_var": self.prune_short_var.get(),
            "simplification_epsilon_var": self.simplification_epsilon_var.get(),
            "stroke_mm_var": self.stroke_mm_var.get(),
            "stitch_length_mm_var": self.stitch_length_mm_var.get(),
            "dpi_var": self.dpi_var.get(),
            "scale_preset_var": self.scale_preset_var.get(),
            "last_folder": self.folder_path_label.cget("text") if "Cap carpeta seleccionada" not in self.folder_path_label.cget("text") else "",
            "last_preset_profile": self.preset_profile_var.get()
        }
        return settings

    def on_closing(self):
        """Accions a realitzar en tancar la finestra (guardar configuració)."""
        self.status_bar.config(text="Guardant configuració...")
        self.master.update_idletasks()
        config_manager.save_config(self._get_current_settings())
        self.status_bar.config(text="Configuració guardada. Tancant aplicació.")
        self.master.after(500, self.master.destroy)

    def apply_preset(self, preset_name=None):
        """Aplica la configuració d'un preset seleccionat al GUI."""
        if preset_name is None:
            preset_name = self.preset_profile_var.get()

        settings_to_apply = config_manager.get_preset_settings(preset_name)

        self.mode_var.set(settings_to_apply.get("mode_var", self.mode_var.get()))
        self.batch_aggressive_var.set(settings_to_apply.get("batch_aggressive_var", self.batch_aggressive_var.get()))
        
        self.bin_method_var.set(settings_to_apply.get("bin_method_var", self.bin_method_var.get()))
        self.threshold_var.set(settings_to_apply.get("threshold_var", self.threshold_var.get()))
        self.block_size_var.set(settings_to_apply.get("block_size_var", self.block_size_var.get()))
        self.C_var.set(settings_to_apply.get("C_var", self.C_var.get()))
        self.illum_sigma_var.set(settings_to_apply.get("illum_sigma_var", self.illum_sigma_var.get()))
        self.clahe_var.set(settings_to_apply.get("clahe_var", self.clahe_var.get()))
        self.median_filter_var.set(settings_to_apply.get("median_filter_var", self.median_filter_var.get()))
        self.opening_radius_var.set(settings_to_apply.get("opening_radius_var", self.opening_radius_var.get()))
        self.min_area_var.set(settings_to_apply.get("min_area_var", self.min_area_var.get()))
        self.invert_var.set(settings_to_apply.get("invert_var", self.invert_var.get()))

        self.prune_short_var.set(settings_to_apply.get("prune_short_var", self.prune_short_var.get()))
        self.simplification_epsilon_var.set(settings_to_apply.get("simplification_epsilon_var", self.simplification_epsilon_var.get()))
        self.stroke_mm_var.set(settings_to_apply.get("stroke_mm_var", self.stroke_mm_var.get()))
        self.stitch_length_mm_var.set(settings_to_apply.get("stitch_length_mm_var", self.stitch_length_mm_var.get()))

        self.dpi_var.set(settings_to_apply.get("dpi_var", self.dpi_var.get()))
        self.scale_preset_var.set(settings_to_apply.get("scale_preset_var", self.scale_preset_var.get()))

        self.update_parameters_visibility()
        self.preview_image()
        self.status_bar.config(text=f"Preset '{preset_name}' aplicat.")

    def reset_current_profile_settings(self):
        """Restaurar els paràmetres de preprocessament i vectorització al preset actual."""
        current_preset_name = self.preset_profile_var.get()
        self.apply_preset(current_preset_name)


    def add_section_title(self, parent_frame, title_text, row):
        """Afegeix un títol de secció amb un separador."""
        ttk.Label(parent_frame, text=title_text, font=FONTS["SectionTitle"], foreground=COLORS["Nexe_700"]).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(15, 0)
        )
        ttk.Separator(parent_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="sEW", pady=(5,0)
        )
        ttk.Frame(parent_frame, height=10).grid(row=row+1, column=0, columnspan=3, sticky="ew")


    def add_slider(self, parent_frame, label_text, var_obj, from_, to, resolution, row, tooltip=""):
        """Afegeix un label, slider i entrada per un paràmetre."""
        ttk.Label(parent_frame, text=label_text).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 5))
        
        vcmd = (parent_frame.register(self._validate_entry), '%P', '%V', str(from_), str(to), var_obj._name)
        
        slider = ttk.Scale(parent_frame, from_=from_, to=to, orient="horizontal", variable=var_obj, command=lambda s: (var_obj.set(round(float(s) / resolution) * resolution), self.preview_image()), style="Nexe.Horizontal.TScale")
        slider.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        
        entry = ttk.Entry(parent_frame, textvariable=var_obj, width=8, style="Parameter.TEntry", validate="focusout", validatecommand=vcmd)
        entry.grid(row=row, column=2, sticky="w", padx=5, pady=2)

        if tooltip:
            self.create_tooltip(slider, tooltip) 
            self.create_tooltip(entry, tooltip)

    def _validate_entry(self, P, V, from_val_str, to_val_str, var_name):
        from_val = float(from_val_str)
        to_val = float(to_val_str)

        if V == 'focusout':
            if P == "":
                self.status_bar.config(text="Estat: Esperant...")
                return True
            
            try:
                val = float(P)

                if not (from_val <= val <= to_val):
                    self.status_bar.config(text=f"Error: El valor ha d'estar entre {from_val_str} i {to_val_str} per a '{var_name.replace('_var', '')}'.")
                    return False
                
                var_obj = getattr(self, var_name)
                if isinstance(var_obj, tk.IntVar):
                    var_obj.set(int(val))
                elif isinstance(var_obj, tk.DoubleVar):
                    var_obj.set(val)
                
                self.preview_image()
                self.status_bar.config(text="Estat: Esperant...")
                return True
            except ValueError:
                self.status_bar.config(text="Error: Entrada no vàlida (només números).")
                return False
        return True


    def create_tooltip(self, widget, text):
        """Crea un tooltip per a un widget."""
        toolTip = ToolTip(widget, text)


    def create_image_preprocessing_controls(self, parent_frame, start_row):
        """Crea els controls per al preprocessament d'imatge, reordenats."""
        row_offset = 0

        self.add_slider(parent_frame, "Correcció il·luminació (nitidesa fons):", self.illum_sigma_var, 1, 200, 1, start_row + row_offset, tooltip="Ajusta la suavitat amb què es calcula el fons de la imatge. Valors alts fan que el fons sigui més suau, ajudant a corregir il·luminació irregular i a fer el traçat més net.")
        row_offset += 1

        ttk.Checkbutton(parent_frame, text="Activar Filtre Median (reducció de soroll)", variable=self.median_filter_var, command=self.preview_image).grid(row=start_row + row_offset, column=0, sticky="w", columnspan=3)
        row_offset += 1

        ttk.Checkbutton(parent_frame, text="Activar CLAHE (millora de contrast adaptatiu)", variable=self.clahe_var, command=self.preview_image).grid(row=start_row + row_offset, column=0, sticky="w", columnspan=3)
        row_offset += 1

        ttk.Label(parent_frame, text="Tipus de Binarització:").grid(row=start_row + row_offset, column=0, sticky="w", pady=(10,0), columnspan=3)
        row_offset += 1
        ttk.Radiobutton(parent_frame, text="Adaptativa (per fotos amb llum irregular)", variable=self.bin_method_var, value="adaptive", command=self.preview_image).grid(row=start_row + row_offset, column=0, sticky="w", columnspan=3)
        row_offset += 1
        ttk.Radiobutton(parent_frame, text="Global (per dibuixos amb llum uniforme)", variable=self.bin_method_var, value="global", command=self.preview_image).grid(row=start_row + row_offset, column=0, sticky="w", columnspan=3)
        row_offset += 1

        self.add_slider(parent_frame, "Llindar Global (Fosc vs. Clar):", self.threshold_var, 0, 255, 1, start_row + row_offset, tooltip="Ajusta el punt on la imatge es divideix entre blanc i negre. Els valors més baixos fan que el dibuix sigui més 'fosc' (més píxels negres), i els valors més alts el fan més 'clar'.")
        row_offset += 1
        self.add_slider(parent_frame, "Mida de l'àrea (adaptatiu):", self.block_size_var, 3, 51, 2, start_row + row_offset, tooltip="Només per a binarització adaptativa. Defineix la mida de l'àrea que es mira per decidir si un punt és blanc o negre. Valors més grans consideren més fons; valors més petits s'adapten més als canvis locals.")
        row_offset += 1
        self.add_slider(parent_frame, "Ajust del contrast (adaptatiu):", self.C_var, -10, 10, 1, start_row + row_offset, tooltip="Només per a binarització adaptativa. Un valor negatiu fa la imatge més clara al voltant dels traços; un valor positiu la fa més fosca i ressalta més els detalls.")
        row_offset += 1

        ttk.Checkbutton(parent_frame, text="Invertir colors (si el fons no és blanc)", variable=self.invert_var, command=self.preview_image).grid(row=start_row + row_offset, column=0, sticky="w", columnspan=3, pady=(10,0))
        row_offset += 1

        self.add_slider(parent_frame, "Radi 'Obertura' (neteja):", self.opening_radius_var, 0, 10, 1, start_row + row_offset, tooltip="Elimina petits punts aïllats ('soroll') i buits molt petits dins dels traços. Un radi més gran elimina més soroll, però també pot esborrar detalls fins.")
        row_offset += 1
        self.add_slider(parent_frame, "Mín. àrea objecte (px):", self.min_area_var, 0, 1000, 10, start_row + row_offset, tooltip="Elimina qualsevol 'taca' o objecte binaritzat la mida del qual sigui inferior a aquest valor en píxels. Ajuda a netejar els petits errors del fons.")
        row_offset += 1


    def create_svg_units_controls(self, parent_frame, start_row):
        """Crea els controls per a les unitats SVG."""
        self.add_slider(parent_frame, "Resolució DPI (imatge original):", self.dpi_var, 50, 200, 1, start_row, tooltip="Píxels per polzada (Dots Per Inch) de la imatge original. Afecta l'escala final de l'SVG: una DPI més alta implica un dibuix més gran en mil·límetres.")

        ttk.Label(parent_frame, text="Mida final (escala):").grid(row=start_row+1, column=0, sticky="w", padx=(0, 5))
        self.scale_preset_menu = ttk.OptionMenu(parent_frame, self.scale_preset_var, self.scale_preset_options[0], *self.scale_preset_options, command=lambda _: self.preview_image())
        self.scale_preset_menu.grid(row=start_row+1, column=1, columnspan=2, sticky="ew", padx=5)


    def update_parameters_visibility(self, event=None):
        """Actualitza la visibilitat dels controls segons el mode seleccionat."""
        if self.mode_var.get() == "centerline":
            self.centerline_params_frame.grid(row=80, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        else:
            self.centerline_params_frame.grid_forget()
        self.preview_image()


    def select_folder(self):
        """Obre un diàleg per seleccionar una carpeta amb imatges."""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_label.config(text=folder_selected)
            self.image_files = [os.path.join(folder_selected, f) for f in os.listdir(folder_selected) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')) and not f.startswith('.')]
            self.image_files.sort()
            if self.image_files:
                self.current_image_index = 0
                self.status_bar.config(text=f"Carpeta seleccionada. Trobades {len(self.image_files)} imatges.")
                self.preview_image()
            else:
                self.status_bar.config(text="Carpeta seleccionada, però no s'han trobat imatges suportades.")
                self.preview_label.config(image='', text="Selecciona una carpeta amb imatges d'esbossos per començar.")
                self.display_image_data = None
                self.folder_path_label.config(text="Cap carpeta seleccionada")


    def _process_image_for_preview(self, image_path):
        """Processa una imatge amb els paràmetres de preprocessament i la retorna binaritzada."""
        try:
            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                raise ValueError(f"No es pot carregar la imatge: {image_path}. Format no vàlid o arxiu corrupte.")

            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            if self.median_filter_var.get():
                img_gray = cv2.medianBlur(img_gray, 5)

            sigma = self.illum_sigma_var.get()
            if sigma > 0:
                blurred_background = cv2.GaussianBlur(img_gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
                blurred_background = np.where(blurred_background == 0, 1, blurred_background)
                img_normalized = cv2.divide(img_gray, blurred_background, scale=255)
                img_gray = img_normalized.astype(np.uint8)

            if self.clahe_var.get():
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                img_gray = clahe.apply(img_gray)

            bin_method = self.bin_method_var.get()
            if bin_method == "adaptive":
                block_size = self.block_size_var.get()
                C = self.C_var.get()
                if block_size % 2 == 0: block_size += 1
                if block_size < 3: block_size = 3
                img_binarized = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C)
            else: # global
                threshold = self.threshold_var.get()
                _, img_binarized = cv2.threshold(img_gray, threshold, 255, cv2.THRESH_BINARY)
            
            if self.invert_var.get():
                img_binarized = cv2.bitwise_not(img_binarized)

            opening_radius = self.opening_radius_var.get()
            if opening_radius > 0:
                kernel_size = opening_radius * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                img_binarized = cv2.morphologyEx(img_binarized, cv2.MORPH_OPEN, kernel)

            min_area = self.min_area_var.get()
            if min_area > 0:
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(img_binarized, 8, cv2.CV_32S)
                output_image = np.zeros_like(img_binarized)
                for i in range(1, num_labels):
                    area = stats[i, cv2.CC_STAT_AREA]
                    if area >= min_area:
                        output_image[labels == i] = 255
                img_binarized = output_image

            return img_binarized

        except Exception as e:
            self.status_bar.config(text=f"Error en processar la imatge: {e}")
            return None


    def _update_preview_display(self, processed_img_np, image_path):
        """Actualitza la visualització de la previsualització al fil principal."""
        if processed_img_np is not None:
            img_pil = Image.fromarray(processed_img_np)

            self.master.update_idletasks()
            max_width = self.preview_frame.winfo_width() - 20 
            max_height = self.preview_frame.winfo_height() - 20 
            
            if max_width <= 0 or max_height <= 0:
                max_width = 600
                max_height = 600

            img_width, img_height = img_pil.size
            if img_width > max_width or img_height > max_height:
                ratio = min(max_width / img_width, max_height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                img_pil = img_pil.resize((new_width, new_height), Image.LANCZOS)
            
            self.display_image_data = ImageTk.PhotoImage(img_pil)
            self.preview_label.config(image=self.display_image_data)
            self.preview_label.image = self.display_image_data
            self.preview_label.config(text="")
            self.status_bar.config(text=f"Previsualització de {os.path.basename(image_path)} actualitzada.")

        else:
            self.preview_label.config(image='', text="Error en la previsualització o imatge no suportada.")
            self.display_image_data = None

    def preview_image(self):
        """Inicia el processament de la imatge en un fil separat i actualitza la UI."""
        if not self.image_files or self.current_image_index == -1:
            self.status_bar.config(text="No hi ha imatge per previsualitzar. Selecciona una carpeta.")
            self.preview_label.config(image='', text="Selecciona una carpeta amb imatges d'esbossos per començar.")
            self.display_image_data = None
            return

        image_path = self.image_files[self.current_image_index]
        self.status_bar.config(text=f"Previsualitzant: {os.path.basename(image_path)} (Processant en segon pla...)")
        self.preview_label.config(image='', text="Processant imatge...")

        thread = threading.Thread(target=self._process_and_update_thread, args=(image_path,))
        thread.daemon = True
        thread.start()

    def _process_and_update_thread(self, image_path):
        """Funció que s'executa en un fil separat per processar la imatge."""
        processed_img_np = self._process_image_for_preview(image_path)
        self.master.after(0, self._update_preview_display, processed_img_np, image_path)

    def _vectorize_outline_potrace(self, binarized_image_np, output_svg_path, original_image_name):
        """
        Vectoritza una imatge binaritzada a SVG utilitzant Potrace.
        Retorna els camins (polígons) de l'SVG per a l'exportació DXF.
        """
        self.status_bar.config(text=f"Vectoritzant {original_image_name} amb Potrace...")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".pbm", delete=False) as temp_pbm_file:
                temp_pbm_path = temp_pbm_file.name
                
                img_for_potrace = binarized_image_np
                if np.mean(img_for_potrace) > 127:
                    img_for_potrace = cv2.bitwise_not(img_for_potrace)

                pil_img = Image.fromarray(img_for_potrace)
                pil_img.save(temp_pbm_path)

            potrace_command = [
                "potrace",
                temp_pbm_path,
                "-s",
                "-o", output_svg_path
            ]
            
            result = subprocess.run(potrace_command, capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                self.status_bar.config(text=f"Vectorització de {original_image_name} completada amb èxit.")
                
                with open(output_svg_path, 'r') as f:
                    svg_content = f.read()
                soup = BeautifulSoup(svg_content, 'xml')
                paths_svg = []
                for path_tag in soup.find_all('path'):
                    d_attr = path_tag.get('d')
                    if d_attr:
                        parsed_path = parse_path(d_attr)
                        current_path_points = []
                        for segment in parsed_path:
                            if hasattr(segment, 'start'):
                                current_path_points.append((segment.start.real, segment.start.imag))
                            
                            if isinstance(segment, (Line, CubicBezier, QuadraticBezier, Arc)):
                                if isinstance(segment, Line):
                                    if hasattr(segment, 'end') and (segment.end.real, segment.end.imag) != current_path_points[-1]:
                                        current_path_points.append((segment.end.real, segment.end.imag))
                                else:
                                    num_samples = 10
                                    for t in np.linspace(0, 1, num_samples):
                                        point_at_t = segment.point(t)
                                        current_path_points.append((point_at_t.real, point_at_t.imag))
                            elif hasattr(segment, 'end'):
                                current_path_points.append((segment.end.real, segment.end.imag))
                        
                        unique_points = []
                        if current_path_points:
                            unique_points.append(current_path_points[0])
                            for i in range(1, len(current_path_points)):
                                if abs(current_path_points[i][0] - unique_points[-1][0]) > 1e-6 or \
                                   abs(current_path_points[i][1] - unique_points[-1][1]) > 1e-6:
                                    unique_points.append(current_path_points[i])

                        if unique_points:
                            paths_svg.append(unique_points)
                            print(f"DEBUG Potrace: Parsed path with {len(unique_points)} unique points.")
                        else:
                            print(f"DEBUG Potrace: Path had d_attr but no valid unique points parsed.")
                print(f"DEBUG Potrace: Final paths_svg count: {len(paths_svg)}")
                return True, paths_svg
            else:
                self.status_bar.config(text=f"Error en vectoritzar {original_image_name} amb Potrace: {result.stderr}")
                return False, []

        except FileNotFoundError:
            self.status_bar.config(text="Error: Potrace no trobat. Assegura't que està instal·lat i al PATH.")
            return False, []
        except subprocess.CalledProcessError as e:
            self.status_bar.config(text=f"Error de Potrace per {original_image_name}: {e.stderr.strip()}")
            return False, []
        except Exception as e:
            self.status_bar.config(text=f"Error inesperat en vectoritzar {original_image_name}: {e}")
            return False, []
        finally:
            if 'temp_pbm_path' in locals() and os.path.exists(temp_pbm_path):
                os.remove(temp_pbm_path)

    def _vectorize_centerline(self, binarized_image_np, output_svg_path, original_image_name):
        """
        Vectoritza una imatge binaritzada a SVG amb traç únic (centerline) utilitzant esqueletització i seguiment de línies.
        Retorna els camins (polilínies) per a l'exportació DXF i CSV.
        """
        self.status_bar.config(text=f"Vectoritzant {original_image_name} amb traç únic (centerline)...")
        print(f"DEBUG Centerline: Iniciant vectorització per a {original_image_name}")

        try:
            if self.invert_var.get():
                skel_image = (binarized_image_np == 255)
            else:
                skel_image = (binarized_image_np == 0)

            print(f"DEBUG Centerline: Imatge per esqueletitzar: {skel_image.shape}, dtype: {skel_image.dtype}")
            skeleton = sk_skeletonize(skel_image)
            print(f"DEBUG Centerline: Esqueletització completada. Píxels True: {np.sum(skeleton)}")
            
            paths = []
            visited = np.zeros_like(skeleton, dtype=bool)
            
            skel_points = np.argwhere(skeleton)
            print(f"DEBUG Centerline: Punts d'esquelet trobats: {len(skel_points)}")

            for r, c in skel_points:
                if not visited[r, c]:
                    current_path = []
                    queue = [(r, c)]
                    visited[r, c] = True

                    while queue:
                        curr_r, curr_c = queue.pop(0)
                        current_path.append((curr_c, curr_r))

                        neighbors = []
                        for dr in [-1, 0, 1]:
                            for dc in [-1, 0, 1]:
                                if dr == 0 and dc == 0: continue
                                nr, nc = curr_r + dr, curr_c + dc
                                if 0 <= nr < skeleton.shape[0] and 0 <= nc < skeleton.shape[1] and \
                                   skeleton[nr, nc] and not visited[nr, nc]:
                                    neighbors.append((nr, nc))
                        
                        if len(neighbors) == 1:
                            next_r, next_c = neighbors[0]
                            queue.append((next_r, next_c))
                            visited[next_r, next_c] = True
                        else:
                            pass

                    if len(current_path) > 1:
                        paths.append(current_path)
            print(f"DEBUG Centerline: Camins bruts (abans de poda/simplificació): {len(paths)}")

            prune_short = self.prune_short_var.get()
            if prune_short > 0:
                filtered_paths = []
                for path in paths:
                    length = 0
                    for i in range(len(path) - 1):
                        p1 = np.array(path[i])
                        p2 = np.array(path[i+1])
                        length += np.linalg.norm(p2 - p1)
                    if length >= prune_short:
                        filtered_paths.append(path)
                paths = filtered_paths
                print(f"DEBUG Centerline: Camins després de poda ({prune_short}px): {len(paths)}")


            epsilon = self.simplification_epsilon_var.get()
            if epsilon > 0:
                simplified_paths = []
                for path in paths:
                    if len(path) > 1:
                        simplified_path = self._ramer_douglas_peucker(path, epsilon)
                        if len(simplified_path) > 1 or (len(simplified_path) == 1 and not np.allclose(path[0], path[-1])):
                           simplified_paths.append(simplified_path)
                        else:
                           print(f"DEBUG Centerline: RDP simplified path to a degenerate segment, discarding.")
                    else:
                        simplified_paths.append(path)
                paths = simplified_paths
                print(f"DEBUG Centerline: Camins després de simplificació ({epsilon}px): {len(paths)}")

            if not paths:
                print("DEBUG Centerline: No s'han trobat camins vàlids després del processament.")
                self.status_bar.config(text=f"Avís: No s'han trobat camins per a {original_image_name} en mode traç únic.")
                return False, []

            img_height, img_width = binarized_image_np.shape
            stroke_width_mm = self.stroke_mm_var.get()
            dpi = self.dpi_var.get()
            scale_preset_tuple = self.scale_preset_values.get(self.scale_preset_var.get())
            
            target_width_mm = None
            target_height_mm = None
            if scale_preset_tuple and scale_preset_tuple[0] == "width":
                target_width_mm = scale_preset_tuple[1]
            elif scale_preset_tuple and scale_preset_tuple[0] == "height":
                target_height_mm = scale_preset_tuple[1]

            stroke_color = "#0000FF"

            self._create_svg_from_paths(output_svg_path, paths, img_width, img_height, dpi, stroke_width_mm, stroke_color, target_width_mm, target_height_mm)
            
            self.status_bar.config(text=f"Vectorització de {original_image_name} amb traç únic completada amb èxit.")
            return True, paths

        except Exception as e:
            self.status_bar.config(text=f"Error en vectoritzar {original_image_name} amb traç únic: {e}")
            print(f"DEBUG Centerline: ERROR en vectorització: {e}")
            return False, []

    def _create_svg_from_paths(self, output_svg_path, paths, img_width_px, img_height_px, dpi, stroke_width_mm, stroke_color, target_width_mm=None, target_height_mm=None):
        mm_per_px = 25.4 / dpi

        final_width_px = img_width_px
        final_height_px = img_height_px

        if target_width_mm is not None and img_width_px > 0:
            scale_factor = (target_width_mm / mm_per_px) / img_width_px
            final_width_px = img_width_px * scale_factor
            final_height_px = img_height_px * scale_factor
        elif target_height_mm is not None and img_height_px > 0:
            scale_factor = (target_height_mm / mm_per_px) / img_height_px
            final_width_px = img_width_px * scale_factor
            final_height_px = img_height_px * scale_factor
        
        svg_width_mm = final_width_px * mm_per_px
        svg_height_mm = final_height_px * mm_per_px

        svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
   width="{svg_width_mm:.2f}mm"
   height="{svg_height_mm:.2f}mm"
   viewBox="0 0 {img_width_px} {img_height_px}"
   version="1.1"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:svg="http://www.w3.org/2000/svg">
  <g
     inkscape:label="Layer 1"
     inkscape:groupmode="layer"
     id="layer1">
"""
        for path_points in paths:
            points_str = " ".join([f"{x},{y}" for x, y in path_points])
            if stroke_color == "#000000" or stroke_color == "black":
                 svg_content += f'    <path d="M{points_str}Z" style="fill:{stroke_color};stroke:none;" />\n'
            else:
                 svg_content += f'    <polyline points="{points_str}" style="fill:none;stroke:{stroke_color};stroke-width:{stroke_width_mm:.3f}mm" />\n'
        
        svg_content += """  </g>\n</svg>"""

        with open(output_svg_path, 'w') as f:
            f.write(svg_content)

    def _ramer_douglas_peucker(self, points, epsilon):
        print(f"DEBUG RDP: Called with {len(points)} points, epsilon={epsilon}")
        points_np = np.array(points)

        # Base case: A path with 0 or 1 point cannot be simplified.
        # A path with 2 points is a line segment, which is already simplified.
        if len(points_np) < 2:
            print(f"DEBUG RDP: Base case (len < 2), returning {len(points_np)} points.")
            return points

        # If start and end points are identical (degenerate segment)
        # This covers cases where a segment collapses to a single point.
        if np.allclose(points_np[0], points_np[-1]):
            print(f"DEBUG RDP: Degenerate segment (start == end), returning single point.")
            return [points[0]]

        if len(points_np) == 2:
            print(f"DEBUG RDP: Base case (len == 2), returning 2 points.")
            return points


        dmax = 0.0
        index = 0
        end_idx = len(points_np) - 1
        
        p_start = points_np[0]
        p_end = points_np[end_idx]
        line_segment_vec = p_end - p_start
        line_length_sq = np.dot(line_segment_vec, line_segment_vec)

        print(f"DEBUG RDP: Segment from {p_start} to {p_end}. Length squared: {line_length_sq}")

        # CRITICAL CHECK: Safeguard against division by zero for *sub-segments*
        # This is the most likely place where line_length_sq could be zero for a sub-segment.
        if line_length_sq < 1e-12: # Use a small tolerance for floating point zero
            print(f"DEBUG RDP: line_length_sq is near zero ({line_length_sq}), returning start point only.")
            return [points[0]] # Return just the start point to avoid division by zero

        for i in range(1, end_idx):
            point_vec = points_np[i] - p_start
            
            t = np.dot(point_vec, line_segment_vec) / line_length_sq # Division happens here
            
            if t < 0.0:
                closest_point_on_line = p_start
            elif t > 1.0:
                closest_point_on_line = p_end
            else:
                closest_point_on_line = p_start + t * line_segment_vec
            
            d = np.linalg.norm(points_np[i] - closest_point_on_line)
            
            if d > dmax:
                index = i
                dmax = d

        print(f"DEBUG RDP: Max distance {dmax} at index {index}. Epsilon: {epsilon}")

        if dmax > epsilon:
            print(f"DEBUG RDP: dmax > epsilon. Recursing on sub-segments.")
            rec_results1 = self._ramer_douglas_peucker(points[0:index+1], epsilon)
            rec_results2 = self._ramer_douglas_peucker(points[index:end_idx+1], epsilon)

            # Reconstruct the result, avoiding duplicate point at the join
            # Check if results are not empty before accessing last/first element
            if rec_results1 and rec_results2 and np.allclose(rec_results1[-1], rec_results2[0]):
                result_points = rec_results1[:-1] + rec_results2
            else:
                result_points = rec_results1 + rec_results2
            print(f"DEBUG RDP: Recurse result len: {len(result_points)}")
        else:
            print(f"DEBUG RDP: dmax <= epsilon. Simplifying to start and end points.")
            result_points = [points[0], points[end_idx]]

        return result_points


    def _export_dxf_from_svg_paths(self, output_dxf_path, paths, img_width_px, img_height_px, dpi, layer_name, dxf_color):
        self.status_bar.config(text=f"Exportant DXF a {os.path.basename(output_dxf_path)}...")
        print(f"DEBUG: Intentant exportar DXF a {output_dxf_path} per a la capa {layer_name} amb color {dxf_color}.")
        print(f"DEBUG: Número de camins per DXF: {len(paths)}")

        try:
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()

            doc.layers.new(layer_name, dxfattribs={'color': dxf_color})

            mm_per_px = 25.4 / dpi

            for path_points in paths:
                dxf_points = [(p[0] * mm_per_px, p[1] * mm_per_px) for p in path_points]

                if len(dxf_points) > 1:
                    is_closed = (len(dxf_points) > 2 and np.allclose(dxf_points[0], dxf_points[-1]))
                    
                    if is_closed:
                        msp.add_lwpolyline(dxf_points, dxfattribs={'layer': layer_name, 'closed': True})
                        print(f"DEBUG: Afegit LWPOLYLINE tancada amb {len(dxf_points)} punts.")
                    else:
                        msp.add_lwpolyline(dxf_points, dxfattribs={'layer': layer_name})
                        print(f"DEBUG: Afegit LWPOLYLINE oberta amb {len(dxf_points)} punts.")
                else:
                    print(f"DEBUG: Camí massa curt per a DXF: {len(dxf_points)} punts, saltant.")
                        
            doc.saveas(output_dxf_path)
            self.status_bar.config(text=f"DXF de {os.path.basename(output_dxf_path)} generat amb èxit.")
            print(f"DEBUG: DXF guardat amb èxit a {output_dxf_path}")
            return True
        except Exception as e:
            self.status_bar.config(text=f"Error en exportar DXF de {os.path.basename(output_dxf_path)}: {e}")
            print(f"DEBUG: ERROR en exportar DXF: {e}")
            return False

    def _export_csv_from_paths(self, output_csv_path, paths, img_width_px, img_height_px, dpi, stitch_length_mm):
        self.status_bar.config(text=f"Exportant CSV de punts a {os.path.basename(output_csv_path)}...")
        print(f"DEBUG: Intentant exportar CSV a {output_csv_path}.")
        print(f"DEBUG: Número de camins per CSV: {len(paths)}")

        mm_per_px = 25.4 / dpi

        try:
            with open(output_csv_path, 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(['X_mm', 'Y_mm']) # Capçalera

                total_points = 0
                for path_points in paths:
                    for x_px, y_px in path_points:
                        x_mm = x_px * mm_per_px
                        y_mm = y_px * mm_per_px
                        csv_writer.writerow([f"{x_mm:.3f}", f"{y_mm:.3f}"])
                        total_points += 1
            
            self.status_bar.config(text=f"CSV de {os.path.basename(output_csv_path)} generat amb èxit ({total_points} punts).")
            print(f"DEBUG: CSV guardat amb èxit a {output_csv_path} amb {total_points} punts.")
            return True
        except Exception as e:
            self.status_bar.config(text=f"Error en exportar CSV de {os.path.basename(output_csv_path)}: {e}")
            print(f"DEBUG: ERROR en exportar CSV: {e}")
            return False


    def _scale_svg(self, svg_path, target_width_mm, target_height_mm, dpi):
        try:
            with open(svg_path, 'r') as f:
                svg_content = f.read()

            soup = BeautifulSoup(svg_content, 'xml')
            svg_tag = soup.find('svg')

            if not svg_tag:
                raise ValueError("No s'ha trobat l'etiqueta <svg> al fitxer.")

            original_width_px = None
            original_height_px = None
            
            if 'viewBox' in svg_tag.attrs:
                _, _, original_width_px_str, original_height_px_str = svg_tag['viewBox'].split()
                original_width_px = float(original_width_px_str)
                original_height_px = float(original_height_px_str)
            else:
                if 'width' in svg_tag.attrs and svg_tag['width'].endswith('px'):
                    original_width_px = float(svg_tag['width'][:-2])
                if 'height' in svg_tag.attrs and svg_tag['height'].endswith('px'):
                    original_height_px = float(svg_tag['height'][:-2])
            
            if original_width_px is None or original_height_px is None or original_width_px == 0 or original_height_px == 0:
                self.status_bar.config(text=f"Avís: No s'han pogut determinar les dimensions originals de l'SVG per escalar. No s'aplicarà l'escalat de mida.")
                return

            mm_per_px = 25.4 / dpi

            final_width_mm = original_width_px * mm_per_px
            final_height_mm = original_height_px * mm_per_px

            if target_width_mm is not None:
                scale_factor = target_width_mm / final_width_mm
                final_width_mm = target_width_mm
                final_height_mm *= scale_factor
            elif target_height_mm is not None:
                scale_factor = target_height_mm / final_height_mm
                final_height_mm = target_height_mm
                final_width_mm *= scale_factor
            
            svg_tag['width'] = f"{final_width_mm:.2f}mm"
            svg_tag['height'] = f"{final_height_mm:.2f}mm"
            
            if 'viewBox' not in svg_tag.attrs:
                svg_tag['viewBox'] = f"0 0 {original_width_px} {original_height_px}"

            with open(svg_path, 'w') as f:
                f.write(str(soup))
            
            self.status_bar.config(text=f"Escalat de {os.path.basename(svg_path)} aplicat.")

        except Exception as e:
            self.status_bar.config(text=f"Error en escalar SVG de {os.path.basename(svg_path)}: {e}")


    def export_batch(self):
        if not self.image_files:
            self.status_bar.config(text="Error: No hi ha imatges per exportar. Selecciona una carpeta.")
            return

        output_folder_base = self.folder_path_label.cget("text")
        if not output_folder_base or "Cap carpeta seleccionada" in output_folder_base:
            self.status_bar.config(text="Error: No s'ha seleccionat una carpeta d'entrada vàlida.")
            return

        output_dir = os.path.join(output_folder_base, "output_svg")
        os.makedirs(output_dir, exist_ok=True)

        self.status_bar.config(text=f"Exportant lot a {output_dir}...")
        self.export_button.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._export_batch_thread, args=(output_dir,))
        thread.daemon = True
        thread.start()

    def _update_status_bar_text(self, message):
        """Funció auxiliar per actualitzar la barra d'estat de forma segura des de qualsevol fil."""
        self.status_bar.config(text=message)
        self.master.update_idletasks() # Força l'actualització visual

    def _export_batch_thread(self, output_dir):
        results = []
        errors = []
        processed_count = 0
        total_files = len(self.image_files)

        for i, image_path in enumerate(self.image_files):
            original_image_name = os.path.basename(image_path)
            base_name, _ = os.path.splitext(original_image_name)
            
            self.master.after(0, self._update_status_bar_text, f"Processant {original_image_name} ({i+1}/{total_files})...")
            print(f"DEBUG: Iniciant processament de {original_image_name}")

            try:
                processed_img_np = self._process_image_for_preview(image_path)
                if processed_img_np is None:
                    errors.append(f"No s'ha pogut preprocessar {original_image_name}.")
                    print(f"DEBUG: Error preprocessant {original_image_name}. Saltant.")
                    continue

                mode = self.mode_var.get()
                output_svg_filename = f"{base_name}__{mode}.svg"
                output_svg_path = os.path.join(output_dir, output_svg_filename)
                
                vectorized_paths = []
                success_svg = False
                print(f"DEBUG: Mode seleccionat: {mode}")

                if mode == "outline":
                    success_svg, vectorized_paths = self._vectorize_outline_potrace(processed_img_np, output_svg_path, original_image_name)
                elif mode == "centerline":
                    success_svg, vectorized_paths = self._vectorize_centerline(processed_img_np, output_svg_path, original_image_name)
                
                if success_svg:
                    print(f"DEBUG: Vectorització SVG exitosa per {original_image_name}. Camins obtinguts: {len(vectorized_paths)}")
                    dpi = self.dpi_var.get()
                    scale_preset_tuple = self.scale_preset_values.get(self.scale_preset_var.get())
                    
                    target_width_mm = None
                    target_height_mm = None
                    if scale_preset_tuple and scale_preset_tuple[0] == "width":
                        target_width_mm = scale_preset_tuple[1]
                    elif scale_preset_tuple and scale_preset_tuple[0] == "height":
                        target_height_mm = scale_preset_tuple[1]

                    self._scale_svg(output_svg_path, target_width_mm, target_height_mm, dpi)
                    
                    current_preset = self.preset_profile_var.get()
                    export_dxf = False
                    export_csv = False
                    dxf_layer = ""
                    dxf_color = 0

                    print(f"DEBUG: Preset actual: '{current_preset}'")
                    if current_preset == "Làser - Tall (CUT)":
                        export_dxf = True
                        dxf_layer = "CUT"
                        dxf_color = 1
                        print("DEBUG: Preset és 'Làser - Tall (CUT)', export_dxf = True")
                    elif current_preset == "Làser - Marcat / Gravat (SCORE)":
                        export_dxf = True
                        dxf_layer = "SCORE"
                        dxf_color = 5
                        print("DEBUG: Preset és 'Làser - Marcat / Gravat (SCORE)', export_dxf = True")
                    elif current_preset == "Brodat (Running Stitch)":
                        export_csv = True
                        print("DEBUG: Preset és 'Brodat (Running Stitch)', export_csv = True")
                    else:
                        print("DEBUG: Preset no és de làser ni brodat, no s'exportarà DXF/CSV.")


                    if export_dxf and vectorized_paths:
                        output_dxf_filename = f"{base_name}__{mode}.dxf"
                        output_dxf_path = os.path.join(output_dir, output_dxf_filename)
                        print(f"DEBUG: Condició DXF complerta: export_dxf={export_dxf}, vectorized_paths té {len(vectorized_paths)} camins.")
                        self._export_dxf_from_svg_paths(output_dxf_path, vectorized_paths, processed_img_np.shape[1], processed_img_np.shape[0], dpi, dxf_layer, dxf_color)
                    elif export_dxf and not vectorized_paths:
                        print(f"DEBUG: Condició DXF no complerta: export_dxf={export_dxf}, vectorized_paths està buit.")
                        errors.append(f"No s'ha pogut generar DXF per {original_image_name}: No hi ha camins vectoritzats.")
                    
                    if export_csv and vectorized_paths:
                        output_csv_filename = f"{base_name}__{mode}.csv"
                        output_csv_path = os.path.join(output_dir, output_csv_filename)
                        print(f"DEBUG: Condició CSV complerta: export_csv={export_csv}, vectorized_paths té {len(vectorized_paths)} camins.")
                        self._export_csv_from_paths(output_csv_path, vectorized_paths, processed_img_np.shape[1], processed_img_np.shape[0], dpi, self.stitch_length_mm_var.get())
                    elif export_csv and not vectorized_paths:
                        print(f"DEBUG: Condició CSV no complerta: export_csv={export_csv}, vectorized_paths està buit.")
                        errors.append(f"No s'ha pogut generar CSV per {original_image_name}: No hi ha camins vectoritzats.")

                    results.append({"original": original_image_name, "output_svg": output_svg_path, "status": "OK"})
                    processed_count += 1
                else:
                    errors.append(f"Error en vectoritzar {original_image_name}.")
                    print(f"DEBUG: Vectorització SVG fallida per {original_image_name}.")

            except Exception as e:
                errors.append(f"Error crític processant {original_image_name}: {e}")
                self.master.after(0, self._update_status_bar_text, f"Error crític processant {original_image_name}: {e}")
                print(f"DEBUG: Excepció crítica en _export_batch_thread per {original_image_name}: {e}")

        self.master.after(0, self._finish_batch_export, processed_count, total_files, output_dir, results, errors)

    def _finish_batch_export(self, processed_count, total_files, output_dir, results, errors):
        self.export_button.config(state=tk.NORMAL)

        manifest_path = os.path.join(output_dir, "manifest.json")
        manifest_content = {
            "profile": self.preset_profile_var.get(),
            "parameters_applied": self._get_current_settings(),
            "input_folder": self.folder_path_label.cget("text"),
            "output_folder": output_dir,
            "processed_files": results,
            "failed_files": errors,
            "summary": f"Processats {processed_count} de {total_files} imatges. Errors: {len(errors)}."
        }
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest_content, f, indent=4)
            self.status_bar.config(text=f"Lot completat. {processed_count}/{total_files} OK. Manifest guardat a {output_dir}.")
        except Exception as e:
            self.status_bar.config(text=f"Lot completat, però error guardant manifest: {e}")
        
        # Opcional: Obrir la carpeta de sortida
        # import platform
        # if platform.system() == "Windows":
        #     os.startfile(output_dir)
        # elif platform.system() == "Linux":
        #     subprocess.Popen(["xdg-open", output_dir])
        # elif platform.system() == "Darwin": # macOS
        #     subprocess.Popen(["open", output_dir])


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x_root = self.widget.winfo_rootx()
        y_root = self.widget.winfo_rooty()
        width = self.widget.winfo_width()
        height = self.widget.winfo_height()

        x = x_root + width + 5
        y = y_root + height + 5

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip_window, text=self.text, background=COLORS["Nexe_50"], relief="solid", borderwidth=1, font=FONTS["UI_Tooltip"], fg=COLORS["Nexe_900"])
        label.pack(padx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')

    style.configure(".", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])

    style.configure("TButton",
                    font=FONTS["UI_Button"],
                    background=COLORS["Nexe_500"],
                    foreground=COLORS["White"],
                    padding=6,
                    relief="flat",
                    focusthickness=0,
                    focuscolor='none')
    style.map("TButton",
              background=[('active', COLORS["Nexe_600"]), ('pressed', COLORS["Nexe_700"])],
              foreground=[('active', COLORS["White"]), ('pressed', COLORS["White"])])

    style.configure("TLabel",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    
    style.configure("TRadiobutton",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    style.configure("TCheckbutton",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    
    style.configure("Parameter.TEntry",
                    fieldbackground=COLORS["White"],
                    foreground=COLORS["Nexe_900"])
    
    style.configure("Nexe.Horizontal.TScale",
                    background=COLORS["Nexe_50"],
                    troughcolor=COLORS["Nexe_200"],
                    sliderthickness=15,
                    relief="flat")
    style.map("Nexe.Horizontal.TScale",
              background=[('active', COLORS["Nexe_300"])])
    
    style.configure("Preview.TFrame", background=COLORS["Nexe_100"])
    
    style.configure("TLabelframe", background=COLORS["Nexe_50"], foreground=COLORS["Nexe_800"])
    style.configure("TLabelframe.Label", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])

    style.configure("TMenubutton",
                    background=COLORS["Nexe_100"],
                    foreground=COLORS["Nexe_800"],
                    arrowcolor=COLORS["Nexe_800"])
    style.map("TMenubutton",
              background=[('active', COLORS["Nexe_200"])])


    app = Sketch2SVGApp(root)
    root.mainloop()
