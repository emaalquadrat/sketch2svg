import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import os
import cv2
import numpy as np

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
    "Title": ("Fraunces", 16, "bold"), # Pesos 600-700 per a titulars
    "SectionTitle": ("Fraunces", 12, "bold"), # Pesos 600-700
    "UI_Label": ("Inter", 10), # Pesos 400-600 per a text corrent i UI
    "UI_Button": ("Inter", 10, "bold"), # Pesos 400-600
    "UI_Small": ("Inter", 9),
    "UI_Tooltip": ("Inter", 8, "normal")
}

class Sketch2SVGApp:
    def __init__(self, master):
        self.master = master
        master.title("Sketch2SVG")
        master.geometry("1000x700") # Mida inicial de la finestra
        master.configure(bg=COLORS["Nexe_50"]) # Color de fons base

        # Configuració del grid per a un layout responsiu
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=3) # Panell de previsualització més gran

        # --- Inicialització de totes les variables de control aquí ---
        self.mode_var = tk.StringVar(value="outline")
        self.batch_aggressive_var = tk.BooleanVar()

        self.bin_method_var = tk.StringVar(value="adaptive")
        self.threshold_var = tk.IntVar(value=127)
        self.block_size_var = tk.IntVar(value=11)
        self.C_var = tk.IntVar(value=2)
        self.illum_sigma_var = tk.DoubleVar(value=50.0)
        self.clahe_var = tk.BooleanVar()
        self.median_filter_var = tk.BooleanVar()
        self.opening_radius_var = tk.IntVar(value=0)
        self.min_area_var = tk.IntVar(value=100)
        self.invert_var = tk.BooleanVar()

        self.prune_short_var = tk.DoubleVar(value=5.0)
        self.simplification_epsilon_var = tk.DoubleVar(value=2.0)
        self.stroke_mm_var = tk.DoubleVar(value=0.1)

        self.dpi_var = tk.IntVar(value=96)
        self.scale_preset_var = tk.StringVar(value="none")
        self.scale_preset_options = ["Cap", "Alçada 20mm", "Alçada 25mm", "Alçada 30mm", "Amplada 20mm", "Amplada 25mm", "Amplada 30mm"]
        self.scale_preset_values = {
            "none": None, "Alçada 20mm": ("height", 20), "Alçada 25mm": ("height", 25), "Alçada 30mm": ("height", 30),
            "Amplada 20mm": ("width", 20), "Amplada 25mm": ("width", 25), "Amplada 30mm": ("width", 30)
        }
        # --- Fi de la inicialització de variables de control ---


        # --- Frame esquerre per controls (Panell de configuració) ---
        self.control_frame = ttk.Frame(master, padding="15")
        self.control_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.control_frame.grid_rowconfigure(99, weight=1) # Per empènyer els elements cap amunt
        
        # Configurar 3 columnes per als controls: Label (Col 0), Slider (Col 1), Entry (Col 2)
        # La columna 0 (labels) tindrà un pes més gran per acomodar text llarg
        self.control_frame.grid_columnconfigure(0, weight=2) 
        self.control_frame.grid_columnconfigure(1, weight=3) # Sliders
        self.control_frame.grid_columnconfigure(2, weight=0, minsize=50) # Entrades fixes


        # Títol del panell de controls
        ttk.Label(self.control_frame, text="Controls de Sketch2SVG", font=FONTS["Title"], foreground=COLORS["Nexe_800"]).grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="ew")

        # Secció 1: Selecció de carpeta i mode
        self.add_section_title(self.control_frame, "Configuració General", 1)

        # Botó "Tria carpeta..."
        ttk.Label(self.control_frame, text="Carpeta d'esbossos:").grid(row=2, column=0, sticky="w", pady=(5,0), columnspan=3)
        self.folder_path_label = ttk.Label(self.control_frame, text="Cap carpeta seleccionada", wraplength=350, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"]) # Wraplength augmentat
        self.folder_path_label.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5)
        self.select_folder_button = ttk.Button(self.control_frame, text="Tria carpeta...", command=self.select_folder)
        self.select_folder_button.grid(row=4, column=0, columnspan=3, pady=(5, 15), sticky="ew")

        # Mode de vectorització
        ttk.Label(self.control_frame, text="Mode de vectorització:").grid(row=5, column=0, sticky="w", pady=5, columnspan=3)
        self.outline_radio = ttk.Radiobutton(self.control_frame, text="Contorn omplert (outline)", variable=self.mode_var, value="outline", command=self.update_parameters_visibility)
        self.outline_radio.grid(row=6, column=0, sticky="w", columnspan=3)
        self.centerline_radio = ttk.Radiobutton(self.control_frame, text="Traç únic (centerline)", variable=self.mode_var, value="centerline", command=self.update_parameters_visibility)
        self.centerline_radio.grid(row=7, column=0, sticky="w", columnspan=3)

        # Checkbox "Batch agressiu"
        self.batch_aggressive_check = ttk.Checkbutton(self.control_frame, text="Mode Batch agressiu", variable=self.batch_aggressive_var, command=self.preview_image)
        self.batch_aggressive_check.grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 20))

        # --- Panell de Preprocés d'Imatge ---
        self.add_section_title(self.control_frame, "Preprocés d'Imatge", 9)
        self.create_image_preprocessing_controls(self.control_frame, 10)

        # --- Panell de Paràmetres de Traç Únic (Centerline) ---
        self.centerline_params_frame = ttk.LabelFrame(self.control_frame, text="Paràmetres Traç Únic", padding="10")
        # Configuració de columnes per al frame de centerline (similar al control_frame)
        self.centerline_params_frame.grid_columnconfigure(0, weight=2)
        self.centerline_params_frame.grid_columnconfigure(1, weight=3)
        self.centerline_params_frame.grid_columnconfigure(2, weight=0, minsize=50)

        self.add_slider(self.centerline_params_frame, "Poda de segments (px):", self.prune_short_var, 0, 50, 0.5, row=0, tooltip="Elimina segments de l'esquelet més curts que aquest valor.")
        self.add_slider(self.centerline_params_frame, "Simplificació RDP ε (px):", self.simplification_epsilon_var, 0, 10, 0.1, row=1, tooltip="Llindar de tolerància per a la simplificació de polilínies (Ramer-Douglas-Peucker).")
        self.add_slider(self.centerline_params_frame, "Gruix de traç (mm):", self.stroke_mm_var, 0.01, 2.0, 0.01, row=2, tooltip="Gruix de línia per a visualització en SVG (no afecta la vectorització).")

        # --- Panell de Unitats SVG ---
        self.add_section_title(self.control_frame, "Unitats i Escalats SVG", 90)
        self.create_svg_units_controls(self.control_frame, 91)

        # --- Secció d'Accions ---
        self.add_section_title(self.control_frame, "Accions", 95)
        self.preview_button = ttk.Button(self.control_frame, text="Previsualitza", command=self.preview_image)
        self.preview_button.grid(row=96, column=0, columnspan=3, pady=(10, 5), sticky="ew")
        self.export_button = ttk.Button(self.control_frame, text="Exporta lot a SVG", command=self.export_batch)
        self.export_button.grid(row=97, column=0, columnspan=3, pady=(5, 10), sticky="ew")

        # --- Frame dret per previsualització i missatges ---
        self.preview_frame = ttk.Frame(master, relief="sunken", padding="10", width=600, height=600, style="Preview.TFrame")
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        self.preview_label = ttk.Label(self.preview_frame, text="Previsualització d'imatge binaritzada aquí", background=COLORS["White"], anchor="center", justify="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Barra d'estat
        self.status_bar = ttk.Label(master, text="Estat: Esperant...", relief=tk.SUNKEN, anchor=tk.W, background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"])
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.image_files = []
        self.current_image_index = -1
        self.display_image_data = None # Per a la imatge processada a la previsualització

        self.update_parameters_visibility() # Call initially to set correct visibility


    def add_section_title(self, parent_frame, title_text, row):
        """Afegeix un títol de secció amb un separador."""
        # Posicionem el títol primer, amb un pady superior i inferior.
        # Després, afegim el separador a la mateixa fila però amb un sticky a la part inferior.
        # Això permetrà que el text s'expandeixi sense solapar-se amb la línia.
        ttk.Label(parent_frame, text=title_text, font=FONTS["SectionTitle"], foreground=COLORS["Nexe_700"]).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(15, 0) # Pady superior per separar de l'anterior
        )
        ttk.Separator(parent_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="sEW", pady=(5,0) # 'sEW' perquè se separi del text i ocupi tot l'ample.
        )
        # Afegim un espai buit per a un millor espaiat visual
        ttk.Frame(parent_frame, height=10).grid(row=row+1, column=0, columnspan=3, sticky="ew")


    def add_slider(self, parent_frame, label_text, var_obj, from_, to, resolution, row, tooltip=""):
        """Afegeix un label, slider i entrada per un paràmetre."""
        ttk.Label(parent_frame, text=label_text).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 5)) # Afegir padx a l'etiqueta
        
        # La lambda crida a self.preview_image() quan el slider es mou.
        # Es retorna el valor per assegurar que el setter del slider funciona correctament.
        slider = ttk.Scale(parent_frame, from_=from_, to=to, orient="horizontal", variable=var_obj, command=lambda s: (var_obj.set(round(float(s) / resolution) * resolution), self.preview_image()), style="Nexe.Horizontal.TScale")
        slider.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        
        entry = ttk.Entry(parent_frame, textvariable=var_obj, width=8, style="Parameter.TEntry")
        entry.grid(row=row, column=2, sticky="w", padx=5, pady=2)

        # Tooltip icon "?"
        if tooltip:
            help_label = ttk.Label(parent_frame, text="?", font=FONTS["UI_Tooltip"], foreground=COLORS["Nexe_600"])
            help_label.grid(row=row, column=2, sticky="e", padx=(0,0)) # Posicionat a la columna 2 (on hi ha l'Entry) però amb sticky="e"
            self.create_tooltip(help_label, tooltip) 
            self.create_tooltip(slider, tooltip) 
            self.create_tooltip(entry, tooltip) 


    def create_tooltip(self, widget, text):
        """Crea un tooltip per a un widget."""
        toolTip = ToolTip(widget, text)


    def create_image_preprocessing_controls(self, parent_frame, start_row):
        """Crea els controls per al preprocessament d'imatge."""
        ttk.Radiobutton(parent_frame, text="Binarització Adaptativa", variable=self.bin_method_var, value="adaptive", command=self.preview_image).grid(row=start_row, column=0, sticky="w", columnspan=3)
        ttk.Radiobutton(parent_frame, text="Binarització Global", variable=self.bin_method_var, value="global", command=self.preview_image).grid(row=start_row+1, column=0, sticky="w", columnspan=3)

        self.add_slider(parent_frame, "Llindar Global:", self.threshold_var, 0, 255, 1, start_row+2, tooltip="Llindar per a la binarització global (0-255).")

        self.add_slider(parent_frame, "Mida de bloc (adaptatiu):", self.block_size_var, 3, 51, 2, start_row+3, tooltip="Mida del veïnatge per al càlcul del llindar adaptatiu (ha de ser un nombre senar).")
        self.add_slider(parent_frame, "Paràmetre C (adaptatiu):", self.C_var, -10, 10, 1, start_row+4, tooltip="Constant restada de la mitjana ponderada local (per a binarització adaptativa).")

        self.add_slider(parent_frame, "σ Correcció il·luminació:", self.illum_sigma_var, 1, 200, 1, start_row+5, tooltip="Desviació estàndard per al filtre gaussià de correcció d'il·luminació (σ).")

        ttk.Checkbutton(parent_frame, text="Activa CLAHE", variable=self.clahe_var, command=self.preview_image).grid(row=start_row+6, column=0, sticky="w", columnspan=3) # Columnspan 3

        ttk.Checkbutton(parent_frame, text="Filtre Median previ", variable=self.median_filter_var, command=self.preview_image).grid(row=start_row+7, column=0, sticky="w", columnspan=3) # Columnspan 3

        self.add_slider(parent_frame, "Radi Opening:", self.opening_radius_var, 0, 10, 1, start_row+8, tooltip="Radi per a l'operació morfològica 'opening' per eliminar soroll.")

        self.add_slider(parent_frame, "Min. àrea obj. (px):", self.min_area_var, 0, 1000, 10, start_row+9, tooltip="Àrea mínima en píxels per mantenir un objecte. Els objectes més petits s'eliminaran.")

        ttk.Checkbutton(parent_frame, text="Invertir imatge (fons clar)", variable=self.invert_var, command=self.preview_image).grid(row=start_row+10, column=0, sticky="w", columnspan=3, pady=(10,0)) # Columnspan 3


    def create_svg_units_controls(self, parent_frame, start_row):
        """Crea els controls per a les unitats SVG."""
        self.add_slider(parent_frame, "DPI (píxels per polzada):", self.dpi_var, 50, 200, 1, start_row, tooltip="Píxels per polzada, per escalar de píxels a mm en SVG.")

        ttk.Label(parent_frame, text="Preset d'escala:").grid(row=start_row+1, column=0, sticky="w", padx=(0, 5)) # Afegir padx
        self.scale_preset_menu = ttk.OptionMenu(parent_frame, self.scale_preset_var, self.scale_preset_options[0], *self.scale_preset_options, command=lambda _: self.preview_image()) # Add command
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
            # Filtrem només imatges vàlides i ignorar arxius que comencen amb '.'
            self.image_files = [os.path.join(folder_selected, f) for f in os.listdir(folder_selected) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')) and not f.startswith('.')]
            self.image_files.sort() # Ordenar per consistència
            if self.image_files:
                self.current_image_index = 0
                self.status_bar.config(text=f"Carpeta seleccionada. Trobades {len(self.image_files)} imatges.")
                self.preview_image() # Previsualitza la primera imatge automàticament
            else:
                self.status_bar.config(text="Carpeta seleccionada, però no s'han trobat imatges suportades.")
                self.preview_label.config(image='')
                self.display_image_data = None


    def _process_image_for_preview(self, image_path):
        """Processa una imatge amb els paràmetres de preprocessament i la retorna binaritzada."""
        try:
            # Carregar imatge amb OpenCV
            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                raise ValueError(f"No es pot carregar la imatge: {image_path}")

            # Convertir a escala de grisos
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 1. Filtre Median previ
            if self.median_filter_var.get():
                # Utilitzar un kernel de 3x3 o 5x5, ha de ser senar
                img_gray = cv2.medianBlur(img_gray, 5) # Kernel de 5x5 per defecte

            # 2. Correcció d'il·luminació (dividir per un fons suau estimat)
            sigma = self.illum_sigma_var.get()
            if sigma > 0: # Només aplicar si sigma és major que 0
                blurred_background = cv2.GaussianBlur(img_gray, (0, 0), sigma)
                # Evitar divisió per zero afegint un petit valor
                blurred_background = np.where(blurred_background == 0, 1, blurred_background)
                img_normalized = cv2.divide(img_gray, blurred_background, scale=255)
                img_gray = img_normalized.astype(np.uint8) # Convertir de nou a uint8

            # 3. CLAHE (equalització adaptativa)
            if self.clahe_var.get():
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)) # Valors per defecte, ajustables si cal
                img_gray = clahe.apply(img_gray)

            # 4. Binarització
            bin_method = self.bin_method_var.get()
            if bin_method == "adaptive":
                block_size = self.block_size_var.get()
                C = self.C_var.get()
                # block_size ha de ser senar i major que 1
                if block_size % 2 == 0:
                    block_size += 1 # Assegurar que és senar
                if block_size < 3:
                    block_size = 3 # Mínim 3 per adaptiveThreshold
                img_binarized = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C)
            else: # global
                threshold = self.threshold_var.get()
                _, img_binarized = cv2.threshold(img_gray, threshold, 255, cv2.THRESH_BINARY)
            
            # 5. Invertir si cal (assumim traç fosc sobre fons clar, si no, invertim)
            if self.invert_var.get():
                img_binarized = cv2.bitwise_not(img_binarized)

            # 6. Neteja morfològica: Opening
            opening_radius = self.opening_radius_var.get()
            if opening_radius > 0:
                # Kernel circular/el·líptic. La mida ha de ser senar (radius*2 + 1)
                kernel_size = opening_radius * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                img_binarized = cv2.morphologyEx(img_binarized, cv2.MORPH_OPEN, kernel)

            # 7. Eliminar objectes petits
            min_area = self.min_area_var.get()
            if min_area > 0:
                # Trobar components connectats
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(img_binarized, 8, cv2.CV_32S)
                output_image = np.zeros_like(img_binarized)
                # Iterar sobre tots els components (excepte el fons, label 0)
                for i in range(1, num_labels):
                    area = stats[i, cv2.CC_STAT_AREA]
                    if area >= min_area:
                        output_image[labels == i] = 255 # Mantenir l'objecte

                img_binarized = output_image

            return img_binarized

        except Exception as e:
            self.status_bar.config(text=f"Error en processar la imatge: {e}")
            return None


    def preview_image(self):
        """Processa la imatge actual i la mostra binaritzada."""
        if not self.image_files:
            self.status_bar.config(text="Error: No hi ha imatges per previsualitzar. Selecciona una carpeta.")
            self.preview_label.config(image='')
            self.display_image_data = None
            return

        if self.current_image_index == -1:
            self.current_image_index = 0

        image_path = self.image_files[self.current_image_index]
        self.status_bar.config(text=f"Previsualitzant: {os.path.basename(image_path)} (Aplicant paràmetres...)")

        # Processar la imatge amb els paràmetres actuals
        processed_img_np = self._process_image_for_preview(image_path)

        if processed_img_np is not None:
            # Convertir l'array NumPy d'OpenCV a format PIL Image per mostrar-lo a Tkinter
            img_pil = Image.fromarray(processed_img_np)

            # Redimensionar per a la previsualització si és massa gran
            # winfo_width/height donarà 1 si la finestra no s'ha mapejat encara, cal un fallback
            self.master.update_idletasks() # Forçar l'actualització per obtenir mides correctes
            max_width = self.preview_frame.winfo_width() - 20 
            max_height = self.preview_frame.winfo_height() - 20 
            
            if max_width <= 0 or max_height <= 0: # Fallback si les mides encara no estan disponibles
                max_width = 600
                max_height = 600

            img_width, img_height = img_pil.size
            if img_width > max_width or img_height > max_height:
                ratio = min(max_width / img_width, max_height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                img_pil = img_pil.resize((new_width, new_height), Image.LANCZOS)
            
            self.display_image_data = ImageTk.PhotoImage(img_pil) # Guarda la referència
            self.preview_label.config(image=self.display_image_data)
            self.preview_label.image = self.display_image_data # Mantenir referència per evitar que esborri la imatge
            self.preview_label.config(text="") # Eliminar text placeholder
            self.status_bar.config(text=f"Previsualització de {os.path.basename(image_path)} actualitzada.")

        else:
            self.preview_label.config(image='', text="Error en la previsualització o imatge no suportada.")
            self.display_image_data = None


    def export_batch(self):
        """Inicia el procés d'exportació en lot de totes les imatges."""
        if not self.image_files:
            self.status_bar.config(text="Error: No hi ha imatges per exportar.")
            return

        self.status_bar.config(text="Exportant lot... (funcionalitat per implementar)")
        print("Exportació en lot iniciada.")
        # Aquí aniria la lògica per processar cada imatge i exportar-la.

# Classe ToolTip (per als tooltips d'ajuda)
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        # Per posicionar a prop del widget
        x_root = self.widget.winfo_rootx()
        y_root = self.widget.winfo_rooty()
        width = self.widget.winfo_width()
        height = self.widget.winfo_height()

        # Posicionar el tooltip a la dreta inferior del widget
        x = x_root + width + 5
        y = y_root + height + 5

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True) # Sense bordes ni barra de títol
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
    style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'

    # Configuració global de la font i els colors per a tots els widgets ttk
    style.configure(".", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])

    # Estil específic per a botons
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

    # Estil per a etiquetes (labels)
    style.configure("TLabel",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    
    # Estil per a Radiobuttons i Checkbuttons
    style.configure("TRadiobutton",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    style.configure("TCheckbutton",
                    foreground=COLORS["Nexe_800"],
                    background=COLORS["Nexe_50"])
    
    # Estil per a Entry amb amplada fixada
    style.configure("Parameter.TEntry", # Estil per a les entrades dels paràmetres
                    fieldbackground=COLORS["White"],
                    foreground=COLORS["Nexe_900"])
    
    # Estil per a Scales (sliders)
    style.configure("Nexe.Horizontal.TScale", # Estil customitzat per als nostres sliders
                    background=COLORS["Nexe_50"],
                    troughcolor=COLORS["Nexe_200"],
                    sliderthickness=15,
                    relief="flat")
    style.map("Nexe.Horizontal.TScale",
              background=[('active', COLORS["Nexe_300"])])
    
    # Estil per a la previsualització Frame
    style.configure("Preview.TFrame", background=COLORS["Nexe_100"])
    
    # Estil per a la LabelFrame (per exemple, Paràmetres Traç Únic)
    style.configure("TLabelframe", background=COLORS["Nexe_50"], foreground=COLORS["Nexe_800"])
    style.configure("TLabelframe.Label", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])

    # Estil per a OptionMenu (dropdowns)
    style.configure("TMenubutton",
                    background=COLORS["Nexe_100"],
                    foreground=COLORS["Nexe_800"],
                    arrowcolor=COLORS["Nexe_800"])
    style.map("TMenubutton",
              background=[('active', COLORS["Nexe_200"])])


    app = Sketch2SVGApp(root)
    root.mainloop()
