import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import os
import cv2
import numpy as np
import config_manager
import threading
import subprocess # Per executar Potrace
import tempfile   # Per crear fitxers temporals
import shutil     # Per netejar fitxers/carpetes

# --- Colors Corporatius emaalquadrat Nexe ---
COLORS = {
    "Nexe_50": "#EFF1EF",
    "Nexe_100": "#DFE2DF",
    "Nexe_200": "#C4CAC4",
    "Nexe_300": "#A9B2A8",
    "Nexe_400": "#8F9A8D",
    "Nexe_500": "#80947E", # Color base
    "Nexe_600": "#5B6959",
    "Nexe_700": "#485346",
    "Nexe_800": "#343D34",
    "Nexe_900": "#242923",
    "Black": "#111111", # Per contrast amb fons clars
    "White": "#FFFFFF"  # Per contrast amb fons foscos
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

        self.dpi_var = tk.IntVar()
        self.scale_preset_var = tk.StringVar()
        self.scale_preset_options = ["Cap", "Alçada 20mm", "Alçada 25mm", "Alçada 30mm", "Amplada 20mm", "Amplada 25mm", "Amplada 30mm"]
        self.scale_preset_values = {
            "none": None, "Alçada 20mm": ("height", 20), "Alçada 25mm": ("height", 25), "Alçada 30mm": ("height", 30),
            "Amplada 20mm": ("width", 20), "Amplada 25mm": ("width", 25), "Amplada 30mm": ("width", 30)
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


        # Títol del panell de controls
        ttk.Label(self.control_frame, text="Controls de Sketch2SVG", font=FONTS["Title"], foreground=COLORS["Nexe_800"]).grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="ew")

        # Secció 1: Selecció de carpeta i mode
        self.add_section_title(self.control_frame, "Configuració General", 1)

        # Selector de perfils d'ús (Presets)
        ttk.Label(self.control_frame, text="Perfil d'ús (Preset):").grid(row=2, column=0, sticky="w", pady=(5,0), columnspan=2)
        preset_names = list(config_manager.PRESETS.keys())
        self.preset_profile_var.set(preset_names[0])
        self.preset_profile_menu = ttk.OptionMenu(self.control_frame, self.preset_profile_var, self.preset_profile_var.get(), *preset_names, command=self.apply_preset)
        self.preset_profile_menu.grid(row=2, column=2, sticky="ew", padx=5)
        
        # Botó "Restaurar configuració del perfil"
        self.reset_profile_button = ttk.Button(self.control_frame, text="Restaurar configuració del perfil", command=self.reset_current_profile_settings)
        self.reset_profile_button.grid(row=3, column=0, columnspan=3, pady=(5, 15), sticky="ew")

        # Botó "Tria carpeta..."
        ttk.Label(self.control_frame, text="Carpeta d'esbossos:").grid(row=4, column=0, sticky="w", pady=(5,0), columnspan=3)
        self.folder_path_label = ttk.Label(self.control_frame, text="Cap carpeta seleccionada", wraplength=350, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"])
        self.folder_path_label.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5)
        self.select_folder_button = ttk.Button(self.control_frame, text="Tria carpeta...", command=self.select_folder)
        self.select_folder_button.grid(row=6, column=0, columnspan=3, pady=(5, 15), sticky="ew")

        # Mode de vectorització
        ttk.Label(self.control_frame, text="Mode de vectorització:").grid(row=7, column=0, sticky="w", pady=5, columnspan=3)
        self.outline_radio = ttk.Radiobutton(self.control_frame, text="Contorn omplert (per Extrusió 3D / Tall Làser)", variable=self.mode_var, value="outline", command=self.update_parameters_visibility)
        self.outline_radio.grid(row=8, column=0, sticky="w", columnspan=3)
        self.centerline_radio = ttk.Radiobutton(self.control_frame, text="Traç únic (per Gravat Làser / Plotter / Brodat)", variable=self.mode_var, value="centerline", command=self.update_parameters_visibility)
        self.centerline_radio.grid(row=9, column=0, sticky="w", columnspan=3)

        # Checkbox "Batch agressiu"
        self.batch_aggressive_check = ttk.Checkbutton(self.control_frame, text="Mode Batch agressiu (Força paràmetres més durs)", variable=self.batch_aggressive_var, command=self.preview_image)
        self.batch_aggressive_check.grid(row=10, column=0, columnspan=3, sticky="w", pady=(10, 20))

        # --- Panell de Preprocés d'Imatge ---
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

        # --- Càrrega inicial de la configuració ---
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

    def _load_initial_config(self):
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

        self.dpi_var.set(settings.get("dpi_var", config_manager.DEFAULT_STANDARD_SETTINGS["dpi_var"]))
        self.scale_preset_var.set(settings.get("scale_preset_var", config_manager.DEFAULT_STANDARD_SETTINGS["scale_preset_var"]))

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
        """
        Valida que l'entrada sigui un número i dins d'un rang specificat.
        P: el text resultant al camp Entry si la modificació és permesa
        V: raó de la validació (focusin, focusout, key, etc.)
        from_val_str, to_val_str: límits del rang com a strings
        var_name: nom de la variable de control (per exemple, 'threshold_var')
        """
        from_val = float(from_val_str)
        to_val = float(to_val_str)

        if V == 'focusout':
            if P == "":
                self.status_bar.config(text="Estat: Esperant...")
                return True
            
            try:
                val = float(P)

                if not (from_val <= val <= to_val):
                    self.status_bar.config(text=f"Error: El valor ha de ser entre {from_val_str} i {to_val_str} per a '{var_name.replace('_var', '')}'.")
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


    def update_parameters_visibility(self):
        """Actualitza la visibilitat dels controls segons el mode seleccionat."""
        if self.mode_var.get() == "centerline":
            self.centerline_params_frame.grid(row=80, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        else:
            self.centerline_params_frame.grid_forget()
        self.preview_image() # Update preview when mode changes


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
        binarized_image_np: Imatge binaritzada (NumPy array, 0 o 255).
        output_svg_path: Ruta completa del fitxer SVG de sortida.
        original_image_name: Nom de la imatge original per als missatges d'estat.
        """
        self.status_bar.config(text=f"Vectoritzant {original_image_name} amb Potrace...")
        
        try:
            # Potrace necessita un fitxer PBM/PGM d'entrada.
            # Creem un fitxer temporal amb NamedTemporaryFile per gestionar-lo automàticament.
            with tempfile.NamedTemporaryFile(suffix=".pbm", delete=False) as temp_pbm_file:
                temp_pbm_path = temp_pbm_file.name
                # Guardem la imatge binaritzada com a PBM
                # Invertim els colors per a Potrace: 0 (negre) es converteix en 1 (traç), 255 (blanc) en 0 (fons)
                # Potrace per defecte vectoritza el negre.
                # Però el nostre _process_image_for_preview genera traç blanc sobre fons negre si invert_var és True,
                # o traç negre sobre fons blanc si invert_var és False.
                # Si volem que Potrace vectoritzi el traç, hem d'assegurar que el traç sigui negre (0) i el fons blanc (255)
                # en el PBM que li passem.
                
                # Convertim a format PBM (P1) amb Pillow
                # Pillow Image.fromarray(np_array) crea una imatge amb 0=negre, 255=blanc
                # Per a Potrace, el negre és el que es vectoritza.
                # Si la nostra imatge binaritzada té el traç negre (0) i fons blanc (255), ja està bé.
                # Si té traç blanc (255) i fons negre (0), l'hem d'invertir abans de guardar a PBM.
                
                # Comprovem si la imatge binaritzada té el traç negre (0) o blanc (255)
                # Assumim que el fons és majoritariament blanc (255) i el traç negre (0) per Potrace
                # Si la imatge ja ha estat invertida pel preprocessament i el traç és blanc, Potrace no el veurà.
                # Per tant, si el traç és blanc (255) i el fons negre (0) a la imatge binaritzada, la invertim per Potrace.
                # La manera més senzilla és assegurar que el traç sigui 0 i el fons 255.
                
                # Potrace vectoritza els píxels negres (0).
                # La nostra imatge binaritzada té 0 per negre i 255 per blanc.
                # Si invert_var és True, el traç és 255 i el fons 0.
                # Si invert_var és False, el traç és 0 i el fons 255.
                # Potrace necessita el traç com a negre (0).
                
                # Per tant, si self.invert_var.get() és True, la imatge binaritzada té el traç blanc.
                # Hem d'invertir-la per a Potrace.
                img_for_potrace = binarized_image_np
                if self.invert_var.get(): # Si l'usuari ha demanat invertir, el traç és blanc. Potrace necessita negre.
                    img_for_potrace = cv2.bitwise_not(binarized_image_np)

                pil_img = Image.fromarray(img_for_potrace)
                pil_img.save(temp_pbm_path)

            # Ordre de Potrace
            # potrace -s -o output.svg input.pbm
            # -s: per generar un SVG més suau (sense pixels)
            # -z group: per agrupar camins (útil per Fusion 360)
            # -u 1: unitats per píxel (per defecte Potrace utilitza 1 unitat per píxel)
            # La resolució i escalat en mm es gestionaran després amb els atributs de l'SVG.
            potrace_command = [
                "potrace",
                temp_pbm_path,
                "-s", # Smooth
                "-o", output_svg_path
            ]
            
            # Executar Potrace
            result = subprocess.run(potrace_command, capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                self.status_bar.config(text=f"Vectorització de {original_image_name} completada amb èxit.")
                print(f"Potrace output for {original_image_name}:\n{result.stdout}")
                return True
            else:
                self.status_bar.config(text=f"Error en vectoritzar {original_image_name} amb Potrace: {result.stderr}")
                print(f"Potrace error for {original_image_name}:\n{result.stderr}")
                return False

        except FileNotFoundError:
            self.status_bar.config(text="Error: Potrace no trobat. Assegura't que està instal·lat i al PATH.")
            print("Error: Potrace executable not found.")
            return False
        except subprocess.CalledProcessError as e:
            self.status_bar.config(text=f"Error de Potrace per {original_image_name}: {e.stderr.strip()}")
            print(f"Potrace command failed for {original_image_name}: {e.cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}")
            return False
        except Exception as e:
            self.status_bar.config(text=f"Error inesperat en vectoritzar {original_image_name}: {e}")
            print(f"Unexpected error during Potrace vectorization: {e}")
            return False
        finally:
            # Netejar el fitxer PBM temporal
            if 'temp_pbm_path' in locals() and os.path.exists(temp_pbm_path):
                os.remove(temp_pbm_path)

    def _scale_svg(self, svg_path, width_mm, height_mm, dpi):
        """
        Ajusta els atributs width, height i viewBox d'un SVG per escalar-lo a mm.
        svg_path: Ruta del fitxer SVG.
        width_mm, height_mm: Dimensions desitjades en mm.
        dpi: Resolució en DPI per a la conversió px a mm.
        """
        try:
            with open(svg_path, 'r') as f:
                svg_content = f.read()

            # Utilitzem BeautifulSoup per parsejar i modificar l'SVG
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(svg_content, 'xml')
            svg_tag = soup.find('svg')

            if not svg_tag:
                raise ValueError("No s'ha trobat l'etiqueta <svg> al fitxer.")

            # Obtenim les dimensions originals en píxels del viewBox si existeix
            original_width_px = None
            original_height_px = None
            if 'viewBox' in svg_tag.attrs:
                _, _, original_width_px_str, original_height_px_str = svg_tag['viewBox'].split()
                original_width_px = float(original_width_px_str)
                original_height_px = float(original_height_px_str)
            else:
                # Si no hi ha viewBox, intentem obtenir-ho de width/height i assumim px
                if 'width' in svg_tag.attrs and svg_tag['width'].endswith('px'):
                    original_width_px = float(svg_tag['width'][:-2])
                if 'height' in svg_tag.attrs and svg_tag['height'].endswith('px'):
                    original_height_px = float(svg_tag['height'][:-2])
                
                # Si no podem obtenir les dimensions, no podem escalar
                if original_width_px is None or original_height_px is None:
                    self.status_bar.config(text=f"Avís: No s'han pogut determinar les dimensions originals de l'SVG per escalar. No s'aplicarà l'escalat de mida.")
                    return # No escalem si no tenim dimensions de referència

            # Calcular el factor de conversió de píxels a mm
            # 1 inch = 25.4 mm
            mm_per_px = 25.4 / dpi

            # Calcular les dimensions en píxels que correspondrien a les dimensions en mm desitjades
            target_width_px = width_mm / mm_per_px if width_mm is not None else None
            target_height_px = height_mm / mm_per_px if height_mm is not None else None

            # Determinar l'escala global per encaixar dins els límits
            scale_factor = 1.0
            if target_width_px and original_width_px > 0:
                scale_factor = min(scale_factor, target_width_px / original_width_px)
            if target_height_px and original_height_px > 0:
                scale_factor = min(scale_factor, target_height_px / original_height_px)
            
            # Si no s'ha especificat cap límit, o les dimensions originals són 0, no escalem per límit.
            # Però sempre apliquem el DPI.
            
            # Calcular les noves dimensions del viewBox en píxels (basades en l'escala)
            new_viewbox_width_px = original_width_px
            new_viewbox_height_px = original_height_px

            # Ajustar el viewBox si cal (Potrace ja sol generar un viewBox correcte)
            # Però si volem escalar, hem de canviar el viewBox i les unitats de width/height
            
            # Si s'ha seleccionat un preset d'escala
            selected_scale_preset = self.scale_preset_var.get()
            scale_type, scale_value_mm = self.scale_preset_values.get(selected_scale_preset, (None, None))

            if scale_type and scale_value_mm is not None:
                if original_width_px is None or original_height_px is None:
                     self.status_bar.config(text=f"Avís: No s'han pogut determinar les dimensions originals de l'SVG per escalar. No s'aplicarà l'escalat de mida.")
                     return # No escalem si no tenim dimensions de referència

                if scale_type == "width":
                    scale_factor = (scale_value_mm / mm_per_px) / original_width_px
                elif scale_type == "height":
                    scale_factor = (scale_value_mm / mm_per_px) / original_height_px
                
                new_viewbox_width_px = original_width_px
                new_viewbox_height_px = original_height_px

                # Si el viewBox ja està ben definit per Potrace, només hem d'actualitzar width/height
                # en mm i mantenir el viewBox en píxels originals.
                svg_tag['width'] = f"{new_viewbox_width_px * scale_factor * mm_per_px:.2f}mm"
                svg_tag['height'] = f"{new_viewbox_height_px * scale_factor * mm_per_px:.2f}mm"
                
                # Potrace ja posa un viewBox correcte. Si el modifiquéssim, hauríem de transformar tots els camins.
                # És més segur mantenir el viewBox original de Potrace i només ajustar width/height en mm.
                # Opcionalment, podríem afegir un <g transform="scale(...)"> al voltant de tot el contingut.
                # Per simplicitat i robustesa amb Potrace, només ajustarem els atributs width/height de l'SVG.

            else: # Només apliquem el DPI per defecte si no hi ha preset d'escala
                svg_tag['width'] = f"{original_width_px * mm_per_px:.2f}mm"
                svg_tag['height'] = f"{original_height_px * mm_per_px:.2f}mm"
            
            # Si no hi ha viewBox, el creem basat en les dimensions originals de Potrace
            if 'viewBox' not in svg_tag.attrs:
                svg_tag['viewBox'] = f"0 0 {original_width_px} {original_height_px}"

            with open(svg_path, 'w') as f:
                f.write(str(soup))
            
            self.status_bar.config(text=f"Escalat de {os.path.basename(svg_path)} aplicat.")

        except Exception as e:
            self.status_bar.config(text=f"Error en escalar SVG de {os.path.basename(svg_path)}: {e}")
            print(f"Error scaling SVG: {e}")


    def export_batch(self):
        """Inicia el procés d'exportació en lot de totes les imatges."""
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
        self.export_button.config(state=tk.DISABLED) # Desactivar botó durant el procés

        # Iniciem el processament en lot en un fil separat
        thread = threading.Thread(target=self._export_batch_thread, args=(output_dir,))
        thread.daemon = True
        thread.start()

    def _export_batch_thread(self, output_dir):
        """Funció que s'executa en un fil separat per processar el lot."""
        results = []
        errors = []
        processed_count = 0
        total_files = len(self.image_files)

        for i, image_path in enumerate(self.image_files):
            original_image_name = os.path.basename(image_path)
            base_name, _ = os.path.splitext(original_image_name)
            
            # Actualitzar la barra d'estat al fil principal
            self.master.after(0, self.status_bar.config, f"Processant {original_image_name} ({i+1}/{total_files})...")

            try:
                # Pas 1: Preprocessar la imatge
                processed_img_np = self._process_image_for_preview(image_path)
                if processed_img_np is None:
                    errors.append(f"No s'ha pogut preprocessar {original_image_name}.")
                    continue

                # Pas 2: Vectoritzar segons el mode seleccionat
                mode = self.mode_var.get()
                output_svg_filename = f"{base_name}__{mode}.svg"
                output_svg_path = os.path.join(output_dir, output_svg_filename)

                success = False
                if mode == "outline":
                    success = self._vectorize_outline_potrace(processed_img_np, output_svg_path, original_image_name)
                elif mode == "centerline":
                    # TODO: Implementar vectorització centerline
                    self.master.after(0, self.status_bar.config, f"Mode 'Traç únic' no implementat encara per {original_image_name}.")
                    errors.append(f"Mode 'Traç únic' no implementat encara per {original_image_name}.")
                    continue # Saltar al següent fitxer
                
                if success:
                    # Pas 3: Aplicar escalat SVG
                    dpi = self.dpi_var.get()
                    scale_preset_tuple = self.scale_preset_values.get(self.scale_preset_var.get(), (None, None))
                    
                    target_width_mm = None
                    target_height_mm = None
                    if scale_preset_tuple and scale_preset_tuple[0] == "width":
                        target_width_mm = scale_preset_tuple[1]
                    elif scale_preset_tuple and scale_preset_tuple[0] == "height":
                        target_height_mm = scale_preset_tuple[1]

                    self._scale_svg(output_svg_path, target_width_mm, target_height_mm, dpi)
                    
                    results.append({"original": original_image_name, "output_svg": output_svg_path, "status": "OK"})
                    processed_count += 1
                else:
                    errors.append(f"Error en vectoritzar {original_image_name}.")

            except Exception as e:
                errors.append(f"Error crític processant {original_image_name}: {e}")
                self.master.after(0, self.status_bar.config, f"Error crític processant {original_image_name}: {e}")
                print(f"Critical error processing {original_image_name}: {e}")

        # Finalitzar el procés al fil principal
        self.master.after(0, self._finish_batch_export, processed_count, total_files, output_dir, results, errors)

    def _finish_batch_export(self, processed_count, total_files, output_dir, results, errors):
        """Finalitza el procés d'exportació en lot i actualitza la UI."""
        self.export_button.config(state=tk.NORMAL) # Reactivar botó

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


# Classe ToolTip (per als tooltips d'ajuda)
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
