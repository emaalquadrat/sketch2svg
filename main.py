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
import json
from bs4 import BeautifulSoup
import ezdxf
import csv
import traceback
import sys

from skimage.morphology import skeletonize as sk_skeletonize
from svg.path import parse_path

# --- Colors i Fonts ---
COLORS = { "Nexe_50": "#EFF1EF", "Nexe_100": "#DFE2DF", "Nexe_200": "#C4CAC4", "Nexe_300": "#A9B2A8", "Nexe_400": "#8F9A8D", "Nexe_500": "#80947E", "Nexe_600": "#5B6959", "Nexe_700": "#485346", "Nexe_800": "#343D34", "Nexe_900": "#242923", "Black": "#111111", "White": "#FFFFFF" }
FONTS = { "Title": ("Fraunces", 16, "bold"), "SectionTitle": ("Fraunces", 12, "bold"), "UI_Label": ("Inter", 10), "UI_Button": ("Inter", 10, "bold"), "UI_Small": ("Inter", 9), "UI_Tooltip": ("Inter", 8, "normal") }

class Sketch2SVGApp:
    def __init__(self, master):
        self.master = master
        master.title("Sketch2SVG")
        master.geometry("1000x700")
        master.minsize(800, 600)
        master.configure(bg=COLORS["Nexe_50"])
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1, minsize=400)
        master.grid_columnconfigure(1, weight=3)

        self._init_vars()
        self._build_ui()
        self.master.after(100, self._load_initial_config)

    def _init_vars(self):
        self.mode_var = tk.StringVar(value="outline")
        self.preset_profile_var = tk.StringVar()
        self.bin_method_var = tk.StringVar(value="adaptive")
        self.threshold_var = tk.IntVar(value=127)
        self.block_size_var = tk.IntVar(value=11)
        self.C_var = tk.IntVar(value=2)
        self.illum_sigma_var = tk.DoubleVar(value=50.0)
        self.clahe_var = tk.BooleanVar(value=False)
        self.median_filter_var = tk.BooleanVar(value=False)
        self.opening_radius_var = tk.IntVar(value=0)
        self.min_area_var = tk.IntVar(value=100)
        self.invert_var = tk.BooleanVar(value=False)
        self.prune_short_var = tk.DoubleVar(value=5.0)
        self.simplification_epsilon_var = tk.DoubleVar(value=2.0)
        self.stroke_mm_var = tk.DoubleVar(value=0.1)
        self.stitch_length_mm_var = tk.DoubleVar(value=1.0)
        self.dpi_var = tk.IntVar(value=96)
        self.scale_preset_var = tk.StringVar(value="Cap")
        self.vector_preview_var = tk.BooleanVar(value=False)
        self.scale_preset_options = ["Cap", "Alçada 20mm", "Alçada 25mm", "Alçada 30mm", "Amplada 20mm", "Amplada 25mm", "Amplada 30mm"]
        self.scale_preset_values = {"Cap": None, "Alçada 20mm": ("height", 20), "Alçada 25mm": ("height", 25), "Alçada 30mm": ("height", 30), "Amplada 20mm": ("width", 20), "Amplada 25mm": ("width", 25), "Amplada 30mm": ("width", 30)}
        self.image_files = []
        self.current_image_index = -1
        self.img_tk = None

    def _build_ui(self):
        self.canvas = tk.Canvas(self.master, bg=COLORS["Nexe_50"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(10,0), pady=10)
        self.control_frame = ttk.Frame(self.canvas, padding="15")
        self.canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=0, sticky="nse", padx=(0,10))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.control_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.master.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"), "+")
        
        ttk.Label(self.control_frame, text="Controls de Sketch2SVG", font=FONTS["Title"], foreground=COLORS["Nexe_800"]).pack(fill="x", pady=(0, 20))
        self._create_general_config_section()
        self._create_preprocessing_section()
        self._create_centerline_params_section()
        self._create_svg_units_section()
        self._create_actions_section()

        self.preview_frame = ttk.Frame(self.master, relief="sunken", padding="10", style="Preview.TFrame")
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        self.preview_frame.grid_propagate(False)
        self.preview_canvas = tk.Canvas(self.preview_frame, bg=COLORS["White"], highlightthickness=0)
        self.preview_canvas.pack(expand=True, fill="both")
        self.preview_canvas.create_text(20, 20, anchor="nw", text="Selecciona una carpeta per començar.", fill=COLORS["Nexe_800"])

        self.status_bar = ttk.Label(self.master, text="Estat: Esperant...", relief=tk.SUNKEN, anchor=tk.W, background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"])
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _add_section_title(self, parent, text):
        ttk.Label(parent, text=text, font=FONTS["SectionTitle"], foreground=COLORS["Nexe_700"]).pack(fill="x", pady=(15, 2), anchor='w')
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 5))

    def _create_general_config_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor='w')
        self._add_section_title(frame, "Configuració General")
        
        ttk.Label(frame, text="Perfil d'ús (Preset):").pack(fill="x")
        preset_names = list(config_manager.PRESETS.keys())
        ttk.OptionMenu(frame, self.preset_profile_var, preset_names[0], *preset_names, command=self.apply_preset).pack(fill="x", pady=(0, 5))
        ttk.Button(frame, text="Restaurar configuració del perfil", command=self.reset_current_profile_settings).pack(fill="x", pady=(0, 10))
        
        ttk.Button(frame, text="Tria carpeta d'esbossos...", command=self.select_folder).pack(fill="x")
        self.folder_path_label = ttk.Label(frame, text="Cap carpeta seleccionada", wraplength=350, font=FONTS["UI_Small"], foreground=COLORS["Nexe_400"])
        self.folder_path_label.pack(fill="x", pady=2)
        
        ttk.Label(frame, text="Mode de vectorització:").pack(fill="x", pady=(10, 2))
        ttk.Radiobutton(frame, text="Contorn omplert (Tall Làser)", variable=self.mode_var, value="outline", command=self.update_parameters_visibility).pack(anchor="w")
        ttk.Radiobutton(frame, text="Traç únic (Gravat / Plotter)", variable=self.mode_var, value="centerline", command=self.update_parameters_visibility).pack(anchor="w")

    def _create_preprocessing_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor='w')
        self._add_section_title(frame, "Preprocés d'Imatge")
        
        self.add_slider(frame, "Correcció il·luminació:", self.illum_sigma_var, 0, 200, 1, "Suavitza el fons per corregir il·luminació irregular.")
        ttk.Checkbutton(frame, text="Filtre Median (reducció soroll)", variable=self.median_filter_var, command=self.preview_image).pack(anchor="w")
        ttk.Checkbutton(frame, text="CLAHE (millora contrast)", variable=self.clahe_var, command=self.preview_image).pack(anchor="w")
        
        ttk.Label(frame, text="Tipus de Binarització:").pack(fill="x", pady=(10, 2))
        ttk.Radiobutton(frame, text="Adaptativa", variable=self.bin_method_var, value="adaptive", command=self.preview_image).pack(anchor="w")
        ttk.Radiobutton(frame, text="Global", variable=self.bin_method_var, value="global", command=self.preview_image).pack(anchor="w")
        self.add_slider(frame, "Llindar Global:", self.threshold_var, 0, 255, 1, "Nivell de tall per al mètode global.")
        self.add_slider(frame, "Mida Àrea (adapt.):", self.block_size_var, 3, 51, 2, "Mida de la regió per al llindar adaptatiu.")
        self.add_slider(frame, "Contrast (adapt.):", self.C_var, -20, 20, 1, "Ajust fi per al llindar adaptatiu.")
        
        ttk.Checkbutton(frame, text="Invertir colors", variable=self.invert_var, command=self.preview_image).pack(anchor="w", pady=(10, 0))
        self.add_slider(frame, "Radi 'Obertura' (neteja):", self.opening_radius_var, 0, 10, 1, "Tapa forats als traços i elimina soroll.")
        self.add_slider(frame, "Mínim Àrea Objecte:", self.min_area_var, 0, 1000, 10, "Elimina taques o components petits.")

    def _create_centerline_params_section(self):
        self.centerline_params_frame = ttk.Frame(self.control_frame)
        self._add_section_title(self.centerline_params_frame, "Paràmetres Traç Únic")
        self.add_slider(self.centerline_params_frame, "Poda segments curts (px):", self.prune_short_var, 0, 50, 0.5, "Elimina línies curtes sorolloses.")
        self.add_slider(self.centerline_params_frame, "Simplificació línies ε (px):", self.simplification_epsilon_var, 0, 10, 0.1, "Suavitza les línies eliminant punts redundants.")
        self.add_slider(self.centerline_params_frame, "Gruix de traç (mm):", self.stroke_mm_var, 0.01, 2.0, 0.01, "Gruix visual per a l'SVG (no afecta el gravat).")
        self.add_slider(self.centerline_params_frame, "Llargada de punt (mm):", self.stitch_length_mm_var, 0.1, 5.0, 0.1, "Llargada mitjana per a punts de brodat (CSV).")
        
    def _create_svg_units_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor='w')
        self._add_section_title(frame, "Unitats i Escalats SVG")
        self.add_slider(frame, "Resolució DPI:", self.dpi_var, 50, 300, 1, "Píxels per polzada de la imatge original.")
        ttk.Label(frame, text="Mida final (escala):").pack(anchor="w")
        ttk.OptionMenu(frame, self.scale_preset_var, self.scale_preset_options[0], *self.scale_preset_options, command=lambda e: self.preview_image()).pack(fill="x")

    def _create_actions_section(self):
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="x", pady=5, anchor='w')
        self._add_section_title(frame, "Accions")
        ttk.Checkbutton(frame, text="Previsualització Vectorial (lent)", variable=self.vector_preview_var, command=self.preview_image).pack(anchor="w", pady=5)
        self.export_button = ttk.Button(frame, text="Exporta lot", command=self.export_batch)
        self.export_button.pack(fill="x", pady=10, ipady=5)

    def add_slider(self, parent_frame, label_text, var_obj, from_, to, resolution, tooltip=""):
        f = ttk.Frame(parent_frame)
        f.pack(fill='x', pady=2)
        ttk.Label(f, text=label_text, width=20).pack(side='left')
        entry = ttk.Entry(f, textvariable=var_obj, width=6)
        entry.pack(side='right', padx=(5,0))
        scale = ttk.Scale(f, from_=from_, to=to, variable=var_obj, orient='horizontal', command=lambda s: var_obj.set(round(float(s) / resolution) * resolution))
        scale.pack(side='right', fill='x', expand=True)
        
        entry.bind("<FocusOut>", lambda e: self.preview_image(), "+")
        entry.bind("<Return>", lambda e: self.preview_image(), "+")
        scale.bind("<ButtonRelease-1>", lambda e: self.preview_image(), "+")

        if tooltip: ToolTip(f, tooltip)
        
    def on_closing(self):
        config_manager.save_config(self._get_current_settings())
        self.master.destroy()

    def apply_preset(self, preset_name=None):
        if preset_name is None: preset_name = self.preset_profile_var.get()
        settings = config_manager.get_preset_settings(preset_name)
        for key, value in settings.items():
            if hasattr(self, key) and isinstance(getattr(self, key), (tk.StringVar, tk.IntVar, tk.DoubleVar, tk.BooleanVar)):
                getattr(self, key).set(value)
        self.update_parameters_visibility()

    def _load_initial_config(self):
        settings = config_manager.load_config()
        self.preset_profile_var.set(settings.get("last_preset_profile", list(config_manager.PRESETS.keys())[0]))
        self.apply_preset()
        last_folder = settings.get("last_folder", "")
        if os.path.isdir(last_folder):
            self.select_folder(last_folder)
    
    def _get_current_settings(self):
        settings = {var_name: getattr(self, var_name).get() for var_name in dir(self) if var_name.endswith("_var")}
        path = self.folder_path_label.cget("text")
        settings["last_folder"] = path if "Cap carpeta" not in path else ""
        settings["last_preset_profile"] = self.preset_profile_var.get()
        return settings

    def reset_current_profile_settings(self):
        self.apply_preset()

    def update_parameters_visibility(self):
        if self.mode_var.get() == "centerline":
            self.centerline_params_frame.pack(fill="x", pady=10, anchor='w')
        else:
            self.centerline_params_frame.pack_forget()
        self.preview_image()

    def select_folder(self, folder_path=None):
        if folder_path is None: folder_path = filedialog.askdirectory()
        if folder_path and os.path.isdir(folder_path):
            self.folder_path_label.config(text=folder_path)
            self.image_files = sorted([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg')) and not f.startswith('.')])
            if self.image_files:
                self.current_image_index = 0
                self.preview_image()
            else:
                self.status_bar.config(text="Cap imatge suportada a la carpeta.")
    
    def preview_image(self):
        if hasattr(self, 'image_files') and self.image_files:
            path = self.image_files[self.current_image_index]
            self.status_bar.config(text=f"Processant {os.path.basename(path)}...")
            threading.Thread(target=self._process_and_update_thread, args=(path,), daemon=True).start()

    def _process_and_update_thread(self, path):
        img_np = self._process_image_for_preview(path)
        vector_paths = []
        if img_np is not None and self.vector_preview_var.get():
            _, vector_paths = self._vectorize_for_preview(img_np, self.mode_var.get())
        self.master.after(0, self._update_preview_display, img_np, path, vector_paths)
        
    def _process_image_for_preview(self, path):
        try:
            img_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img_gray is None: raise ValueError("No es pot llegir la imatge.")

            # Pre-filtres
            if self.median_filter_var.get(): img_gray = cv2.medianBlur(img_gray, 5)
            sigma = self.illum_sigma_var.get()
            if sigma > 0:
                blurred = cv2.GaussianBlur(img_gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
                img_gray = cv2.divide(img_gray, blurred, scale=255)
            if self.clahe_var.get():
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                img_gray = clahe.apply(img_gray)
            
            # Binarització (sortida estàndard: traç negre, fons blanc)
            if self.bin_method_var.get() == "adaptive":
                bs = self.block_size_var.get();
                if bs % 2 == 0: bs += 1
                img_bin = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, bs, self.C_var.get())
            else:
                _, img_bin = cv2.threshold(img_gray, self.threshold_var.get(), 255, cv2.THRESH_BINARY_INV)
            
            # Conversió a format de treball (traç blanc, fons negre)
            img_work = cv2.bitwise_not(img_bin)
            if self.invert_var.get(): img_work = cv2.bitwise_not(img_work)
            
            # Post-filtres sobre imatge amb traç blanc
            radius = self.opening_radius_var.get()
            if radius > 0:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))
                img_work = cv2.morphologyEx(img_work, cv2.MORPH_OPEN, kernel)
            
            min_area = self.min_area_var.get()
            if min_area > 0:
                n, labels, stats, _ = cv2.connectedComponentsWithStats(img_work, 8, cv2.CV_32S)
                for i in range(1, n):
                    if stats[i, cv2.CC_STAT_AREA] < min_area: img_work[labels == i] = 0
            
            return img_work
        except Exception as e:
            traceback.print_exc(); return None

    def _update_preview_display(self, img_np, path, vector_paths=None):
        self.master.update_idletasks() # Forcem l'actualització de la UI abans de llegir mides
        self.preview_canvas.delete("all")
        if img_np is None:
            self.preview_canvas.create_text(20,20, anchor='nw', text=f"Error processant {os.path.basename(path)}")
            return

        canvas_w, canvas_h = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        if canvas_w < 2 or canvas_h < 2: return # Evitem dibuixar si el canvas no és visible
        
        img_h, img_w = img_np.shape
        ratio = min((canvas_w-20) / img_w, (canvas_h-20) / img_h)
        disp_w, disp_h = int(img_w * ratio), int(img_h * ratio)
        
        img_pil = Image.fromarray(img_np).resize((disp_w, disp_h), Image.LANCZOS)
        self.img_tk = ImageTk.PhotoImage(img_pil)
        self.preview_canvas.create_image(canvas_w/2, canvas_h/2, anchor='center', image=self.img_tk)

        if vector_paths:
            ox, oy = (canvas_w - disp_w) / 2, (canvas_h - disp_h) / 2
            for path in vector_paths:
                scaled_path = [(x * ratio + ox, y * ratio + oy) for x, y in path]
                if len(scaled_path) > 1:
                    self.preview_canvas.create_line(scaled_path, fill="lime", width=1.5)

        self.status_bar.config(text=f"Previsualitzant {os.path.basename(path)}")

    def _vectorize_for_preview(self, img_np, mode):
        if mode == 'outline':
            return self._vectorize_outline_potrace(img_np, preview_only=True)
        else:
            return self._vectorize_centerline(img_np, preview_only=True)

    def _vectorize_outline_potrace(self, binarized_image_np, output_svg_path=None, preview_only=False):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            img_for_potrace = cv2.bitwise_not(binarized_image_np) # Potrace vol traç negre
            cv2.imwrite(tmp_path, img_for_potrace)
            
            command = ["potrace", tmp_path]
            if preview_only:
                command.extend(["-b", "svg"])
            else:
                command.extend(["-s", "-o", output_svg_path, "--fillcolor", "none", "--strokecolor", "black", "--stroke-width", "0.01mm"])

            result = subprocess.run(command, check=True, capture_output=True, text=True)
            svg_content = result.stdout if preview_only else open(output_svg_path, 'r', encoding='utf-8').read()

            soup = BeautifulSoup(svg_content, 'xml')
            paths = [self._convert_svgpath_to_points(parse_path(p.get('d'))) for p in soup.find_all('path') if p.get('d')]
            return True, [p for p in paths if p]
        except Exception as e:
            traceback.print_exc(); return False, []
        finally:
            if tmp_path and os.path.exists(tmp_path): os.remove(tmp_path)

    def _vectorize_centerline(self, binarized_image_np, output_svg_path=None, preview_only=False):
        try:
            skeleton = sk_skeletonize(binarized_image_np / 255)
            skel_coords = np.argwhere(skeleton)
            if skel_coords.size == 0: return True, []

            graph = {tuple(p): [tuple(n) for n in self._get_neighbors(p, skeleton)] for p in skel_coords}
            raw_paths = []
            
            nodes_to_process = [node for node, nbrs in graph.items() if len(nbrs) != 2]
            for start_node in nodes_to_process:
                if start_node not in graph: continue
                for neighbor in list(graph[start_node]):
                    path = [start_node, neighbor]
                    self._remove_edge(graph, start_node, neighbor)
                    curr, prev = neighbor, start_node
                    while curr in graph and len(graph.get(curr, [])) == 1:
                        prev, curr = curr, graph[curr][0]
                        path.append(curr)
                        self._remove_edge(graph, prev, curr)
                    raw_paths.append([(c,r) for r,c in path])

            while graph:
                start_node = next(iter(graph))
                path = [start_node]
                curr = start_node
                while curr in graph and graph[curr]:
                    neighbor = graph[curr][0]
                    self._remove_edge(graph, curr, neighbor)
                    curr = neighbor
                    path.append(curr)
                    if curr == start_node: break
                raw_paths.append([(c,r) for r,c in path])

            paths = self._join_paths(raw_paths, max_dist=5)
            
            prune_len = self.prune_short_var.get()
            if prune_len > 0: paths = [p for p in paths if np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)) >= prune_len]
            epsilon = self.simplification_epsilon_var.get()
            if epsilon > 0: paths = [self._ramer_douglas_peucker(p, epsilon) for p in paths if len(p) > 1]
            
            if not preview_only and output_svg_path:
                h, w = binarized_image_np.shape
                self._create_svg_from_paths(output_svg_path, paths, w, h, self.dpi_var.get(), self.stroke_mm_var.get(), "blue")
            return True, paths
        except Exception as e:
            traceback.print_exc(); return False, []

    def _join_paths(self, paths, max_dist):
        paths = [list(p) for p in paths]
        while True:
            merged = False
            i = 0
            while i < len(paths):
                j = i + 1
                while j < len(paths):
                    p1, p2 = paths[i], paths[j]
                    endpoints1 = [np.array(p1[0]), np.array(p1[-1])]
                    endpoints2 = [np.array(p2[0]), np.array(p2[-1])]
                    
                    min_dist = float('inf')
                    best_case = (-1, -1)
                    for i1 in range(2):
                        for i2 in range(2):
                            dist = np.linalg.norm(endpoints1[i1] - endpoints2[i2])
                            if dist < min_dist:
                                min_dist = dist
                                best_case = (i1, i2)

                    if min_dist < max_dist:
                        if best_case == (1, 0): paths[i].extend(p2) # end1 -> start2
                        elif best_case == (0, 0): p1.reverse(); paths[i] = p1 + p2 # start1 -> start2
                        elif best_case == (1, 1): p2.reverse(); paths[i].extend(p2) # end1 -> end2
                        elif best_case == (0, 1): p1.reverse(); p2.reverse(); paths[i] = p2 + p1 # start1 -> end2
                        
                        paths.pop(j)
                        merged = True; break
                    else: j += 1
                if merged: break
                i += 1
            if not merged: break
        return paths

    def _get_neighbors(self, p, skeleton):
        r, c = p
        neighbors = []
        for dr in [-1,0,1]:
            for dc in [-1,0,1]:
                if dr==0 and dc==0: continue
                nr, nc = r+dr, c+dc
                if 0 <= nr < skeleton.shape[0] and 0 <= nc < skeleton.shape[1] and skeleton[nr,nc]:
                    neighbors.append((nr,nc))
        return neighbors

    def _remove_edge(self, graph, n1, n2):
        if n1 in graph and n2 in graph.get(n1, []): graph[n1].remove(n2)
        if n2 in graph and n1 in graph.get(n2, []): graph[n2].remove(n1)
        if n1 in graph and not graph[n1]: del graph[n1]
        if n2 in graph and not graph[n2]: del graph[n2]
    
    def _convert_svgpath_to_points(self, path_obj, step=1.0):
        length = path_obj.length()
        if length == 0: return []
        points = []
        num_steps = max(2, int(length / step))
        for i in range(num_steps + 1):
            p = path_obj.point(i/num_steps)
            points.append((p.real, p.imag))
        return points
        
    def _create_svg_from_paths(self, svg_path, paths, w_px, h_px, dpi, stroke_w_mm, color):
        mm_per_px = 25.4 / dpi
        w_mm, h_mm = w_px * mm_per_px, h_px * mm_per_px
        scale_preset_str = self.scale_preset_var.get()
        if scale_preset_str != "Cap" and self.scale_preset_values[scale_preset_str]:
            dim, val = self.scale_preset_values[scale_preset_str]
            if dim == "width" and w_mm > 0: ratio = val / w_mm; w_mm, h_mm = val, h_mm * ratio
            elif dim == "height" and h_mm > 0: ratio = val / h_mm; w_mm, h_mm = w_mm * ratio, val
        svg = f'<svg width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_px} {h_px}" xmlns="http://www.w3.org/2000/svg">'
        for path in paths:
            points = " ".join([f"{x:.3f},{y:.3f}" for x,y in path])
            svg += f'<polyline points="{points}" style="fill:none;stroke:{color};stroke-width:{stroke_w_mm:.3f}"/>'
        svg += '</svg>'
        with open(svg_path, 'w', encoding='utf-8') as f: f.write(svg)

    def _ramer_douglas_peucker(self, points, epsilon):
        if len(points) < 3: return points
        dmax, index = 0.0, 0
        p1, p2 = np.array(points[0]), np.array(points[-1])
        if np.allclose(p1, p2): return [p1.tolist()]
        line_vec = p2 - p1
        line_len = np.linalg.norm(line_vec)
        if line_len == 0: return [p1.tolist()]
        
        for i in range(1, len(points) - 1):
            d = np.linalg.norm(np.cross(line_vec, p1-np.array(points[i]))) / line_len
            if d > dmax: index, dmax = i, d
        if dmax > epsilon:
            res1 = self._ramer_douglas_peucker(points[:index+1], epsilon)
            res2 = self._ramer_douglas_peucker(points[index:], epsilon)
            return res1[:-1] + res2
        else: return [points[0], points[-1]]

    def _export_dxf_from_svg_paths(self, dxf_path, paths, w_px, h_px, dpi, layer, color):
        try:
            doc = ezdxf.new('R2010'); msp = doc.modelspace()
            doc.layers.new(layer, dxfattribs={'color': color})
            mm_per_px = 25.4 / dpi
            for path in paths:
                dxf_points = [(p[0] * mm_per_px, (h_px - p[1]) * mm_per_px) for p in path]
                if len(dxf_points) > 1: msp.add_lwpolyline(dxf_points, dxfattribs={'layer': layer})
            doc.saveas(dxf_path)
        except Exception as e: self.status_bar.config(text=f"Error exportant DXF: {e}")

    def _export_csv_from_paths(self, csv_path, paths, w_px, h_px, dpi, stitch_len_mm):
        try:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f); writer.writerow(['X_mm', 'Y_mm'])
                mm_per_px = 25.4 / dpi
                for path in paths:
                    for x, y in path: writer.writerow([f"{x * mm_per_px:.3f}", f"{(h_px - y) * mm_per_px:.3f}"])
        except Exception as e: self.status_bar.config(text=f"Error exportant CSV: {e}")

    def _finish_batch_export(self, count, total, out_dir, errors):
        self.export_button.config(state=tk.NORMAL)
        msg = f"Lot completat: {count}/{total} OK."
        if errors: msg += f" Errors en: {', '.join(errors)}"
        self.status_bar.config(text=msg)
        try:
            if sys.platform == "win32": os.startfile(out_dir)
            elif sys.platform == "darwin": subprocess.Popen(["open", out_dir])
            else: subprocess.Popen(["xdg-open", out_dir])
        except Exception: pass
        
    def export_batch(self):
        if not (hasattr(self, 'image_files') and self.image_files):
            self.status_bar.config(text="Error: No hi ha imatges per exportar.")
            return
        output_dir = os.path.join(self.folder_path_label.cget("text"), "output_vector")
        os.makedirs(output_dir, exist_ok=True)
        self.export_button.config(state=tk.DISABLED)
        threading.Thread(target=self._export_batch_thread, args=(output_dir,), daemon=True).start()

    def _export_batch_thread(self, output_dir):
        results, errors = [], []
        for i, img_path in enumerate(self.image_files):
            base_name = os.path.splitext(os.path.basename(img_path))[0]
            self.master.after(0, lambda name=base_name, num=i+1, total=len(self.image_files): self.status_bar.config(text=f"Processant {num}/{total}: {name}"))
            
            processed_img = self._process_image_for_preview(img_path)
            if processed_img is None:
                errors.append(base_name); continue

            mode = self.mode_var.get()
            svg_path = os.path.join(output_dir, f"{base_name}__{mode}.svg")
            
            vectorizer = self._vectorize_outline_potrace if mode == 'outline' else self._vectorize_centerline
            success, paths = vectorizer(processed_img, svg_path)
            
            if success:
                preset = self.preset_profile_var.get()
                h, w = processed_img.shape
                dpi = self.dpi_var.get()
                if "Làser" in preset and paths:
                    layer, color = ("CUT", 1) if "Tall" in preset else ("SCORE", 5)
                    dxf_path = os.path.join(output_dir, f"{base_name}__{mode}.dxf")
                    self._export_dxf_from_svg_paths(dxf_path, paths, w, h, dpi, layer, color)
                elif "Brodat" in preset and paths:
                    csv_path = os.path.join(output_dir, f"{base_name}__{mode}.csv")
                    self._export_csv_from_paths(csv_path, paths, w, h, dpi, self.stitch_length_mm_var.get())
                results.append(base_name)
            else:
                errors.append(base_name)
        
        self.master.after(0, self._finish_batch_export, len(results), len(self.image_files), output_dir, errors)

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tip_window, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=FONTS["UI_Tooltip"], wraplength=300)
        label.pack(ipadx=4, ipady=4)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')

    style.configure(".", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TButton", font=FONTS["UI_Button"], background=COLORS["Nexe_500"], foreground=COLORS["White"], padding=6, relief="flat", focusthickness=0, focuscolor='none')
    style.map("TButton", background=[('active', COLORS["Nexe_600"]), ('pressed', COLORS["Nexe_700"])])
    style.configure("TLabel", foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TRadiobutton", foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TCheckbutton", foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TEntry", fieldbackground=COLORS["White"], foreground=COLORS["Nexe_900"])
    style.configure("TScale", background=COLORS["Nexe_50"], troughcolor=COLORS["Nexe_200"], sliderthickness=15, relief="flat")
    style.configure("Preview.TFrame", background=COLORS["Nexe_100"])
    style.configure("TLabelframe", background=COLORS["Nexe_50"], foreground=COLORS["Nexe_800"])
    style.configure("TLabelframe.Label", font=FONTS["UI_Label"], foreground=COLORS["Nexe_800"], background=COLORS["Nexe_50"])
    style.configure("TMenubutton", background=COLORS["Nexe_100"], foreground=COLORS["Nexe_800"], arrowcolor=COLORS["Nexe_800"])
    
    app = Sketch2SVGApp(root)
    root.mainloop()

