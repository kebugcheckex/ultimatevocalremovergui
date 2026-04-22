from __future__ import annotations

# GUI modules
import time
#start_time = time.time()
import audioread
import gui_data.sv_ttk
import hashlib
import json
import librosa
import math
import natsort
import os
import pickle
import psutil
from pyglet import font as pyglet_font
import pyperclip
import base64
import queue
import shutil
import subprocess
import soundfile as sf
import torch
import urllib.request
import webbrowser
import traceback
import matchering as match
import tkinter as tk
import tkinter.ttk as ttk
from tkinter.font import Font
from tkinter import filedialog
from tkinter import messagebox
from collections import Counter
from __version__ import VERSION, PATCH, PATCH_MAC, PATCH_LINUX
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime
from gui_data.constants import *
from gui_data.app_size_values import *
from gui_data.error_handling import error_text, error_dialouge
from gui_data.old_data_check import file_check, remove_unneeded_yamls, remove_temps
from lib_v5.vr_network.model_param_init import ModelParameters
from kthread import KThread
from lib_v5 import spec_utils
from pathlib  import Path
from separate import (
    SeperateDemucs, SeperateMDX, SeperateMDXC, SeperateVR,  # Model-related
    save_format, clear_gpu_cache,  # Utility functions
    cuda_available, mps_available, #directml_available,
)
try:
    from playsound3 import playsound
except ImportError:
    from playsound import playsound
from typing import List
import onnx
import re
import sys
import yaml
from ml_collections import ConfigDict
from collections import Counter
from uvr.config.models import AppSettings
from uvr.config import persistence as persistence_helpers
from uvr.domain import audio_tools as audio_tools_module
from uvr.domain import ensemble as ensemble_module
from uvr.domain import model_data as model_data_module
from uvr.services import downloads as downloads_service_module
from uvr.services import processing as processing_service_module
from uvr.ui import actions as ui_actions_module
from uvr.ui import file_inputs as ui_file_inputs_module
from uvr.ui.menus import advanced as advanced_menus_module
from uvr.ui.menus import common as common_menus_module
from uvr.ui.menus import downloads as download_menus_module
from uvr.ui.menus import inputs as input_menus_module
from uvr.ui import widgets as widgets_module
from uvr.utils import system as system_helpers
from uvr.utils import tk_helpers as tk_helpers_module

ENABLE_DRAG_AND_DROP = os.environ.get("UVR_ENABLE_DND", "").lower() in {"1", "true", "yes", "on"}
TkinterDnD = None
DND_FILES = None

if ENABLE_DRAG_AND_DROP:
    try:
        from gui_data.tkinterdnd2 import TkinterDnD, DND_FILES
    except Exception:
        TkinterDnD = None
        DND_FILES = None

# if not is_macos:
#     import torch_directml

# is_choose_arch = cuda_available and directml_available
# is_opencl_only = not cuda_available and directml_available
# is_cuda_only = cuda_available and not directml_available

is_gpu_available = cuda_available or mps_available# or directml_available

# Change the current working directory to the directory
# this file sits in
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_PATH)  # Change the current working directory to the base path

SPLASH_DOC = os.path.join(BASE_PATH, 'tmp', 'splash.txt')

if os.path.isfile(SPLASH_DOC):
    os.remove(SPLASH_DOC)

def get_execution_time(function, name):
    start = time.time()
    function()
    end = time.time()
    time_difference = end - start
    print(f'{name} Execution Time: ', time_difference)

PREVIOUS_PATCH_WIN = 'UVR_Patch_10_6_23_4_27'

is_dnd_compatible = ENABLE_DRAG_AND_DROP and TkinterDnD is not None
banner_placement = -2

if OPERATING_SYSTEM=="Darwin":
    OPEN_FILE_func = lambda input_string:subprocess.Popen(["open", input_string])
    dnd_path_check = MAC_DND_CHECK
    banner_placement = -8
    current_patch = PATCH_MAC
    is_windows = False
    is_macos = True
    right_click_button = '<Button-2>'
    application_extension = ".dmg"
elif OPERATING_SYSTEM=="Linux":
    OPEN_FILE_func = lambda input_string:subprocess.Popen(["xdg-open", input_string])
    dnd_path_check = LINUX_DND_CHECK
    current_patch = PATCH_LINUX
    is_windows = False
    is_macos = False
    right_click_button = '<Button-3>'
    application_extension = ".zip"
elif OPERATING_SYSTEM=="Windows":
    OPEN_FILE_func = lambda input_string:os.startfile(input_string)
    dnd_path_check = WINDOWS_DND_CHECK
    current_patch = PATCH
    is_windows = True
    is_macos = False
    right_click_button = '<Button-3>'
    application_extension = ".exe"

def right_click_release_linux(window, top_win=None):
    if OPERATING_SYSTEM=="Linux":
        root.bind('<Button-1>', lambda e:window.destroy())
        if top_win:
            top_win.bind('<Button-1>', lambda e:window.destroy())

if not is_windows:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
else:
    from ctypes import windll, wintypes
    
def close_process(q:queue.Queue):
    def close_splash():
        name = "UVR_Launcher.exe"
        for process in psutil.process_iter(attrs=["name"]):
            process_name = process.info.get("name")
            
            if process_name == name:
                try:
                    process.terminate()
                    q.put(f"{name} terminated.")  # Push message to queue
                    break
                except psutil.NoSuchProcess as e:
                    q.put(f"Error terminating {name}: {e}")  # Push error to queue
                    
                    try:
                        with open(SPLASH_DOC, 'w') as f:
                            f.write('1')
                    except:
                        print('No splash screen.')

    thread = KThread(target=close_splash)
    thread.start()

def save_data(data, data_file='config.yaml'):
    """Compatibility wrapper for extracted persistence helper."""
    persistence_helpers.save_data(data=data, data_file=data_file)

def load_data(default_data=DEFAULT_DATA, data_file='config.yaml') -> dict:
    """Compatibility wrapper for extracted persistence helper."""
    return persistence_helpers.load_data(default_data=default_data, data_file=data_file)

def load_model_hash_data(dictionary):
    '''Get the model hash dictionary'''
    with open(dictionary, 'r') as d:
        return json.load(d)

def font_checker(font_file):
    chosen_font_name = None
    chosen_font_file = None
    
    try:
        if os.path.isfile(font_file):
            with open(font_file, 'r') as d:
                chosen_font = json.load(d)
                
            chosen_font_name = chosen_font["font_name"]
            if chosen_font["font_file"]:
                chosen_font_file = os.path.join(OTHER_FONT_PATH, chosen_font["font_file"])
                chosen_font_file = chosen_font_file if os.path.isfile(chosen_font_file) else None
    except Exception as e:
        print(e)
        
    chosen_font = chosen_font_name, chosen_font_file
     
    return chosen_font
        
debugger = []

#--Constants--
#Models
MODELS_DIR = os.path.join(BASE_PATH, 'models')
VR_MODELS_DIR = os.path.join(MODELS_DIR, 'VR_Models')
MDX_MODELS_DIR = os.path.join(MODELS_DIR, 'MDX_Net_Models')
DEMUCS_MODELS_DIR = os.path.join(MODELS_DIR, 'Demucs_Models')
DEMUCS_NEWER_REPO_DIR = os.path.join(DEMUCS_MODELS_DIR, 'v3_v4_repo')
MDX_MIXER_PATH = os.path.join(BASE_PATH, 'lib_v5', 'mixer.ckpt')

#Cache & Parameters
VR_HASH_DIR = os.path.join(VR_MODELS_DIR, 'model_data')
VR_HASH_JSON = os.path.join(VR_MODELS_DIR, 'model_data', 'model_data.json')
MDX_HASH_DIR = os.path.join(MDX_MODELS_DIR, 'model_data')
MDX_HASH_JSON = os.path.join(MDX_HASH_DIR, 'model_data.json')
MDX_C_CONFIG_PATH = os.path.join(MDX_HASH_DIR, 'mdx_c_configs')

DEMUCS_MODEL_NAME_SELECT = os.path.join(DEMUCS_MODELS_DIR, 'model_data', 'model_name_mapper.json')
MDX_MODEL_NAME_SELECT = os.path.join(MDX_MODELS_DIR, 'model_data', 'model_name_mapper.json')
ENSEMBLE_CACHE_DIR = os.path.join(BASE_PATH, 'gui_data', 'saved_ensembles')
SETTINGS_CACHE_DIR = os.path.join(BASE_PATH, 'gui_data', 'saved_settings')
VR_PARAM_DIR = os.path.join(BASE_PATH, 'lib_v5', 'vr_network', 'modelparams')
SAMPLE_CLIP_PATH = os.path.join(BASE_PATH, 'temp_sample_clips')
ENSEMBLE_TEMP_PATH = os.path.join(BASE_PATH, 'ensemble_temps')
DOWNLOAD_MODEL_CACHE = os.path.join(BASE_PATH, 'gui_data', 'model_manual_download.json')

#CR Text
CR_TEXT = os.path.join(BASE_PATH, 'gui_data', 'cr_text.txt')

#Style
ICON_IMG_PATH = os.path.join(BASE_PATH, 'gui_data', 'img', 'GUI-Icon.ico')
if not is_windows:
    MAIN_ICON_IMG_PATH = os.path.join(BASE_PATH, 'gui_data', 'img', 'GUI-Icon.png')

OWN_FONT_PATH = os.path.join(BASE_PATH, 'gui_data', 'own_font.json')

MAIN_FONT_NAME = 'Montserrat'
SEC_FONT_NAME = 'Century Gothic'
FONT_PATH = os.path.join(BASE_PATH, 'gui_data', 'fonts', 'Montserrat', 'Montserrat.ttf')#
SEC_FONT_PATH = os.path.join(BASE_PATH, 'gui_data', 'fonts', 'centurygothic', 'GOTHIC.ttf')#
OTHER_FONT_PATH = os.path.join(BASE_PATH, 'gui_data', 'fonts', 'other')#

FONT_MAPPER = {MAIN_FONT_NAME:FONT_PATH,
               SEC_FONT_NAME:SEC_FONT_PATH}

#Other
COMPLETE_CHIME = os.path.join(BASE_PATH, 'gui_data', 'complete_chime.wav')
FAIL_CHIME = os.path.join(BASE_PATH, 'gui_data', 'fail_chime.wav')
CHANGE_LOG = os.path.join(BASE_PATH, 'gui_data', 'change_log.txt')

DENOISER_MODEL_PATH = os.path.join(VR_MODELS_DIR, 'UVR-DeNoise-Lite.pth')
DEVERBER_MODEL_PATH = os.path.join(VR_MODELS_DIR, 'UVR-DeEcho-DeReverb.pth')

MODEL_DATA_URLS = [VR_MODEL_DATA_LINK, MDX_MODEL_DATA_LINK, MDX_MODEL_NAME_DATA_LINK, DEMUCS_MODEL_NAME_DATA_LINK]
MODEL_DATA_FILES = [VR_HASH_JSON, MDX_HASH_JSON, MDX_MODEL_NAME_SELECT, DEMUCS_MODEL_NAME_SELECT]

file_check(os.path.join(MODELS_DIR, 'Main_Models'), VR_MODELS_DIR)
file_check(os.path.join(DEMUCS_MODELS_DIR, 'v3_repo'), DEMUCS_NEWER_REPO_DIR)
remove_unneeded_yamls(DEMUCS_MODELS_DIR)

remove_temps(ENSEMBLE_TEMP_PATH)
remove_temps(SAMPLE_CLIP_PATH)
remove_temps(os.path.join(BASE_PATH, 'img'))

if not os.path.isdir(ENSEMBLE_TEMP_PATH):
    os.mkdir(ENSEMBLE_TEMP_PATH)
    
if not os.path.isdir(SAMPLE_CLIP_PATH):
    os.mkdir(SAMPLE_CLIP_PATH)

model_hash_table = {}
data = persistence_helpers.load_settings(DEFAULT_DATA).to_legacy_dict()


def normalize_app_settings_dict(data: dict | None) -> dict:
    """Normalize legacy settings dicts against the current defaults."""
    return AppSettings.from_legacy_dict(data, DEFAULT_DATA).to_legacy_dict()


def build_model_data_settings() -> model_data_module.ModelDataSettings:
    device_set = root.device_set_var.get()
    return model_data_module.ModelDataSettings(
        device_set=device_set,
        is_deverb_vocals=root.is_deverb_vocals_var.get(),
        deverb_vocal_opt=DEVERB_MAPPER[root.deverb_vocal_opt_var.get()],
        is_denoise_model=root.denoise_option_var.get() == DENOISE_M,
        is_gpu_conversion=root.is_gpu_conversion_var.get(),
        is_normalization=root.is_normalization_var.get(),
        is_use_opencl=False,
        is_primary_stem_only=root.is_primary_stem_only_var.get(),
        is_secondary_stem_only=root.is_secondary_stem_only_var.get(),
        is_primary_stem_only_demucs=root.is_primary_stem_only_Demucs_var.get(),
        is_secondary_stem_only_demucs=root.is_secondary_stem_only_Demucs_var.get(),
        denoise_option=root.denoise_option_var.get(),
        is_mdx_c_seg_def=root.is_mdx_c_seg_def_var.get(),
        mdx_batch_size=root.mdx_batch_size_var.get(),
        mdxnet_stems=root.mdxnet_stems_var.get(),
        overlap=root.overlap_var.get(),
        overlap_mdx=root.overlap_mdx_var.get(),
        overlap_mdx23=root.overlap_mdx23_var.get(),
        semitone_shift=root.semitone_shift_var.get(),
        is_match_frequency_pitch=root.is_match_frequency_pitch_var.get(),
        is_mdx23_combine_stems=root.is_mdx23_combine_stems_var.get(),
        wav_type_set=root.wav_type_set,
        mp3_bit_set=root.mp3_bit_set_var.get(),
        save_format=root.save_format_var.get(),
        is_invert_spec=root.is_invert_spec_var.get(),
        demucs_stems=root.demucs_stems_var.get(),
        is_demucs_combine_stems=root.is_demucs_combine_stems_var.get(),
        chosen_process_method=root.chosen_process_method_var.get(),
        is_save_inst_set_vocal_splitter=root.is_save_inst_set_vocal_splitter_var.get(),
        ensemble_main_stem=root.ensemble_main_stem_var.get(),
        vr_is_secondary_model_activate=root.vr_is_secondary_model_activate_var.get(),
        aggression_setting=root.aggression_setting_var.get(),
        is_tta=root.is_tta_var.get(),
        is_post_process=root.is_post_process_var.get(),
        window_size=root.window_size_var.get(),
        batch_size=root.batch_size_var.get(),
        crop_size=root.crop_size_var.get(),
        is_high_end_process=root.is_high_end_process_var.get(),
        post_process_threshold=root.post_process_threshold_var.get(),
        vr_hash_mapper=root.vr_hash_MAPPER,
        mdx_is_secondary_model_activate=root.mdx_is_secondary_model_activate_var.get(),
        margin=root.margin_var.get(),
        mdx_segment_size=root.mdx_segment_size_var.get(),
        mdx_hash_mapper=root.mdx_hash_MAPPER,
        compensate=root.compensate_var.get(),
        demucs_is_secondary_model_activate=root.demucs_is_secondary_model_activate_var.get(),
        is_demucs_pre_proc_model_activate=root.is_demucs_pre_proc_model_activate_var.get(),
        is_demucs_pre_proc_model_inst_mix=root.is_demucs_pre_proc_model_inst_mix_var.get(),
        margin_demucs=root.margin_demucs_var.get(),
        shifts=root.shifts_var.get(),
        is_split_mode=root.is_split_mode_var.get(),
        segment=root.segment_var.get(),
        is_chunk_demucs=root.is_chunk_demucs_var.get(),
        mdx_name_select_mapper=root.mdx_name_select_MAPPER,
        demucs_name_select_mapper=root.demucs_name_select_MAPPER,
    )


def build_audio_tool_settings() -> audio_tools_module.AudioToolSettings:
    return audio_tools_module.AudioToolSettings(
        export_path=root.export_path_var.get(),
        wav_type_set=root.wav_type_set,
        is_normalization=root.is_normalization_var.get(),
        is_testing_audio=root.is_testing_audio_var.get(),
        save_format=root.save_format_var.get(),
        mp3_bit_set=root.mp3_bit_set_var.get(),
        align_window=TIME_WINDOW_MAPPER[root.time_window_var.get()],
        align_intro_val=INTRO_MAPPER[root.intro_analysis_var.get()],
        db_analysis_val=VOLUME_MAPPER[root.db_analysis_var.get()],
        is_save_align=root.is_save_align_var.get(),
        is_match_silence=root.is_match_silence_var.get(),
        is_spec_match=root.is_spec_match_var.get(),
        phase_option=root.phase_option_var.get(),
        phase_shifts=PHASE_SHIFTS_OPT[root.phase_shifts_var.get()],
        time_stretch_rate=root.time_stretch_rate_var.get(),
        pitch_rate=root.pitch_rate_var.get(),
        is_time_correction=root.is_time_correction_var.get(),
    )


def build_ensembler_settings() -> ensemble_module.EnsemblerSettings:
    chosen_ensemble = root.chosen_ensemble_var.get()
    chosen_ensemble_name = chosen_ensemble.replace(" ", "_") if chosen_ensemble != CHOOSE_ENSEMBLE_OPTION else "Ensembled"
    ensemble_main_stem = root.ensemble_main_stem_var.get().partition("/")
    return ensemble_module.EnsemblerSettings(
        is_save_all_outputs_ensemble=root.is_save_all_outputs_ensemble_var.get(),
        chosen_ensemble_name=chosen_ensemble_name,
        ensemble_type=root.ensemble_type_var.get(),
        ensemble_main_stem_pair=(ensemble_main_stem[0], ensemble_main_stem[2]),
        export_path=root.export_path_var.get(),
        is_append_ensemble_name=root.is_append_ensemble_name_var.get(),
        is_testing_audio=root.is_testing_audio_var.get(),
        is_normalization=root.is_normalization_var.get(),
        is_wav_ensemble=root.is_wav_ensemble_var.get(),
        wav_type_set=root.wav_type_set,
        mp3_bit_set=root.mp3_bit_set_var.get(),
        save_format=root.save_format_var.get(),
        choose_algorithm=root.choose_algorithm_var.get(),
    )


def resolve_model_data_popup(
    process_method: str,
    model_name: str,
    model_hash: str,
    model_path: str,
    is_change_def: bool,
):
    if not is_change_def:
        confirm = messagebox.askyesno(
            title=UNRECOGNIZED_MODEL[0],
            message=f'"{model_name}"{UNRECOGNIZED_MODEL[1]}',
            parent=root,
        )
        if not confirm:
            return None

    if process_method == VR_ARCH_TYPE:
        root.pop_up_vr_param(model_hash)
        return root.vr_model_params
    if process_method == MDX_ARCH_TYPE:
        root.pop_up_mdx_model(model_hash, model_path)
        return root.mdx_model_params
    return None


def build_model_data_resolvers() -> model_data_module.ModelDataResolvers:
    return model_data_module.ModelDataResolvers(
        return_ensemble_stems=root.return_ensemble_stems,
        check_only_selection_stem=root.check_only_selection_stem,
        determine_secondary_model=root.process_determine_secondary_model,
        determine_demucs_pre_proc_model=root.process_determine_demucs_pre_proc_model,
        determine_vocal_split_model=root.process_determine_vocal_split_model,
        resolve_popup_model_data=resolve_model_data_popup,
    )

def drop(event, accept_mode: str = 'files'):
    path = event.data
    if accept_mode == 'folder':
        path = path.replace('{', '').replace('}', '')
        if not os.path.isdir(path):
            messagebox.showerror(parent=root,
                                    title=INVALID_FOLDER_ERROR_TEXT[0],
                                    message=INVALID_FOLDER_ERROR_TEXT[1])
            return
        root.export_path_var.set(path)
    elif accept_mode in ['files', FILE_1, FILE_2, FILE_1_LB, FILE_2_LB]:
        path = path.replace("{", "").replace("}", "")
        for dnd_file in dnd_path_check:
            path = path.replace(f" {dnd_file}", f";{dnd_file}")
        path = path.split(';')
        path[-1] = path[-1].replace(';', '')
        
        if accept_mode == 'files':
            root.inputPaths = tuple(path)
            root.process_input_selections()
            root.update_inputPaths()
        elif accept_mode in [FILE_1, FILE_2]:
            if len(path) == 2:
                root.select_audiofile(path[0])
                root.select_audiofile(path[1], is_primary=False)
                root.DualBatch_inputPaths = []
                root.check_dual_paths()
            elif len(path) == 1:
                if accept_mode == FILE_1:
                    root.select_audiofile(path[0])
                else:
                    root.select_audiofile(path[0], is_primary=False)

        elif accept_mode in [FILE_1_LB, FILE_2_LB]:
            return path
    else:
        return    

class ModelData():
    def __init__(self, model_name: str, 
                 selected_process_method=ENSEMBLE_MODE, 
                 is_secondary_model=False, 
                 primary_model_primary_stem=None, 
                 is_primary_model_primary_stem_only=False, 
                 is_primary_model_secondary_stem_only=False, 
                 is_pre_proc_model=False,
                 is_dry_check=False,
                 is_change_def=False,
                 is_get_hash_dir_only=False,
                 is_vocal_split_model=False):

        device_set = root.device_set_var.get()
        self.DENOISER_MODEL = DENOISER_MODEL_PATH
        self.DEVERBER_MODEL = DEVERBER_MODEL_PATH
        self.is_deverb_vocals = root.is_deverb_vocals_var.get() if os.path.isfile(DEVERBER_MODEL_PATH) else False
        self.deverb_vocal_opt = DEVERB_MAPPER[root.deverb_vocal_opt_var.get()]
        self.is_denoise_model = True if root.denoise_option_var.get() == DENOISE_M and os.path.isfile(DENOISER_MODEL_PATH) else False
        self.is_gpu_conversion = 0 if root.is_gpu_conversion_var.get() else -1
        self.is_normalization = root.is_normalization_var.get()#
        self.is_use_opencl = False#True if is_opencl_only else root.is_use_opencl_var.get()
        self.is_primary_stem_only = root.is_primary_stem_only_var.get()
        self.is_secondary_stem_only = root.is_secondary_stem_only_var.get()
        self.is_denoise = True if not root.denoise_option_var.get() == DENOISE_NONE else False
        self.is_mdx_c_seg_def = root.is_mdx_c_seg_def_var.get()#
        self.mdx_batch_size = 1 if root.mdx_batch_size_var.get() == DEF_OPT else int(root.mdx_batch_size_var.get())
        self.mdxnet_stem_select = root.mdxnet_stems_var.get() 
        self.overlap = float(root.overlap_var.get()) if not root.overlap_var.get() == DEFAULT else 0.25
        self.overlap_mdx = float(root.overlap_mdx_var.get()) if not root.overlap_mdx_var.get() == DEFAULT else root.overlap_mdx_var.get()
        self.overlap_mdx23 = int(float(root.overlap_mdx23_var.get()))
        self.semitone_shift = float(root.semitone_shift_var.get())
        self.is_pitch_change = False if self.semitone_shift == 0 else True
        self.is_match_frequency_pitch = root.is_match_frequency_pitch_var.get()
        self.is_mdx_ckpt = False
        self.is_mdx_c = False
        self.is_mdx_combine_stems = root.is_mdx23_combine_stems_var.get()#
        self.mdx_c_configs = None
        self.mdx_model_stems = []
        self.mdx_dim_f_set = None
        self.mdx_dim_t_set = None
        self.mdx_stem_count = 1
        self.compensate = None
        self.mdx_n_fft_scale_set = None
        self.wav_type_set = root.wav_type_set#
        self.device_set = device_set.split(':')[-1].strip() if ':' in device_set else device_set
        self.mp3_bit_set = root.mp3_bit_set_var.get()
        self.save_format = root.save_format_var.get()
        self.is_invert_spec = root.is_invert_spec_var.get()#
        self.is_mixer_mode = False#
        self.demucs_stems = root.demucs_stems_var.get()
        self.is_demucs_combine_stems = root.is_demucs_combine_stems_var.get()
        self.demucs_source_list = []
        self.demucs_stem_count = 0
        self.mixer_path = MDX_MIXER_PATH
        self.model_name = model_name
        self.process_method = selected_process_method
        self.model_status = False if self.model_name == CHOOSE_MODEL or self.model_name == NO_MODEL else True
        self.primary_stem = None
        self.secondary_stem = None
        self.primary_stem_native = None
        self.is_ensemble_mode = False
        self.ensemble_primary_stem = None
        self.ensemble_secondary_stem = None
        self.primary_model_primary_stem = primary_model_primary_stem
        self.is_secondary_model = True if is_vocal_split_model else is_secondary_model
        self.secondary_model = None
        self.secondary_model_scale = None
        self.demucs_4_stem_added_count = 0
        self.is_demucs_4_stem_secondaries = False
        self.is_4_stem_ensemble = False
        self.pre_proc_model = None
        self.pre_proc_model_activated = False
        self.is_pre_proc_model = is_pre_proc_model
        self.is_dry_check = is_dry_check
        self.model_samplerate = 44100
        self.model_capacity = 32, 128
        self.is_vr_51_model = False
        self.is_demucs_pre_proc_model_inst_mix = False
        self.manual_download_Button = None
        self.secondary_model_4_stem = []
        self.secondary_model_4_stem_scale = []
        self.secondary_model_4_stem_names = []
        self.secondary_model_4_stem_model_names_list = []
        self.all_models = []
        self.secondary_model_other = None
        self.secondary_model_scale_other = None
        self.secondary_model_bass = None
        self.secondary_model_scale_bass = None
        self.secondary_model_drums = None
        self.secondary_model_scale_drums = None
        self.is_multi_stem_ensemble = False
        self.is_karaoke = False
        self.is_bv_model = False
        self.bv_model_rebalance = 0
        self.is_sec_bv_rebalance = False
        self.is_change_def = is_change_def
        self.model_hash_dir = None
        self.is_get_hash_dir_only = is_get_hash_dir_only
        self.is_secondary_model_activated = False
        self.vocal_split_model = None
        self.is_vocal_split_model = is_vocal_split_model
        self.is_vocal_split_model_activated = False
        self.is_save_inst_vocal_splitter = root.is_save_inst_set_vocal_splitter_var.get()
        self.is_inst_only_voc_splitter = root.check_only_selection_stem(INST_STEM_ONLY)
        self.is_save_vocal_only = root.check_only_selection_stem(IS_SAVE_VOC_ONLY)

        if selected_process_method == ENSEMBLE_MODE:
            self.process_method, _, self.model_name = model_name.partition(ENSEMBLE_PARTITION)
            self.model_and_process_tag = model_name
            self.ensemble_primary_stem, self.ensemble_secondary_stem = root.return_ensemble_stems()
            
            is_not_secondary_or_pre_proc = not is_secondary_model and not is_pre_proc_model
            self.is_ensemble_mode = is_not_secondary_or_pre_proc
            
            if root.ensemble_main_stem_var.get() == FOUR_STEM_ENSEMBLE:
                self.is_4_stem_ensemble = self.is_ensemble_mode
            elif root.ensemble_main_stem_var.get() == MULTI_STEM_ENSEMBLE and root.chosen_process_method_var.get() == ENSEMBLE_MODE:
                self.is_multi_stem_ensemble = True

            is_not_vocal_stem = self.ensemble_primary_stem != VOCAL_STEM
            self.pre_proc_model_activated = root.is_demucs_pre_proc_model_activate_var.get() if is_not_vocal_stem else False

        if self.process_method == VR_ARCH_TYPE:
            self.is_secondary_model_activated = root.vr_is_secondary_model_activate_var.get() if not is_secondary_model else False
            self.aggression_setting = float(int(root.aggression_setting_var.get())/100)
            self.is_tta = root.is_tta_var.get()
            self.is_post_process = root.is_post_process_var.get()
            self.window_size = int(root.window_size_var.get())
            self.batch_size = 1 if root.batch_size_var.get() == DEF_OPT else int(root.batch_size_var.get())
            self.crop_size = int(root.crop_size_var.get())
            self.is_high_end_process = 'mirroring' if root.is_high_end_process_var.get() else 'None'
            self.post_process_threshold = float(root.post_process_threshold_var.get())
            self.model_capacity = 32, 128
            self.model_path = os.path.join(VR_MODELS_DIR, f"{self.model_name}.pth")
            self.get_model_hash()
            if self.model_hash:
                self.model_hash_dir = os.path.join(VR_HASH_DIR, f"{self.model_hash}.json")
                if is_change_def:
                    self.model_data = self.change_model_data()
                else:
                    self.model_data = self.get_model_data(VR_HASH_DIR, root.vr_hash_MAPPER) if not self.model_hash == WOOD_INST_MODEL_HASH else WOOD_INST_PARAMS
                if self.model_data:
                    vr_model_param = os.path.join(VR_PARAM_DIR, "{}.json".format(self.model_data["vr_model_param"]))
                    self.primary_stem = self.model_data["primary_stem"]
                    self.secondary_stem = secondary_stem(self.primary_stem)
                    self.vr_model_param = ModelParameters(vr_model_param)
                    self.model_samplerate = self.vr_model_param.param['sr']
                    self.primary_stem_native = self.primary_stem
                    if "nout" in self.model_data.keys() and "nout_lstm" in self.model_data.keys():
                        self.model_capacity = self.model_data["nout"], self.model_data["nout_lstm"]
                        self.is_vr_51_model = True
                    self.check_if_karaokee_model()
   
                else:
                    self.model_status = False
                
        if self.process_method == MDX_ARCH_TYPE:
            self.is_secondary_model_activated = root.mdx_is_secondary_model_activate_var.get() if not is_secondary_model else False
            self.margin = int(root.margin_var.get())
            self.chunks = 0
            self.mdx_segment_size = int(root.mdx_segment_size_var.get())
            self.get_mdx_model_path()
            self.get_model_hash()
            if self.model_hash:
                self.model_hash_dir = os.path.join(MDX_HASH_DIR, f"{self.model_hash}.json")
                if is_change_def:
                    self.model_data = self.change_model_data()
                else:
                    self.model_data = self.get_model_data(MDX_HASH_DIR, root.mdx_hash_MAPPER)
                if self.model_data:
                    
                    if "config_yaml" in self.model_data:
                        self.is_mdx_c = True
                        config_path = os.path.join(MDX_C_CONFIG_PATH, self.model_data["config_yaml"])
                        if os.path.isfile(config_path):
                            with open(config_path) as f:
                                config = ConfigDict(yaml.load(f, Loader=yaml.FullLoader))

                            self.mdx_c_configs = config
                                
                            if self.mdx_c_configs.training.target_instrument:
                                # Use target_instrument as the primary stem and set 4-stem ensemble to False
                                target = self.mdx_c_configs.training.target_instrument
                                self.mdx_model_stems = [target]
                                self.primary_stem = target
                            else:
                                # If no specific target_instrument, use all instruments in the training config
                                self.mdx_model_stems = self.mdx_c_configs.training.instruments
                                self.mdx_stem_count = len(self.mdx_model_stems)
                                
                                # Set primary stem based on stem count
                                if self.mdx_stem_count == 2:
                                    self.primary_stem = self.mdx_model_stems[0]
                                else:
                                    self.primary_stem = self.mdxnet_stem_select
                                
                                # Update mdxnet_stem_select based on ensemble mode
                                if self.is_ensemble_mode:
                                    self.mdxnet_stem_select = self.ensemble_primary_stem
                        else:
                            self.model_status = False
                    else:
                        self.compensate = self.model_data["compensate"] if root.compensate_var.get() == AUTO_SELECT else float(root.compensate_var.get())
                        self.mdx_dim_f_set = self.model_data["mdx_dim_f_set"]
                        self.mdx_dim_t_set = self.model_data["mdx_dim_t_set"]
                        self.mdx_n_fft_scale_set = self.model_data["mdx_n_fft_scale_set"]
                        self.primary_stem = self.model_data["primary_stem"]
                        self.primary_stem_native = self.model_data["primary_stem"]
                        self.check_if_karaokee_model()
                        
                    self.secondary_stem = secondary_stem(self.primary_stem)
                else:
                    self.model_status = False

        if self.process_method == DEMUCS_ARCH_TYPE:
            self.is_secondary_model_activated = root.demucs_is_secondary_model_activate_var.get() if not is_secondary_model else False
            if not self.is_ensemble_mode:
                self.pre_proc_model_activated = root.is_demucs_pre_proc_model_activate_var.get() if not root.demucs_stems_var.get() in [VOCAL_STEM, INST_STEM] else False
            self.margin_demucs = int(root.margin_demucs_var.get())
            self.chunks_demucs = 0
            self.shifts = int(root.shifts_var.get())
            self.is_split_mode = root.is_split_mode_var.get()
            self.segment = root.segment_var.get()
            self.is_chunk_demucs = root.is_chunk_demucs_var.get()
            self.is_primary_stem_only = root.is_primary_stem_only_var.get() if self.is_ensemble_mode else root.is_primary_stem_only_Demucs_var.get() 
            self.is_secondary_stem_only = root.is_secondary_stem_only_var.get() if self.is_ensemble_mode else root.is_secondary_stem_only_Demucs_var.get()
            self.get_demucs_model_data()
            self.get_demucs_model_path()
            
        if self.model_status:
            self.model_basename = os.path.splitext(os.path.basename(self.model_path))[0]
        else:
            self.model_basename = None
            
        self.pre_proc_model_activated = self.pre_proc_model_activated if not self.is_secondary_model else False
        
        self.is_primary_model_primary_stem_only = is_primary_model_primary_stem_only
        self.is_primary_model_secondary_stem_only = is_primary_model_secondary_stem_only

        is_secondary_activated_and_status = self.is_secondary_model_activated and self.model_status
        is_demucs = self.process_method == DEMUCS_ARCH_TYPE
        is_all_stems = root.demucs_stems_var.get() == ALL_STEMS
        is_valid_ensemble = not self.is_ensemble_mode and is_all_stems and is_demucs
        is_multi_stem_ensemble_demucs = self.is_multi_stem_ensemble and is_demucs

        if is_secondary_activated_and_status:
            if is_valid_ensemble or self.is_4_stem_ensemble or is_multi_stem_ensemble_demucs:
                for key in DEMUCS_4_SOURCE_LIST:
                    self.secondary_model_data(key)
                    self.secondary_model_4_stem.append(self.secondary_model)
                    self.secondary_model_4_stem_scale.append(self.secondary_model_scale)
                    self.secondary_model_4_stem_names.append(key)
                
                self.demucs_4_stem_added_count = sum(i is not None for i in self.secondary_model_4_stem)
                self.is_secondary_model_activated = any(i is not None for i in self.secondary_model_4_stem)
                self.demucs_4_stem_added_count -= 1 if self.is_secondary_model_activated else 0
                
                if self.is_secondary_model_activated:
                    self.secondary_model_4_stem_model_names_list = [i.model_basename if i is not None else None for i in self.secondary_model_4_stem]
                    self.is_demucs_4_stem_secondaries = True
            else:
                primary_stem = self.ensemble_primary_stem if self.is_ensemble_mode and is_demucs else self.primary_stem
                self.secondary_model_data(primary_stem)

        if self.process_method == DEMUCS_ARCH_TYPE and not is_secondary_model:
            if self.demucs_stem_count >= 3 and self.pre_proc_model_activated:
                self.pre_proc_model = root.process_determine_demucs_pre_proc_model(self.primary_stem)
                self.pre_proc_model_activated = True if self.pre_proc_model else False
                self.is_demucs_pre_proc_model_inst_mix = root.is_demucs_pre_proc_model_inst_mix_var.get() if self.pre_proc_model else False

        if self.is_vocal_split_model and self.model_status:
            self.is_secondary_model_activated = False
            if self.is_bv_model:
                primary = BV_VOCAL_STEM if self.primary_stem_native == VOCAL_STEM else LEAD_VOCAL_STEM
            else:
                primary = LEAD_VOCAL_STEM if self.primary_stem_native == VOCAL_STEM else BV_VOCAL_STEM
            self.primary_stem, self.secondary_stem = primary, secondary_stem(primary)
            
        self.vocal_splitter_model_data()
            
    def vocal_splitter_model_data(self):
        if not self.is_secondary_model and self.model_status:
            self.vocal_split_model = root.process_determine_vocal_split_model()
            self.is_vocal_split_model_activated = True if self.vocal_split_model else False
            
            if self.vocal_split_model:
                if self.vocal_split_model.bv_model_rebalance:
                    self.is_sec_bv_rebalance = True
            
    def secondary_model_data(self, primary_stem):
        secondary_model_data = root.process_determine_secondary_model(self.process_method, primary_stem, self.is_primary_stem_only, self.is_secondary_stem_only)
        self.secondary_model = secondary_model_data[0]
        self.secondary_model_scale = secondary_model_data[1]
        self.is_secondary_model_activated = False if not self.secondary_model else True
        if self.secondary_model:
            self.is_secondary_model_activated = False if self.secondary_model.model_basename == self.model_basename else True
            
        #print("self.is_secondary_model_activated: ", self.is_secondary_model_activated)
              
    def check_if_karaokee_model(self):
        if IS_KARAOKEE in self.model_data.keys():
            self.is_karaoke = self.model_data[IS_KARAOKEE]
        if IS_BV_MODEL in self.model_data.keys():
            self.is_bv_model = self.model_data[IS_BV_MODEL]#
        if IS_BV_MODEL_REBAL in self.model_data.keys() and self.is_bv_model:
            self.bv_model_rebalance = self.model_data[IS_BV_MODEL_REBAL]#
   
    def get_mdx_model_path(self):
        
        if self.model_name.endswith(CKPT):
            self.is_mdx_ckpt = True

        ext = '' if self.is_mdx_ckpt else ONNX
        
        for file_name, chosen_mdx_model in root.mdx_name_select_MAPPER.items():
            if self.model_name in chosen_mdx_model:
                if file_name.endswith(CKPT):
                    ext = ''
                self.model_path = os.path.join(MDX_MODELS_DIR, f"{file_name}{ext}")
                break
        else:
            self.model_path = os.path.join(MDX_MODELS_DIR, f"{self.model_name}{ext}")
            
        self.mixer_path = os.path.join(MDX_MODELS_DIR, f"mixer_val.ckpt")
    
    def get_demucs_model_path(self):
        
        demucs_newer = self.demucs_version in {DEMUCS_V3, DEMUCS_V4}
        demucs_model_dir = DEMUCS_NEWER_REPO_DIR if demucs_newer else DEMUCS_MODELS_DIR
        
        for file_name, chosen_model in root.demucs_name_select_MAPPER.items():
            if self.model_name == chosen_model:
                self.model_path = os.path.join(demucs_model_dir, file_name)
                break
        else:
            self.model_path = os.path.join(DEMUCS_NEWER_REPO_DIR, f'{self.model_name}.yaml')

    def get_demucs_model_data(self):

        self.demucs_version = DEMUCS_V4

        for key, value in DEMUCS_VERSION_MAPPER.items():
            if value in self.model_name:
                self.demucs_version = key

        if DEMUCS_UVR_MODEL in self.model_name:
            self.demucs_source_list, self.demucs_source_map, self.demucs_stem_count = DEMUCS_2_SOURCE, DEMUCS_2_SOURCE_MAPPER, 2
        else:
            self.demucs_source_list, self.demucs_source_map, self.demucs_stem_count = DEMUCS_4_SOURCE, DEMUCS_4_SOURCE_MAPPER, 4

        if not self.is_ensemble_mode:
            self.primary_stem = PRIMARY_STEM if self.demucs_stems == ALL_STEMS else self.demucs_stems
            self.secondary_stem = secondary_stem(self.primary_stem)
            
    def get_model_data(self, model_hash_dir, hash_mapper:dict):
        model_settings_json = os.path.join(model_hash_dir, f"{self.model_hash}.json")

        if os.path.isfile(model_settings_json):
            with open(model_settings_json, 'r') as json_file:
                return json.load(json_file)
        else:
            for hash, settings in hash_mapper.items():
                if self.model_hash in hash:
                    return settings

            return self.get_model_data_from_popup()

    def change_model_data(self):
        if self.is_get_hash_dir_only:
            return None
        else:
            return self.get_model_data_from_popup()

    def get_model_data_from_popup(self):
        if self.is_dry_check:
            return None
            
        if not self.is_change_def:
            confirm = messagebox.askyesno(
                title=UNRECOGNIZED_MODEL[0],
                message=f'"{self.model_name}"{UNRECOGNIZED_MODEL[1]}',
                parent=root
            )
            if not confirm:
                return None
        
        if self.process_method == VR_ARCH_TYPE:
            root.pop_up_vr_param(self.model_hash)
            return root.vr_model_params
        elif self.process_method == MDX_ARCH_TYPE:
            root.pop_up_mdx_model(self.model_hash, self.model_path)
            return root.mdx_model_params

    def get_model_hash(self):
        self.model_hash = None
        
        if not os.path.isfile(self.model_path):
            self.model_status = False
            self.model_hash is None
        else:
            if model_hash_table:
                for (key, value) in model_hash_table.items():
                    if self.model_path == key:
                        self.model_hash = value
                        break
                    
            if not self.model_hash:
                try:
                    with open(self.model_path, 'rb') as f:
                        f.seek(- 10000 * 1024, 2)
                        self.model_hash = hashlib.md5(f.read()).hexdigest()
                except:
                    self.model_hash = hashlib.md5(open(self.model_path,'rb').read()).hexdigest()
                    
                table_entry = {self.model_path: self.model_hash}
                model_hash_table.update(table_entry)
                
        #print(self.model_name," - ", self.model_hash)

class ModelData(model_data_module.ModelData):
    def __init__(self, model_name: str,
                 selected_process_method=ENSEMBLE_MODE,
                 is_secondary_model=False,
                 primary_model_primary_stem=None,
                 is_primary_model_primary_stem_only=False,
                 is_primary_model_secondary_stem_only=False,
                 is_pre_proc_model=False,
                 is_dry_check=False,
                 is_change_def=False,
                 is_get_hash_dir_only=False,
                 is_vocal_split_model=False):
        super().__init__(
            model_name=model_name,
            selected_process_method=selected_process_method,
            is_secondary_model=is_secondary_model,
            primary_model_primary_stem=primary_model_primary_stem,
            is_primary_model_primary_stem_only=is_primary_model_primary_stem_only,
            is_primary_model_secondary_stem_only=is_primary_model_secondary_stem_only,
            is_pre_proc_model=is_pre_proc_model,
            is_dry_check=is_dry_check,
            is_change_def=is_change_def,
            is_get_hash_dir_only=is_get_hash_dir_only,
            is_vocal_split_model=is_vocal_split_model,
            settings=build_model_data_settings(),
            resolvers=build_model_data_resolvers(),
        )

class Ensembler():
    def __init__(self, is_manual_ensemble=False):
        self.is_save_all_outputs_ensemble = root.is_save_all_outputs_ensemble_var.get()
        chosen_ensemble_name = '{}'.format(root.chosen_ensemble_var.get().replace(" ", "_")) if not root.chosen_ensemble_var.get() == CHOOSE_ENSEMBLE_OPTION else 'Ensembled'
        ensemble_algorithm = root.ensemble_type_var.get().partition("/")
        ensemble_main_stem_pair = root.ensemble_main_stem_var.get().partition("/")
        time_stamp = round(time.time())
        self.audio_tool = MANUAL_ENSEMBLE
        self.main_export_path = Path(root.export_path_var.get())
        self.chosen_ensemble = f"_{chosen_ensemble_name}" if root.is_append_ensemble_name_var.get() else ''
        ensemble_folder_name = self.main_export_path if self.is_save_all_outputs_ensemble else ENSEMBLE_TEMP_PATH
        self.ensemble_folder_name = os.path.join(ensemble_folder_name, '{}_Outputs_{}'.format(chosen_ensemble_name, time_stamp))
        self.is_testing_audio = f"{time_stamp}_" if root.is_testing_audio_var.get() else ''
        self.primary_algorithm = ensemble_algorithm[0]
        self.secondary_algorithm = ensemble_algorithm[2]
        self.ensemble_primary_stem = ensemble_main_stem_pair[0]
        self.ensemble_secondary_stem = ensemble_main_stem_pair[2]
        self.is_normalization = root.is_normalization_var.get()
        self.is_wav_ensemble = root.is_wav_ensemble_var.get()
        self.wav_type_set = root.wav_type_set
        self.mp3_bit_set = root.mp3_bit_set_var.get()
        self.save_format = root.save_format_var.get()
        if not is_manual_ensemble:
            os.mkdir(self.ensemble_folder_name)

    def ensemble_outputs(self, audio_file_base, export_path, stem, is_4_stem=False, is_inst_mix=False):
        """Processes the given outputs and ensembles them with the chosen algorithm"""
        
        if is_4_stem:
            algorithm = root.ensemble_type_var.get()
            stem_tag = stem
        else:
            if is_inst_mix:
                algorithm = self.secondary_algorithm
                stem_tag = f"{self.ensemble_secondary_stem} {INST_STEM}"
            else:
                algorithm = self.primary_algorithm if stem == PRIMARY_STEM else self.secondary_algorithm
                stem_tag = self.ensemble_primary_stem if stem == PRIMARY_STEM else self.ensemble_secondary_stem

        stem_outputs = self.get_files_to_ensemble(folder=export_path, prefix=audio_file_base, suffix=f"_({stem_tag}).wav")
        audio_file_output = f"{self.is_testing_audio}{audio_file_base}{self.chosen_ensemble}_({stem_tag})"
        stem_save_path = os.path.join('{}'.format(self.main_export_path),'{}.wav'.format(audio_file_output))
        
        #print("get_files_to_ensemble: ", stem_outputs)
        
        if len(stem_outputs) > 1:
            spec_utils.ensemble_inputs(stem_outputs, algorithm, self.is_normalization, self.wav_type_set, stem_save_path, is_wave=self.is_wav_ensemble)
            save_format(stem_save_path, self.save_format, self.mp3_bit_set)
        
        if self.is_save_all_outputs_ensemble:
            for i in stem_outputs:
                save_format(i, self.save_format, self.mp3_bit_set)
        else:
            for i in stem_outputs:
                try:
                    os.remove(i)
                except Exception as e:
                    print(e)

    def ensemble_manual(self, audio_inputs, audio_file_base, is_bulk=False):
        """Processes the given outputs and ensembles them with the chosen algorithm"""
        
        is_mv_sep = True
        
        if is_bulk:
            number_list = list(set([os.path.basename(i).split("_")[0] for i in audio_inputs]))
            for n in number_list:
                current_list = [i for i in audio_inputs if os.path.basename(i).startswith(n)]
                audio_file_base = os.path.basename(current_list[0]).split('.wav')[0]
                stem_testing = "instrum" if "Instrumental" in audio_file_base else "vocals"
                if is_mv_sep:
                    audio_file_base = audio_file_base.split("_")
                    audio_file_base = f"{audio_file_base[1]}_{audio_file_base[2]}_{stem_testing}"
                self.ensemble_manual_process(current_list, audio_file_base, is_bulk)
        else:
            self.ensemble_manual_process(audio_inputs, audio_file_base, is_bulk)
            
    def ensemble_manual_process(self, audio_inputs, audio_file_base, is_bulk):
        
        algorithm = root.choose_algorithm_var.get()
        algorithm_text = "" if is_bulk else f"_({root.choose_algorithm_var.get()})"
        stem_save_path = os.path.join('{}'.format(self.main_export_path),'{}{}{}.wav'.format(self.is_testing_audio, audio_file_base, algorithm_text))
        spec_utils.ensemble_inputs(audio_inputs, algorithm, self.is_normalization, self.wav_type_set, stem_save_path, is_wave=self.is_wav_ensemble)
        save_format(stem_save_path, self.save_format, self.mp3_bit_set)

    def get_files_to_ensemble(self, folder="", prefix="", suffix=""):
        """Grab all the files to be ensembled"""
        
        return [os.path.join(folder, i) for i in os.listdir(folder) if i.startswith(prefix) and i.endswith(suffix)]

    def combine_audio(self, audio_inputs, audio_file_base):
        save_format_ = lambda save_path:save_format(save_path, root.save_format_var.get(), root.mp3_bit_set_var.get())
        spec_utils.combine_audio(audio_inputs, 
                                 os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}"), 
                                 self.wav_type_set,
                                 save_format=save_format_)

class AudioTools():
    def __init__(self, audio_tool):
        time_stamp = round(time.time())
        self.audio_tool = audio_tool
        self.main_export_path = Path(root.export_path_var.get())
        self.wav_type_set = root.wav_type_set
        self.is_normalization = root.is_normalization_var.get()
        self.is_testing_audio = f"{time_stamp}_" if root.is_testing_audio_var.get() else ''
        self.save_format = lambda save_path:save_format(save_path, root.save_format_var.get(), root.mp3_bit_set_var.get())
        self.align_window = TIME_WINDOW_MAPPER[root.time_window_var.get()]
        self.align_intro_val = INTRO_MAPPER[root.intro_analysis_var.get()]
        self.db_analysis_val = VOLUME_MAPPER[root.db_analysis_var.get()]
        self.is_save_align = root.is_save_align_var.get()#
        self.is_match_silence = root.is_match_silence_var.get()#
        self.is_spec_match = root.is_spec_match_var.get()
        
        self.phase_option = root.phase_option_var.get()#
        self.phase_shifts = PHASE_SHIFTS_OPT[root.phase_shifts_var.get()]
        
    def align_inputs(self, audio_inputs, audio_file_base, audio_file_2_base, command_Text, set_progress_bar):
        audio_file_base = f"{self.is_testing_audio}{audio_file_base}"
        audio_file_2_base = f"{self.is_testing_audio}{audio_file_2_base}"
        
        aligned_path = os.path.join('{}'.format(self.main_export_path),'{}_(Aligned).wav'.format(audio_file_2_base))
        inverted_path = os.path.join('{}'.format(self.main_export_path),'{}_(Inverted).wav'.format(audio_file_base))

        spec_utils.align_audio(audio_inputs[0], 
                               audio_inputs[1], 
                               aligned_path, 
                               inverted_path, 
                               self.wav_type_set, 
                               self.is_save_align, 
                               command_Text, 
                               self.save_format,
                               align_window=self.align_window,
                               align_intro_val=self.align_intro_val,
                               db_analysis=self.db_analysis_val,
                               set_progress_bar=set_progress_bar, 
                               phase_option=self.phase_option,
                               phase_shifts=self.phase_shifts,
                               is_match_silence=self.is_match_silence,
                               is_spec_match=self.is_spec_match)
        
    def match_inputs(self, audio_inputs, audio_file_base, command_Text):
        
        target = audio_inputs[0]
        reference = audio_inputs[1]
        
        command_Text(f"Processing... ")
        
        save_path = os.path.join('{}'.format(self.main_export_path),'{}_(Matched).wav'.format(f"{self.is_testing_audio}{audio_file_base}"))
        
        match.process(
            target=target,
            reference=reference,
            results=[match.save_audiofile(save_path, wav_set=self.wav_type_set),
            ],
        )
        
        self.save_format(save_path)
        
    def combine_audio(self, audio_inputs, audio_file_base):
        spec_utils.combine_audio(audio_inputs, 
                                 os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}"), 
                                 self.wav_type_set,
                                 save_format=self.save_format)
        
    def pitch_or_time_shift(self, audio_file, audio_file_base):
        is_time_correction = True
        rate = float(root.time_stretch_rate_var.get()) if self.audio_tool == TIME_STRETCH else float(root.pitch_rate_var.get())
        is_pitch = False if self.audio_tool == TIME_STRETCH else True
        if is_pitch:
            is_time_correction = True if root.is_time_correction_var.get() else False
        file_text = TIME_TEXT if self.audio_tool == TIME_STRETCH else PITCH_TEXT
        save_path = os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}{file_text}.wav")
        spec_utils.augment_audio(save_path, audio_file, rate, self.is_normalization, self.wav_type_set, self.save_format, is_pitch=is_pitch, is_time_correction=is_time_correction)
   
class ToolTip(object):

    def __init__(self, widget):
        self.widget = widget
        self.tooltip = None

    def showtip(self, text, is_message_box=False, is_success_message=None):#
        self.hidetip()
        def create_label_config():
            
            font_size = FONT_SIZE_3 if is_message_box else FONT_SIZE_2
            
            """Helper function to generate label configurations."""
            common_config = {
                "text": text,
                "relief": tk.SOLID,
                "borderwidth": 1,
                "font": (MAIN_FONT_NAME, f"{font_size}", "normal")
            }
            if is_message_box:
                background_color = "#03692d" if is_success_message else "#8B0000"
                return {**common_config, "background": background_color, "foreground": "#ffffff"}
            else:
                return {**common_config, "background": "#1C1C1C", "foreground": "#ffffff", 
                        "highlightcolor": "#898b8e", "justify": tk.LEFT}

        if is_message_box:
            temp_tooltip = tk.Toplevel(self.widget)
            temp_tooltip.wm_overrideredirect(True)
            temp_tooltip.withdraw()
            label = tk.Label(temp_tooltip, **create_label_config())
            label.pack()
            temp_tooltip.update() if is_windows else temp_tooltip.update_idletasks()

            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - (temp_tooltip.winfo_reqwidth() // 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height()

            temp_tooltip.destroy()
        else:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 25

        # Create the actual tooltip
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)  
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label_config = create_label_config()
        if not is_message_box:
            label_config['padx'] = 10  # horizontal padding
            label_config['pady'] = 10  # vertical padding
            label_config["wraplength"] = 750
        label = tk.Label(self.tooltip, **label_config)

        label.pack()

        if is_message_box:
            self.tooltip.after(3000 if type(is_success_message) is bool else 2000, self.hidetip)

    def hidetip(self):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class ListboxBatchFrame(tk.Frame):
    def __init__(self, master=None, name="Listbox", command=None, image_sel=None, img_mapper=None):
        super().__init__(master)
        self.master = master

        self.path_list = []  # A list to keep track of the paths
        self.basename_to_path = {}  # A dict to map basenames to paths

        self.label = tk.Label(self, text=name, font=(MAIN_FONT_NAME, f"{FONT_SIZE_5}"), foreground=FG_COLOR)
        self.label.pack(pady=(10, 8))  # add padding between label and listbox

        self.input_button = ttk.Button(self, text=SELECT_INPUTS, command=self.select_input)  # create button for selecting files
        self.input_button.pack(pady=(0, 10))  # add padding between button and next widget

        self.listbox = tk.Listbox(self, activestyle='dotbox', font=(MAIN_FONT_NAME, f"{FONT_SIZE_4}"), foreground='#cdd3ce', background='#101414', exportselection=0, width=70, height=15)
        self.listbox.pack(fill="both", expand=True)

        self.button_frame = tk.Frame(self)
        self.button_frame.pack()

        self.up_button = ttk.Button(self.button_frame, image=img_mapper["up"], command=self.move_up)
        self.up_button.grid(row=0, column=0)

        self.down_button = ttk.Button(self.button_frame, image=img_mapper["down"], command=self.move_down)
        self.down_button.grid(row=0, column=1)
        
        if command and image_sel:
            self.move_button = ttk.Button(self.button_frame, image=image_sel, command=command)
            self.move_button.grid(row=0, column=2)

        self.duplicate_button = ttk.Button(self.button_frame, image=img_mapper["copy"], command=self.duplicate_selected)
        self.duplicate_button.grid(row=0, column=3) 

        self.delete_button = ttk.Button(self.button_frame, image=img_mapper["clear"], command=self.delete_selected)
        self.delete_button.grid(row=0, column=4)

    def delete_selected(self):
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]  # We get the actual basename here, without the index
            path_to_delete = self.basename_to_path[basename]  # store the path to delete
            del self.basename_to_path[basename]  # delete from the dict
            self.path_list.remove(path_to_delete)  # delete from the list
            self.listbox.delete(selected)
            self.update_displayed_index()

    def select_input(self, inputs=None):
        files = inputs if inputs else root.show_file_dialog(dialoge_type=MULTIPLE_FILE)
        for file in files:
            if file not in self.path_list:  # only add file if it's not already in the list
                basename = os.path.basename(file)
                self.listbox.insert(tk.END, basename)  # insert basename to the listbox
                self.path_list.append(file)  # append the file path to the list
                self.basename_to_path[basename] = file  # add to the dict
        self.update_displayed_index(is_acc_dupe=False)

    def duplicate_selected(self):
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]  # We get the actual basename here, without the index
            path_to_duplicate = self.basename_to_path[basename]  # store the path to duplicate
            self.path_list.append(path_to_duplicate)  # add the duplicated path to the list
            self.update_displayed_index()  # redraw listbox with the duplicated item

    def update_displayed_index(self, inputs=None, is_acc_dupe=True):
        self.basename_to_path = {}  # reset the dictionary
        
        if inputs:
            self.path_list = inputs
            
        basename_count = Counter(self.path_list)  # count occurrences of each path

        for i in range(len(self.path_list)):
            basename = os.path.basename(self.path_list[i])

            # If the path is not unique or we are adding a duplicate
            if basename_count[self.path_list[i]] > 1 and is_acc_dupe:
                j = 1
                new_basename = f"{basename} ({j})"
                while new_basename in self.basename_to_path:
                    j += 1
                    new_basename = f"{basename} ({j})"
                basename = new_basename

            self.basename_to_path[basename] = self.path_list[i]  # update the dict with the new order
            self.listbox.delete(i)
            self.listbox.insert(i, f"{i + 1}: {basename}")

    def move_up(self):
        selected = self.listbox.curselection()
        if selected and selected[0] > 0:
            # Swap items in path_list
            self.path_list[selected[0] - 1], self.path_list[selected[0]] = self.path_list[selected[0]], self.path_list[selected[0] - 1]
            # Redraw listbox
            self.update_displayed_index()
            # Reselect item
            self.listbox.select_set(selected[0] - 1)

    def move_down(self):
        selected = self.listbox.curselection()
        if selected and selected[0] < self.listbox.size() - 1:
            # Swap items in path_list
            self.path_list[selected[0] + 1], self.path_list[selected[0]] = self.path_list[selected[0]], self.path_list[selected[0] + 1]
            # Redraw listbox
            self.update_displayed_index()
            # Reselect item
            self.listbox.select_set(selected[0] + 1)
            
    def get_selected_path(self):
        """Returns the path associated with the selected entry."""
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]  # We get the actual basename here, without the index
            path = self.basename_to_path[basename]  # get the path associated with the basename
            return path
        return None
        
class ComboBoxEditableMenu(ttk.Combobox):
    def __init__(self, master=None, pattern=None, default=None, width=None, is_stay_disabled=False, **kw):
        
        if 'values' in kw:
            kw['values'] = tuple(kw['values']) + (OPT_SEPARATOR, USER_INPUT)
        else:
            kw['values'] = (USER_INPUT)
        
        super().__init__(master, **kw)

        self.textvariable = kw.get('textvariable', tk.StringVar())
        self.pattern = pattern
        self.test = 1
        self.tooltip = ToolTip(self)
        self.is_user_input_var = tk.BooleanVar(value=False)
        self.is_stay_disabled = is_stay_disabled
        
        if isinstance(default, (str, int)):
            self.default = default
        else:
            self.default = default[0]
        
        self.menu_combobox_configure()
        self.var_validation(is_start_up=True)

        if width:
            self.configure(width=width)
        
    def menu_combobox_configure(self):
        self.bind('<<ComboboxSelected>>', self.check_input)
        self.bind('<Button-1>', lambda e:self.focus())
        self.bind('<FocusIn>', self.focusin)
        self.bind('<FocusOut>', lambda e: self.var_validation(is_focus_only=True))

        if is_macos:
            self.bind('<Enter>', lambda e:self.button_released())

        if not self.is_stay_disabled:
            self.configure(state=READ_ONLY)
        
    def check_input(self, event=None):
        if self.textvariable.get() == USER_INPUT:
            self.textvariable.set('')
            self.configure(state=tk.NORMAL)
            self.focus()
            self.selection_range(0, 0)
        else:
            self.var_validation()
   
    def var_validation(self, is_focus_only=False, is_start_up=False):
        if is_focus_only and not self.is_stay_disabled:
            self.configure(state=READ_ONLY)

        if re.fullmatch(self.pattern, self.textvariable.get()) is None:
            if not is_start_up and not self.textvariable.get() in (OPT_SEPARATOR, USER_INPUT):
                self.tooltip.showtip(INVALID_INPUT_E, True)
    
            self.textvariable.set(self.default)
            
    def button_released(self, e=None):
        self.event_generate('<Button-3>')
        self.event_generate('<ButtonRelease-3>')

    def focusin(self, e):
        self.selection_clear()
        if is_macos:
            self.event_generate('<Leave>')

class ComboBoxMenu(ttk.Combobox):
    def __init__(self, master=None, dropdown_name=None, offset=185, is_download_menu=False, command=None, width=None, **kw):
        super().__init__(master, **kw)
        
        # Configure the combobox using the menu_combobox_configure method
        self.menu_combobox_configure(is_download_menu, width=width)

        # Check if both dropdown_name and 'values' are provided to update dropdown size
        if dropdown_name and 'values' in kw:
            self.update_dropdown_size(kw['values'], dropdown_name, offset)
            
        if command:
            self.command(command)

    def menu_combobox_configure(self, is_download_menu=False, command=None, width=None):
        self.bind('<FocusIn>', self.focusin)
        self.bind('<MouseWheel>', lambda e:"break")
        
        if is_macos:
            self.bind('<Enter>', lambda e:self.button_released())
        
        if not is_download_menu:
            self.configure(state=READ_ONLY)
            
        if command:
            self.command(command)
            
        if width:
            self.configure(width=width)

    def button_released(self, e=None):
        self.event_generate('<Button-3>')
        self.event_generate('<ButtonRelease-3>')

    def command(self, command):
        if not self.bind('<<ComboboxSelected>>'):
            self.bind('<<ComboboxSelected>>', command)

    def focusin(self, e):
        self.selection_clear()
        if is_macos:
            self.event_generate('<Leave>')

    def update_dropdown_size(self, option_list, dropdown_name, offset=185, command=None):
        dropdown_style = f"{dropdown_name}.TCombobox"
        if option_list:
            max_string = max(option_list, key=len)
            font = Font(font=self.cget('font'))
            width_in_pixels = font.measure(max_string) - offset
            width_in_pixels = 0 if width_in_pixels < 0 else width_in_pixels
        else:
            width_in_pixels = 0
        
        style = ttk.Style(self)
        style.configure(dropdown_style, padding=(0, 0, 0, 0), postoffset=(0, 0, width_in_pixels, 0))
        self.configure(style=dropdown_style)
                
        if command:
            self.command(command)

class ThreadSafeConsole(tk.Text):
    """
    Text Widget which is thread safe for tkinter
    """
    
    def __init__(self, master, **options):
        tk.Text.__init__(self, master, **options)
        self.queue = queue.Queue()
        self.update_me()

    def write(self, line):
        self.queue.put(line)

    def clear(self):
        self.queue.put(None)

    def update_me(self):
        self.configure(state=tk.NORMAL)
        try:
            while 1:
                line = self.queue.get_nowait()
                if line is None:
                    self.delete(1.0, tk.END)
                else:
                    self.insert(tk.END, str(line))
                self.see(tk.END)
                self.update_idletasks()
        except queue.Empty:
            pass
        self.configure(state=tk.DISABLED)
        self.after(100, self.update_me)
        
    def copy_text(self):
        hightlighted_text = self.selection_get()
        self.clipboard_clear()
        self.clipboard_append(hightlighted_text)
        
    def select_all_text(self):
        self.tag_add('sel', '1.0', 'end')

class MainWindow(TkinterDnD.Tk if is_dnd_compatible else tk.Tk):
    # --Constants--
    # Layout

    IMAGE_HEIGHT = IMAGE_HEIGHT
    FILEPATHS_HEIGHT = FILEPATHS_HEIGHT
    OPTIONS_HEIGHT = OPTIONS_HEIGHT
    CONVERSIONBUTTON_HEIGHT = CONVERSIONBUTTON_HEIGHT
    COMMAND_HEIGHT = COMMAND_HEIGHT
    PROGRESS_HEIGHT = PROGRESS_HEIGHT
    PADDING = PADDING
    WIDTH = WIDTH
    COL1_ROWS = 11
    COL2_ROWS = 11
    
    def __init__(self):
        #Run the __init__ method on the tk.Tk class
        super().__init__()
        
        self.set_app_font()

        style = ttk.Style(self)
        style.map('TCombobox', selectbackground=[('focus', '#0c0c0c')], selectforeground=[('focus', 'white')])
        style.configure('TCombobox', selectbackground='#0c0c0c')
        #style.configure('TCheckbutton', indicatorsize=30)
        
        # Calculate window height
        height = self.IMAGE_HEIGHT + self.FILEPATHS_HEIGHT + self.OPTIONS_HEIGHT
        height += self.CONVERSIONBUTTON_HEIGHT + self.COMMAND_HEIGHT + self.PROGRESS_HEIGHT
        height += self.PADDING * 5  # Padding
        width = self.WIDTH
        self.main_window_width = width
        self.main_window_height = height

        # --Window Settings--
        self.withdraw()
        self.title('Ultimate Vocal Remover')
        # Set Geometry and Center Window
        self.geometry('{width}x{height}+{xpad}+{ypad}'.format(
            width=self.main_window_width,
            height=height,
            xpad=int(self.winfo_screenwidth()/2 - width/2),
            ypad=int(self.winfo_screenheight()/2 - height/2 - 30)))
 
        self.iconbitmap(ICON_IMG_PATH) if is_windows else self.tk.call('wm', 'iconphoto', self._w, tk.PhotoImage(file=MAIN_ICON_IMG_PATH))
        self.protocol("WM_DELETE_WINDOW", self.save_values)
        self.resizable(False, False)
        
        self.msg_queue = queue.Queue()
        # Create a custom style that inherits from the original Combobox style.
        
        if not is_windows:
            self.update()

        #Load Images
        img = ImagePath(BASE_PATH)
        self.logo_img = img.open_image(path=img.banner_path, size=(width, height))
        self.efile_img = img.efile_img
        self.stop_img = img.stop_img
        self.help_img = img.help_img
        self.download_img = img.download_img
        self.donate_img = img.donate_img
        self.key_img = img.key_img
        self.credits_img = img.credits_img
        
        self.right_img = img.right_img
        self.left_img = img.left_img
        self.img_mapper = {
            "down":img.down_img,
            "up":img.up_img,
            "copy":img.copy_img,
            "clear":img.clear_img
        }

        #Placeholders
        self.error_log_var = tk.StringVar(value='')
        self.vr_secondary_model_names = []
        self.mdx_secondary_model_names = []
        self.demucs_secondary_model_names = []
        self.vr_primary_model_names = []
        self.mdx_primary_model_names = []
        self.demucs_primary_model_names = []
        
        self.vr_cache_source_mapper = {}
        self.mdx_cache_source_mapper = {}
        self.demucs_cache_source_mapper = {}
        
        # -Tkinter Value Holders-
        
        try:
            self.load_saved_vars(data)
        except Exception as e:
            self.error_log_var.set(error_text('Loading Saved Variables', e))
            self.load_saved_vars(DEFAULT_DATA)
            
        self.cached_sources_clear()
        
        self.method_mapper = {
            VR_ARCH_PM: self.vr_model_var,
            MDX_ARCH_TYPE: self.mdx_net_model_var,
            DEMUCS_ARCH_TYPE: self.demucs_model_var}

        self.vr_secondary_model_vars = {'voc_inst_secondary_model': self.vr_voc_inst_secondary_model_var,
                                        'other_secondary_model': self.vr_other_secondary_model_var,
                                        'bass_secondary_model': self.vr_bass_secondary_model_var,
                                        'drums_secondary_model': self.vr_drums_secondary_model_var,
                                        'is_secondary_model_activate': self.vr_is_secondary_model_activate_var,
                                        'voc_inst_secondary_model_scale': self.vr_voc_inst_secondary_model_scale_var,
                                        'other_secondary_model_scale': self.vr_other_secondary_model_scale_var,
                                        'bass_secondary_model_scale': self.vr_bass_secondary_model_scale_var,
                                        'drums_secondary_model_scale': self.vr_drums_secondary_model_scale_var}
        
        self.demucs_secondary_model_vars = {'voc_inst_secondary_model': self.demucs_voc_inst_secondary_model_var,
                                        'other_secondary_model': self.demucs_other_secondary_model_var,
                                        'bass_secondary_model': self.demucs_bass_secondary_model_var,
                                        'drums_secondary_model': self.demucs_drums_secondary_model_var,
                                        'is_secondary_model_activate': self.demucs_is_secondary_model_activate_var,
                                        'voc_inst_secondary_model_scale': self.demucs_voc_inst_secondary_model_scale_var,
                                        'other_secondary_model_scale': self.demucs_other_secondary_model_scale_var,
                                        'bass_secondary_model_scale': self.demucs_bass_secondary_model_scale_var,
                                        'drums_secondary_model_scale': self.demucs_drums_secondary_model_scale_var}
        
        self.mdx_secondary_model_vars = {'voc_inst_secondary_model': self.mdx_voc_inst_secondary_model_var,
                                        'other_secondary_model': self.mdx_other_secondary_model_var,
                                        'bass_secondary_model': self.mdx_bass_secondary_model_var,
                                        'drums_secondary_model': self.mdx_drums_secondary_model_var,
                                        'is_secondary_model_activate': self.mdx_is_secondary_model_activate_var,
                                        'voc_inst_secondary_model_scale': self.mdx_voc_inst_secondary_model_scale_var,
                                        'other_secondary_model_scale': self.mdx_other_secondary_model_scale_var,
                                        'bass_secondary_model_scale': self.mdx_bass_secondary_model_scale_var,
                                        'drums_secondary_model_scale': self.mdx_drums_secondary_model_scale_var}

        #Main Application Vars
        self.progress_bar_main_var = tk.IntVar(value=0)
        self.inputPathsEntry_var = tk.StringVar(value='')
        self.conversion_Button_Text_var = tk.StringVar(value=START_PROCESSING)
        self.chosen_ensemble_var = tk.StringVar(value=CHOOSE_ENSEMBLE_OPTION)
        self.ensemble_main_stem_var = tk.StringVar(value=CHOOSE_STEM_PAIR)
        self.ensemble_type_var = tk.StringVar(value=MAX_MIN)
        self.save_current_settings_var = tk.StringVar(value=SELECT_SAVED_SET)
        self.demucs_stems_var = tk.StringVar(value=ALL_STEMS)
        self.mdxnet_stems_var = tk.StringVar(value=ALL_STEMS)
        self.is_primary_stem_only_Text_var = tk.StringVar(value='')
        self.is_secondary_stem_only_Text_var = tk.StringVar(value='')
        self.is_primary_stem_only_Demucs_Text_var = tk.StringVar(value='')
        self.is_secondary_stem_only_Demucs_Text_var = tk.StringVar(value='')
        self.scaling_var = tk.DoubleVar(value=1.0)
        self.active_processing_thread = None
        self.verification_thread = None
        self.is_menu_settings_open = False
        self.is_root_defined_var = tk.BooleanVar(value=False)
        self.is_check_splash = False
        
        self.is_open_menu_advanced_vr_options = tk.BooleanVar(value=False)
        self.is_open_menu_advanced_demucs_options = tk.BooleanVar(value=False)
        self.is_open_menu_advanced_mdx_options = tk.BooleanVar(value=False)
        self.is_open_menu_advanced_ensemble_options = tk.BooleanVar(value=False)
        self.is_open_menu_view_inputs = tk.BooleanVar(value=False)
        self.is_open_menu_help = tk.BooleanVar(value=False)
        self.is_open_menu_error_log = tk.BooleanVar(value=False)
        self.is_open_menu_advanced_align_options = tk.BooleanVar(value=False)

        self.menu_advanced_vr_options_close_window = None
        self.menu_advanced_demucs_options_close_window = None
        self.menu_advanced_mdx_options_close_window = None
        self.menu_advanced_ensemble_options_close_window = None
        self.menu_help_close_window = None
        self.menu_error_log_close_window = None
        self.menu_view_inputs_close_window = None
        self.menu_advanced_align_options_close_window = None

        self.mdx_model_params = None
        self.vr_model_params = None
        self.current_text_box = None
        self.wav_type_set = None
        self.is_online_model_menu = None
        self.progress_bar_var = tk.IntVar(value=0)
        self.is_confirm_error_var = tk.BooleanVar(value=False)
        self.clear_cache_torch = False
        self.vr_hash_MAPPER = load_model_hash_data(VR_HASH_JSON)
        self.mdx_hash_MAPPER = load_model_hash_data(MDX_HASH_JSON)
        self.mdx_name_select_MAPPER = load_model_hash_data(MDX_MODEL_NAME_SELECT)
        self.demucs_name_select_MAPPER = load_model_hash_data(DEMUCS_MODEL_NAME_SELECT)
        self.is_gpu_available = is_gpu_available
        self.is_process_stopped = False
        self.inputs_from_dir = []
        self.iteration = 0
        self.true_model_count = 0
        self.vr_primary_source = None
        self.vr_secondary_source = None
        self.mdx_primary_source = None
        self.mdx_secondary_source = None
        self.demucs_primary_source = None
        self.demucs_secondary_source = None
        self.toplevels = []

        #Download Center Vars
        self.online_data = {}
        self.bulletin_data = INFO_UNAVAILABLE_TEXT
        self.is_online = False
        self.lastest_version = ''
        self.model_download_demucs_var = tk.StringVar(value='')
        self.model_download_mdx_var = tk.StringVar(value='')
        self.model_download_vr_var = tk.StringVar(value='')
        self.selected_download_var = tk.StringVar(value=NO_MODEL)
        self.select_download_var = tk.StringVar(value='')
        self.download_progress_info_var = tk.StringVar(value='')
        self.download_progress_percent_var = tk.StringVar(value='')
        self.download_progress_bar_var = tk.IntVar(value=0)
        self.download_stop_var = tk.StringVar(value='') 
        self.app_update_status_Text_var = tk.StringVar(value=LOADING_VERSION_INFO_TEXT)
        self.app_update_button_Text_var = tk.StringVar(value=CHECK_FOR_UPDATES_TEXT)
        
        self.user_code_validation_var = tk.StringVar(value='')
        self.download_link_path_var = tk.StringVar(value='') 
        self.download_save_path_var = tk.StringVar(value='')
        self.download_update_link_var = tk.StringVar(value='') 
        self.download_update_path_var = tk.StringVar(value='') 
        self.download_demucs_models_list = []
        self.download_demucs_newer_models = []
        self.refresh_list_Button = None
        self.stop_download_Button_DISABLE = None
        self.enable_tabs = None
        self.is_download_thread_active = False
        self.is_process_thread_active = False
        self.is_active_processing_thread = False
        self.active_download_thread = None
        self.pre_proc_model_toggle = None
        self.change_state_lambda = None
        self.file_one_sub_var = tk.StringVar(value=FILE_ONE_MAIN_LABEL) 
        self.file_two_sub_var = tk.StringVar(value=FILE_TWO_MAIN_LABEL) 
        self.cuda_device_list = GPU_DEVICE_NUM_OPTS
        self.opencl_list = GPU_DEVICE_NUM_OPTS
        
        #Model Update
        self.last_found_ensembles = ENSEMBLE_OPTIONS
        self.last_found_settings = ENSEMBLE_OPTIONS
        self.last_found_models = ()
        self.model_data_table = ()
        self.ensemble_model_list = ()
        self.default_change_model_list = ()
                
        # --Widgets--
        self.fill_main_frame()
        self.bind_widgets()
        
        # --Update Widgets--
        self.update_available_models()
        self.update_main_widget_states()
        self.update_loop()
        self.update_button_states()
        self.download_validate_code()
        self.delete_temps(is_start_up=True)
        self.ensemble_listbox_Option.configure(state=tk.DISABLED)
        self.command_Text.write(f'Ultimate Vocal Remover {VERSION} [{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]')
        self.update_checkbox_text = lambda:self.selection_action_process_method(self.chosen_process_method_var.get())
        self.check_dual_paths()
        if not is_windows:
            self.update_idletasks()
        self.fill_gpu_list()
        self.online_data_refresh(user_refresh=False, is_start_up=True)
        
    # Menu Functions
    def main_window_LABEL_SET(self, master, text):return ttk.Label(master=master, text=text, background=BG_COLOR, font=self.font_set, foreground=FG_COLOR, anchor=tk.CENTER)
    def main_window_LABEL_SUB_SET(self, master, text_var):return ttk.Label(master=master, textvariable=text_var, background=BG_COLOR, font=self.font_set, foreground=FG_COLOR, anchor=tk.CENTER)
    def menu_title_LABEL_SET(self, frame, text, width=35):return ttk.Label(master=frame, text=text, font=(SEC_FONT_NAME, f"{FONT_SIZE_5}", "underline"), justify="center", foreground="#13849f", width=width, anchor=tk.CENTER)
    def menu_sub_LABEL_SET(self, frame, text, font_size=FONT_SIZE_2):return ttk.Label(master=frame, text=text, font=(MAIN_FONT_NAME, f"{font_size}"), foreground=FG_COLOR, anchor=tk.CENTER)
    def menu_FRAME_SET(self, frame, thickness=20):return tk.Frame(frame, highlightbackground=BG_COLOR, highlightcolor=BG_COLOR, highlightthicknes=thickness)
    def check_is_menu_settings_open(self):self.menu_settings() if not self.is_menu_settings_open else None
    def spacer_label(self, frame): return tk.Label(frame, text='', font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground='#868687', justify="left").grid()

    #Ensemble Listbox Functions
    def ensemble_listbox_get_all_selected_models(self):return [self.ensemble_listbox_Option.get(i) for i in self.ensemble_listbox_Option.curselection()]
    def ensemble_listbox_select_from_indexs(self, indexes):return [self.ensemble_listbox_Option.selection_set(i) for i in indexes]
    def ensemble_listbox_clear_and_insert_new(self, model_ensemble_updated):return (self.ensemble_listbox_Option.delete(0, 'end'), [self.ensemble_listbox_Option.insert(tk.END, models) for models in model_ensemble_updated])
    def ensemble_listbox_get_indexes_for_files(self, updated, selected):return [updated.index(model) for model in selected if model in updated]
    
    def set_app_font(self):
        chosen_font_name, chosen_font_file = font_checker(OWN_FONT_PATH)

        if chosen_font_name:
            gui_data.sv_ttk.set_theme("dark", chosen_font_name, 10)
            if chosen_font_file:
                pyglet_font.add_file(chosen_font_file)
            self.font_set = Font(family=chosen_font_name, size=FONT_SIZE_F2)
            self.font_entry = Font(family=chosen_font_name, size=FONT_SIZE_F2)
        else:
            pyglet_font.add_file(FONT_MAPPER[MAIN_FONT_NAME])
            pyglet_font.add_file(FONT_MAPPER[SEC_FONT_NAME])
            gui_data.sv_ttk.set_theme("dark", MAIN_FONT_NAME, 10)
            self.font_set = Font(family=SEC_FONT_NAME, size=FONT_SIZE_F2)
            self.font_entry = Font(family=MAIN_FONT_NAME, size=FONT_SIZE_F2)
    
    def process_iteration(self):
        self.iteration = self.iteration + 1

    def processing_controller(self):
        return processing_service_module.ProcessingController(self)

    def set_processing_button_enabled(self, is_enabled: bool):
        self.conversion_Button.configure(state="normal" if is_enabled else "disabled")

    def confirm_stop_process_dialog(self) -> bool:
        return messagebox.askyesno(
            parent=self,
            title=STOP_PROCESS_CONFIRM[0],
            message=STOP_PROCESS_CONFIRM[1],
        )

    def confirm_processing_error_dialog(self, message: str) -> bool:
        return messagebox.askyesno(
            parent=self,
            title=ERROR_OCCURED[0],
            message=message,
        )

    def file_inputs(self):
        return ui_file_inputs_module.MainWindowFileInputs(self)

    def input_menus(self):
        return input_menus_module.InputMenus(self)

    def advanced_menus(self):
        return advanced_menus_module.AdvancedMenus(self)

    def download_menus(self):
        return download_menus_module.DownloadMenus(self)

    def menu_helpers(self):
        return common_menus_module.MenuHelpers(self)

    def ui_actions(self):
        return ui_actions_module.MainWindowActions(self)
    
    def assemble_model_data(self, model=None, arch_type=ENSEMBLE_MODE, is_dry_check=False, is_change_def=False, is_get_hash_dir_only=False):

        if arch_type == ENSEMBLE_STEM_CHECK:
            
            model_data = self.model_data_table
            missing_models = [model.model_status for model in model_data if not model.model_status]
            
            if missing_models or not model_data:
                model_data: List[ModelData] = [ModelData(model_name, is_dry_check=is_dry_check) for model_name in self.ensemble_model_list]
                self.model_data_table = model_data

        if arch_type == KARAOKEE_CHECK:
            model_list = []
            model_data: List[ModelData] = [ModelData(model_name, is_dry_check=is_dry_check) for model_name in self.default_change_model_list]
            for model in model_data:
                if model.model_status and model.is_karaoke or model.is_bv_model:
                    model_list.append(model.model_and_process_tag)
            
            return model_list

        if arch_type == ENSEMBLE_MODE:
            model_data: List[ModelData] = [ModelData(model_name) for model_name in self.ensemble_listbox_get_all_selected_models()]
        if arch_type == ENSEMBLE_CHECK:
            model_data: List[ModelData] = [ModelData(model, is_change_def=is_change_def, is_get_hash_dir_only=is_get_hash_dir_only)]
        if arch_type == VR_ARCH_TYPE or arch_type == VR_ARCH_PM:
            model_data: List[ModelData] = [ModelData(model, VR_ARCH_TYPE)]
        if arch_type == MDX_ARCH_TYPE:
            model_data: List[ModelData] = [ModelData(model, MDX_ARCH_TYPE)]
        if arch_type == DEMUCS_ARCH_TYPE:
            model_data: List[ModelData] = [ModelData(model, DEMUCS_ARCH_TYPE)]#

        return model_data
        
    def clear_cache(self, network):
        
        if network == VR_ARCH_TYPE:
            dir = VR_HASH_DIR
        if network == MDX_ARCH_TYPE:
            dir = MDX_HASH_DIR     
        
        for filename in os.listdir(dir):
            filepath = os.path.join(dir, filename)
            if filename not in ['model_data.json', 'model_name_mapper.json', 'mdx_c_configs'] and not os.path.isdir(filepath):
                os.remove(filepath)
        
        self.vr_model_var.set(CHOOSE_MODEL)
        self.mdx_net_model_var.set(CHOOSE_MODEL)
        self.model_data_table.clear()
        self.chosen_ensemble_var.set(CHOOSE_ENSEMBLE_OPTION)
        self.ensemble_main_stem_var.set(CHOOSE_STEM_PAIR)
        self.ensemble_listbox_Option.configure(state=tk.DISABLED)
        self.update_checkbox_text()
    
    def thread_check(self, thread_to_check):
        '''Checks if thread is alive'''
        
        is_running = False
        
        if type(thread_to_check) is KThread:
            if thread_to_check.is_alive():
                is_running = True
                
        return is_running

    # -Widget Methods--

    def fill_main_frame(self):
        """Creates root window widgets"""
        
        self.title_Label = tk.Label(master=self, image=self.logo_img, compound=tk.TOP)
        self.title_Label.place(x=-2, y=banner_placement)

        self.fill_filePaths_Frame()
        self.fill_options_Frame()
        
        self.conversion_Button = ttk.Button(master=self, textvariable=self.conversion_Button_Text_var, command=self.process_initialize)
        self.conversion_Button.place(x=X_CONVERSION_BUTTON_1080P, y=BUTTON_Y_1080P, width=WIDTH_CONVERSION_BUTTON_1080P, height=HEIGHT_GENERIC_BUTTON_1080P,
                                    relx=0, rely=0, relwidth=1, relheight=0)
        
        self.conversion_Button_enable = lambda:(self.conversion_Button_Text_var.set(START_PROCESSING), self.conversion_Button.configure(state=tk.NORMAL))
        self.conversion_Button_disable = lambda message:(self.conversion_Button_Text_var.set(message), self.conversion_Button.configure(state=tk.DISABLED))
        
        self.stop_Button = ttk.Button(master=self, image=self.stop_img, command=self.confirm_stop_process)
        self.stop_Button.place(x=X_STOP_BUTTON_1080P, y=BUTTON_Y_1080P, width=HEIGHT_GENERIC_BUTTON_1080P, height=HEIGHT_GENERIC_BUTTON_1080P,
                            relx=1, rely=0, relwidth=0, relheight=0)
        self.help_hints(self.stop_Button, text=STOP_HELP)
        
        self.settings_Button = ttk.Button(master=self, image=self.help_img, command=self.check_is_menu_settings_open)
        self.settings_Button.place(x=X_SETTINGS_BUTTON_1080P, y=BUTTON_Y_1080P, width=HEIGHT_GENERIC_BUTTON_1080P, height=HEIGHT_GENERIC_BUTTON_1080P,
                                relx=1, rely=0, relwidth=0, relheight=0)
        self.help_hints(self.settings_Button, text=SETTINGS_HELP)
    
        self.progressbar = ttk.Progressbar(master=self, variable=self.progress_bar_main_var)
        self.progressbar.place(x=X_PROGRESSBAR_1080P, y=Y_OFFSET_PROGRESS_BAR_1080P, width=WIDTH_PROGRESSBAR_1080P, height=HEIGHT_PROGRESSBAR_1080P,
                            relx=0, rely=0, relwidth=1, relheight=0)

         # Select Music Files Option
        self.console_Frame = tk.Frame(master=self, highlightbackground='#101012', highlightcolor='#101012', highlightthicknes=2)
        self.console_Frame.place(x=15, y=self.IMAGE_HEIGHT + self.FILEPATHS_HEIGHT + self.OPTIONS_HEIGHT + self.CONVERSIONBUTTON_HEIGHT + self.PADDING + 5 *3, width=-30, height=self.COMMAND_HEIGHT+7,
                                relx=0, rely=0, relwidth=1, relheight=0)


        self.command_Text = ThreadSafeConsole(master=self.console_Frame, background='#0c0c0d',fg='#898b8e', highlightcolor="#0c0c0d",  font=(MAIN_FONT_NAME, FONT_SIZE_4), borderwidth=0)
        self.command_Text.pack(fill=tk.BOTH, expand=1)
        self.command_Text.bind(right_click_button, lambda e:self.right_click_console(e))
            
    def fill_filePaths_Frame(self):
        """Fill Frame with neccessary widgets"""

        # Select Music Files Option
        self.filePaths_Frame = ttk.Frame(master=self)
        self.filePaths_Frame.place(x=FILEPATHS_FRAME_X, y=FILEPATHS_FRAME_Y, width=FILEPATHS_FRAME_WIDTH, height=self.FILEPATHS_HEIGHT, relx=0, rely=0, relwidth=1, relheight=0)

        self.filePaths_musicFile_Button = ttk.Button(master=self.filePaths_Frame, text=SELECT_INPUT_TEXT, command=self.input_select_filedialog)
        self.filePaths_musicFile_Button.place(x=MUSICFILE_BUTTON_X, y=MUSICFILE_BUTTON_Y, width=MUSICFILE_BUTTON_WIDTH, height=MUSICFILE_BUTTON_HEIGHT, relx=0, rely=0, relwidth=0.3, relheight=0.5)
        self.filePaths_musicFile_Entry = ttk.Entry(master=self.filePaths_Frame, textvariable=self.inputPathsEntry_var, font=self.font_entry, state=tk.DISABLED)
        self.filePaths_musicFile_Entry.place(x=MUSICFILE_ENTRY_X, y=MUSICFILE_BUTTON_Y, width=MUSICFILE_ENTRY_WIDTH, height=MUSICFILE_ENTRY_HEIGHT, relx=0.3, rely=0, relwidth=0.7, relheight=0.5)                                   
        self.filePaths_musicFile_Open = ttk.Button(master=self.filePaths_Frame, image=self.efile_img, command=lambda:OPEN_FILE_func(os.path.dirname(self.inputPaths[0])) if self.inputPaths and os.path.isdir(os.path.dirname(self.inputPaths[0])) else self.error_dialoge(INVALID_INPUT))
        self.filePaths_musicFile_Open.place(x=OPEN_BUTTON_X, y=MUSICFILE_BUTTON_Y, width=OPEN_BUTTON_WIDTH, height=MUSICFILE_ENTRY_HEIGHT, relx=0.3, rely=0, relwidth=0.7, relheight=0.5)   

        # Add any additional configurations or method calls here
        self.filePaths_musicFile_Entry.configure(cursor="hand2")
        self.help_hints(self.filePaths_musicFile_Button, text=INPUT_FOLDER_ENTRY_HELP) 
        self.help_hints(self.filePaths_musicFile_Entry, text=INPUT_FOLDER_ENTRY_HELP_2)
        self.help_hints(self.filePaths_musicFile_Open, text=INPUT_FOLDER_BUTTON_HELP)     

        # Save To Option
        self.filePaths_saveTo_Button = ttk.Button(master=self.filePaths_Frame, text=SELECT_OUTPUT_TEXT, command=self.export_select_filedialog)
        self.filePaths_saveTo_Button.place(x=SAVETO_BUTTON_X, y=SAVETO_BUTTON_Y, width=SAVETO_BUTTON_WIDTH, height=SAVETO_BUTTON_HEIGHT, relx=0, rely=0.5, relwidth=0.3, relheight=0.5)
        self.filePaths_saveTo_Entry = ttk.Entry(master=self.filePaths_Frame, textvariable=self.export_path_var, font=self.font_entry, state=tk.DISABLED)
        self.filePaths_saveTo_Entry.place(x=SAVETO_ENTRY_X, y=SAVETO_BUTTON_Y, width=SAVETO_ENTRY_WIDTH, height=SAVETO_ENTRY_HEIGHT, relx=0.3, rely=0.5, relwidth=0.7, relheight=0.5)
        self.filePaths_saveTo_Open = ttk.Button(master=self.filePaths_Frame, image=self.efile_img, command=lambda:OPEN_FILE_func(Path(self.export_path_var.get())) if os.path.isdir(self.export_path_var.get()) else self.error_dialoge(INVALID_EXPORT))
        self.filePaths_saveTo_Open.place(x=OPEN_BUTTON_X, y=SAVETO_BUTTON_Y, width=OPEN_BUTTON_WIDTH, height=SAVETO_ENTRY_HEIGHT, relx=0.3, rely=0.5, relwidth=0.7, relheight=0.5)
        self.help_hints(self.filePaths_saveTo_Button, text=OUTPUT_FOLDER_ENTRY_HELP) 
        self.help_hints(self.filePaths_saveTo_Open, text=OUTPUT_FOLDER_BUTTON_HELP)     

    def fill_options_Frame(self):
        """Fill Frame with neccessary widgets"""
        
        self.options_Frame = ttk.Frame(master=self)
        self.options_Frame.place(x=OPTIONS_FRAME_X, y=OPTIONS_FRAME_Y, width=OPTIONS_FRAME_WIDTH, height=self.OPTIONS_HEIGHT, relx=0, rely=0, relwidth=1, relheight=0)

        # -Create Widgets-

        ## Save Format
        self.wav_button = ttk.Radiobutton(master=self.options_Frame, text=WAV, variable=self.save_format_var, value=WAV)
        self.wav_button.place(x=RADIOBUTTON_X_WAV, y=RADIOBUTTON_Y, width=RADIOBUTTON_WIDTH, height=RADIOBUTTON_HEIGHT, relx=0, rely=0/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.wav_button, text=f'{FORMAT_SETTING_HELP}{WAV}')

        self.flac_button = ttk.Radiobutton(master=self.options_Frame, text=FLAC, variable=self.save_format_var, value=FLAC)
        self.flac_button.place(x=RADIOBUTTON_X_FLAC, y=RADIOBUTTON_Y, width=RADIOBUTTON_WIDTH, height=RADIOBUTTON_HEIGHT, relx=1/3, rely=0/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.flac_button, text=f'{FORMAT_SETTING_HELP}{FLAC}')

        self.mp3_button = ttk.Radiobutton(master=self.options_Frame, text=MP3, variable=self.save_format_var, value=MP3)
        self.mp3_button.place(x=RADIOBUTTON_X_MP3, y=RADIOBUTTON_Y, width=RADIOBUTTON_WIDTH, height=RADIOBUTTON_HEIGHT, relx=2/3, rely=0/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.mp3_button, text=f'{FORMAT_SETTING_HELP}{MP3}')

        # Choose Conversion Method
        self.chosen_process_method_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_PROC_METHOD_MAIN_LABEL)
        self.chosen_process_method_Label.place(x=0, y=MAIN_ROW_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.chosen_process_method_Option = ComboBoxMenu(self.options_Frame, textvariable=self.chosen_process_method_var, values=PROCESS_METHODS, command=lambda e: self.selection_action_process_method(self.chosen_process_method_var.get(), from_widget=True, is_from_conv_menu=True))
        self.chosen_process_method_Option.place(x=0, y=MAIN_ROW_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        #self.chosen_process_method_var.trace_add('write', lambda *args: self.update_main_widget_states())
        self.help_hints(self.chosen_process_method_Label, text=CHOSEN_PROCESS_METHOD_HELP)
        
        #  Choose Settings Option
        self.save_current_settings_Label = self.main_window_LABEL_SET(self.options_Frame, SELECT_SAVED_SETTINGS_MAIN_LABEL)
        self.save_current_settings_Label_place = lambda:self.save_current_settings_Label.place(x=MAIN_ROW_2_X[0], y=LOW_MENU_Y[0], width=0, height=LABEL_HEIGHT, relx=2/3, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.save_current_settings_Option = ComboBoxMenu(self.options_Frame, textvariable=self.save_current_settings_var, command=lambda e:self.selection_action_saved_settings(self.save_current_settings_var.get()))
        self.save_current_settings_Option_place = lambda:self.save_current_settings_Option.place(x=MAIN_ROW_2_X[1], y=LOW_MENU_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.save_current_settings_Label, text=SAVE_CURRENT_SETTINGS_HELP)
        
        ### MDX-NET ###

        #  Choose MDX-Net Model
        self.mdx_net_model_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_MDX_MODEL_MAIN_LABEL)
        self.mdx_net_model_Label_place = lambda:self.mdx_net_model_Label.place(x=0, y=LOW_MENU_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.mdx_net_model_Option = ComboBoxMenu(self.options_Frame, textvariable=self.mdx_net_model_var, command=lambda event: self.selection_action(event, self.mdx_net_model_var, is_mdx_net=True))
        self.mdx_net_model_Option_place = lambda:self.mdx_net_model_Option.place(x=0, y=LOW_MENU_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        #self.mdx_net_model_var.trace_add('write', lambda *args: self.update_main_widget_states_mdx())
        self.help_hints(self.mdx_net_model_Label, text=CHOOSE_MODEL_HELP)
        
        # MDX-Overlap
        self.overlap_mdx_Label = self.main_window_LABEL_SET(self.options_Frame, 'OVERLAP')
        self.overlap_mdx_Label_place = lambda:self.overlap_mdx_Label.place(x=MAIN_ROW_2_X[0], y=MAIN_ROW_2_Y[0], width=0, height=LABEL_HEIGHT, relx=2/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.overlap_mdx_Option = ComboBoxEditableMenu(self.options_Frame, values=MDX_OVERLAP, width=MENU_COMBOBOX_WIDTH, textvariable=self.overlap_mdx_var, pattern=REG_OVERLAP, default=MDX_OVERLAP)
        self.overlap_mdx_Option_place = lambda:self.overlap_mdx_Option.place(x=MAIN_ROW_2_X[1], y=MAIN_ROW_2_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        
        # MDX23-Overlap
        self.overlap_mdx23_Option = ComboBoxEditableMenu(self.options_Frame, values=MDX23_OVERLAP, width=MENU_COMBOBOX_WIDTH, textvariable=self.overlap_mdx23_var, pattern=REG_OVERLAP23, default="8")
        self.overlap_mdx23_Option_place = lambda:self.overlap_mdx23_Option.place(x=MAIN_ROW_2_X[1], y=MAIN_ROW_2_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.overlap_mdx_Label, text=MDX_OVERLAP_HELP)
        
        # Choose MDX-Net Stems
        self.mdxnet_stems_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_STEMS_MAIN_LABEL)
        self.mdxnet_stems_Label_place = lambda:self.mdxnet_stems_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        
        self.mdxnet_stems_Option = ComboBoxMenu(self.options_Frame, textvariable=self.mdxnet_stems_var)
        self.mdxnet_stems_Option_place = lambda:self.mdxnet_stems_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.mdxnet_stems_Label, text=DEMUCS_STEMS_HELP)
        
        # MDX-Segment Size
        self.mdx_segment_size_Label = self.main_window_LABEL_SET(self.options_Frame, SEGMENT_MDX_MAIN_LABEL)
        self.mdx_segment_size_Label_place = lambda:self.mdx_segment_size_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.mdx_segment_size_Option = ComboBoxEditableMenu(self.options_Frame, values=MDX_SEGMENTS, width=MENU_COMBOBOX_WIDTH, textvariable=self.mdx_segment_size_var, pattern=REG_MDX_SEG, default="256")#
        self.mdx_segment_size_Option_place = lambda:self.mdx_segment_size_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.mdx_segment_size_Label, text=MDX_SEGMENT_SIZE_HELP)

        ### VR ARCH ###
        
        #  Choose VR Model
        self.vr_model_Label = self.main_window_LABEL_SET(self.options_Frame, SELECT_VR_MODEL_MAIN_LABEL)
        self.vr_model_Label_place = lambda:self.vr_model_Label.place(x=0, y=LOW_MENU_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.vr_model_Option = ComboBoxMenu(self.options_Frame, textvariable=self.vr_model_var, command=lambda event: self.selection_action(event, self.vr_model_var))
        self.vr_model_Option_place = lambda:self.vr_model_Option.place(x=0, y=LOW_MENU_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.vr_model_Label, text=CHOOSE_MODEL_HELP)
        
        # Aggression Setting
        self.aggression_setting_Label = self.main_window_LABEL_SET(self.options_Frame, AGGRESSION_SETTING_MAIN_LABEL)
        self.aggression_setting_Label_place = lambda:self.aggression_setting_Label.place(x=MAIN_ROW_2_X[0], y=MAIN_ROW_2_Y[0], width=0, height=LABEL_HEIGHT, relx=2/3, rely=2/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.aggression_setting_Option = ComboBoxEditableMenu(self.options_Frame, values=VR_AGGRESSION, textvariable=self.aggression_setting_var, pattern=REG_AGGRESSION, default=VR_AGGRESSION[5])#
        self.aggression_setting_Option_place = lambda:self.aggression_setting_Option.place(x=MAIN_ROW_2_X[1], y=MAIN_ROW_2_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=3/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.aggression_setting_Label, text=AGGRESSION_SETTING_HELP)
        
        # Window Size
        self.window_size_Label = self.main_window_LABEL_SET(self.options_Frame, WINDOW_SIZE_MAIN_LABEL)
        self.window_size_Label_place = lambda:self.window_size_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.window_size_Option = ComboBoxEditableMenu(self.options_Frame, values=VR_WINDOW, textvariable=self.window_size_var, pattern=REG_WINDOW, default=VR_WINDOW[1])#
        self.window_size_Option_place = lambda:self.window_size_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.window_size_Label, text=WINDOW_SIZE_HELP)
        
        ### DEMUCS ###
        
        #  Choose Demucs Models
        self.demucs_model_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_DEMUCS_MODEL_MAIN_LABEL)
        self.demucs_model_Label_place = lambda:self.demucs_model_Label.place(x=0, y=LOW_MENU_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.demucs_model_Option = ComboBoxMenu(self.options_Frame, textvariable=self.demucs_model_var, command=lambda event: self.selection_action(event, self.demucs_model_var))
        self.demucs_model_Option_place = lambda:self.demucs_model_Option.place(x=0, y=LOW_MENU_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.demucs_model_Label, text=CHOOSE_MODEL_HELP)

        # Choose Demucs Stems
        self.demucs_stems_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_STEMS_MAIN_LABEL)
        self.demucs_stems_Label_place = lambda:self.demucs_stems_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.demucs_stems_Option = ComboBoxMenu(self.options_Frame, textvariable=self.demucs_stems_var)
        self.demucs_stems_Option_place = lambda:self.demucs_stems_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.demucs_stems_Label, text=DEMUCS_STEMS_HELP)

        # Demucs-Segment
        self.segment_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_SEGMENT_MAIN_LABEL)
        self.segment_Label_place = lambda:self.segment_Label.place(x=MAIN_ROW_2_X[0], y=MAIN_ROW_2_Y[0], width=0, height=LABEL_HEIGHT, relx=2/3, rely=2/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.segment_Option = ComboBoxEditableMenu(self.options_Frame, values=DEMUCS_SEGMENTS, textvariable=self.segment_var, pattern=REG_SEGMENTS, default=DEMUCS_SEGMENTS)#
        self.segment_Option_place = lambda:self.segment_Option.place(x=MAIN_ROW_2_X[1], y=MAIN_ROW_2_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=3/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.segment_Label, text=SEGMENT_HELP)
     
        # Stem A
        self.is_primary_stem_only_Demucs_Option = ttk.Checkbutton(master=self.options_Frame, textvariable=self.is_primary_stem_only_Demucs_Text_var, variable=self.is_primary_stem_only_Demucs_var, command=lambda:self.is_primary_stem_only_Demucs_Option_toggle())
        self.is_primary_stem_only_Demucs_Option_place = lambda:self.is_primary_stem_only_Demucs_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=6/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.is_primary_stem_only_Demucs_Option_toggle = lambda:self.is_secondary_stem_only_Demucs_var.set(False) if self.is_primary_stem_only_Demucs_var.get() else self.is_secondary_stem_only_Demucs_Option.configure(state=tk.NORMAL)
        self.help_hints(self.is_primary_stem_only_Demucs_Option, text=SAVE_STEM_ONLY_HELP)
        
        # Stem B
        self.is_secondary_stem_only_Demucs_Option = ttk.Checkbutton(master=self.options_Frame, textvariable=self.is_secondary_stem_only_Demucs_Text_var, variable=self.is_secondary_stem_only_Demucs_var, command=lambda:self.is_secondary_stem_only_Demucs_Option_toggle())
        self.is_secondary_stem_only_Demucs_Option_place = lambda:self.is_secondary_stem_only_Demucs_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=7/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.is_secondary_stem_only_Demucs_Option_toggle = lambda:self.is_primary_stem_only_Demucs_var.set(False) if self.is_secondary_stem_only_Demucs_var.get() else self.is_primary_stem_only_Demucs_Option.configure(state=tk.NORMAL)
        self.is_stem_only_Demucs_Options_Enable = lambda:(self.is_primary_stem_only_Demucs_Option.configure(state=tk.NORMAL), self.is_secondary_stem_only_Demucs_Option.configure(state=tk.NORMAL))
        self.help_hints(self.is_secondary_stem_only_Demucs_Option, text=SAVE_STEM_ONLY_HELP)

        ### ENSEMBLE MODE ###

        # Ensemble Mode
        self.chosen_ensemble_Label = self.main_window_LABEL_SET(self.options_Frame, ENSEMBLE_OPTIONS_MAIN_LABEL)
        self.chosen_ensemble_Label_place = lambda:self.chosen_ensemble_Label.place(x=0, y=LOW_MENU_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.chosen_ensemble_Option = ComboBoxMenu(self.options_Frame, textvariable=self.chosen_ensemble_var, command=lambda e:self.selection_action_chosen_ensemble(self.chosen_ensemble_var.get()))
        self.chosen_ensemble_Option_place = lambda:self.chosen_ensemble_Option.place(x=0, y=LOW_MENU_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.chosen_ensemble_Label, text=CHOSEN_ENSEMBLE_HELP)
                        
        # Ensemble Main Stems
        self.ensemble_main_stem_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_MAIN_PAIR_MAIN_LABEL)
        self.ensemble_main_stem_Label_place = lambda:self.ensemble_main_stem_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.ensemble_main_stem_Option = ComboBoxMenu(self.options_Frame, textvariable=self.ensemble_main_stem_var, values=ENSEMBLE_MAIN_STEM, command=lambda e: self.selection_action_ensemble_stems(self.ensemble_main_stem_var.get()))
        self.ensemble_main_stem_Option_place = lambda:self.ensemble_main_stem_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.ensemble_main_stem_Label, text=ENSEMBLE_MAIN_STEM_HELP)

        # Ensemble Algorithm
        self.ensemble_type_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_ENSEMBLE_ALGORITHM_MAIN_LABEL)
        self.ensemble_type_Label_place = lambda:self.ensemble_type_Label.place(x=MAIN_ROW_2_X[0], y=MAIN_ROW_2_Y[0], width=0, height=LABEL_HEIGHT, relx=2/3, rely=2/11, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.ensemble_type_Option = ComboBoxMenu(self.options_Frame, textvariable=self.ensemble_type_var, values=ENSEMBLE_TYPE)
        self.ensemble_type_Option_place = lambda:self.ensemble_type_Option.place(x=MAIN_ROW_2_X[1], y=MAIN_ROW_2_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT,relx=2/3, rely=3/11, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.ensemble_type_Label, text=ENSEMBLE_TYPE_HELP)
        
        # Select Music Files Option
    
        # Ensemble Save Ensemble Outputs
        self.ensemble_listbox_Label = self.main_window_LABEL_SET(self.options_Frame, AVAILABLE_MODELS_MAIN_LABEL)
        self.ensemble_listbox_Label_place = lambda:self.ensemble_listbox_Label.place(x=MAIN_ROW_2_X[0], y=MAIN_ROW_2_Y[1], width=0, height=LABEL_HEIGHT, relx=2/3, rely=5/11, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.ensemble_listbox_Frame = tk.Frame(self.options_Frame, highlightbackground='#04332c', highlightcolor='#04332c', highlightthicknes=1)
        self.ensemble_listbox_Option = tk.Listbox(self.ensemble_listbox_Frame, selectmode=tk.MULTIPLE, activestyle='dotbox', font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), background='#070708', exportselection=0, relief=tk.SOLID, borderwidth=0)
        self.ensemble_listbox_scroll = ttk.Scrollbar(self.options_Frame, orient=tk.VERTICAL)
        self.ensemble_listbox_Option.config(yscrollcommand=self.ensemble_listbox_scroll.set)
        self.ensemble_listbox_scroll.configure(command=self.ensemble_listbox_Option.yview)
        self.ensemble_listbox_Option_place = lambda: (self.ensemble_listbox_Frame.place(x=ENSEMBLE_LISTBOX_FRAME_X, y=ENSEMBLE_LISTBOX_FRAME_Y, width=ENSEMBLE_LISTBOX_FRAME_WIDTH, height=ENSEMBLE_LISTBOX_FRAME_HEIGHT, relx=2/3, rely=6/11, relwidth=1/3, relheight=1/self.COL1_ROWS),
                                                    self.ensemble_listbox_scroll.place(x=ENSEMBLE_LISTBOX_SCROLL_X, y=ENSEMBLE_LISTBOX_SCROLL_Y, width=ENSEMBLE_LISTBOX_SCROLL_WIDTH, height=ENSEMBLE_LISTBOX_SCROLL_HEIGHT, relx=2/3, rely=6/11, relwidth=1/10, relheight=1/self.COL1_ROWS))
        self.ensemble_listbox_Option_pack = lambda:self.ensemble_listbox_Option.pack(fill=tk.BOTH, expand=1)
        self.help_hints(self.ensemble_listbox_Label, text=ENSEMBLE_LISTBOX_HELP)
        
        ### AUDIO TOOLS ###

        # Chosen Audio Tool 
        self.chosen_audio_tool_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_AUDIO_TOOLS_MAIN_LABEL)
        self.chosen_audio_tool_Label_place = lambda:self.chosen_audio_tool_Label.place(x=0, y=LOW_MENU_Y[0], width=LEFT_ROW_WIDTH, height=LABEL_HEIGHT, relx=0, rely=6/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.chosen_audio_tool_Option = ComboBoxMenu(self.options_Frame, textvariable=self.chosen_audio_tool_var, values=AUDIO_TOOL_OPTIONS, command=lambda e: self.update_main_widget_states())
        self.chosen_audio_tool_Option_place = lambda:self.chosen_audio_tool_Option.place(x=0, y=LOW_MENU_Y[1], width=LEFT_ROW_WIDTH, height=OPTION_HEIGHT, relx=0, rely=7/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL1_ROWS)
        self.help_hints(self.chosen_audio_tool_Label, text=AUDIO_TOOLS_HELP)
        
        # Choose Agorithim
        self.choose_algorithm_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_MANUAL_ALGORITHM_MAIN_LABEL)
        self.choose_algorithm_Label_place = lambda:self.choose_algorithm_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.choose_algorithm_Option = ComboBoxMenu(self.options_Frame, textvariable=self.choose_algorithm_var, values=MANUAL_ENSEMBLE_OPTIONS)
        self.choose_algorithm_Option_place = lambda:self.choose_algorithm_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        #self.help_hints(self.mdx_segment_size_Label, text=MDX_SEGMENT_SIZE_HELP)
        
        
        # Time Stretch
        self.time_stretch_rate_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_RATE_MAIN_LABEL)
        self.time_stretch_rate_Label_place = lambda:self.time_stretch_rate_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.time_stretch_rate_Option = ComboBoxEditableMenu(self.options_Frame, values=TIME_PITCH, textvariable=self.time_stretch_rate_var, pattern=REG_TIME, default=TIME_PITCH)#
        self.time_stretch_rate_Option_place = lambda:self.time_stretch_rate_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        #self.help_hints(self.mdx_segment_size_Label, text=MDX_SEGMENT_SIZE_HELP)

        # Pitch Rate
        self.pitch_rate_Label = self.main_window_LABEL_SET(self.options_Frame, CHOOSE_SEMITONES_MAIN_LABEL)
        self.pitch_rate_Label_place = lambda:self.pitch_rate_Label.place(x=MAIN_ROW_X[0], y=MAIN_ROW_Y[0], width=0, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.pitch_rate_Option = ComboBoxEditableMenu(self.options_Frame, values=TIME_PITCH, textvariable=self.pitch_rate_var, pattern=REG_PITCH, default=TIME_PITCH)#
        self.pitch_rate_Option_place = lambda:self.pitch_rate_Option.place(x=MAIN_ROW_X[1], y=MAIN_ROW_Y[1], width=MAIN_ROW_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)

        # Is Time Correction
        self.is_time_correction_Option = ttk.Checkbutton(master=self.options_Frame, text=TIME_CORRECTION_TEXT, variable=self.is_time_correction_var)
        self.is_time_correction_Option_place = lambda:self.is_time_correction_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=5/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.is_time_correction_Option, text=IS_TIME_CORRECTION_HELP)
        
        # Is Wav Ensemble
        self.is_wav_ensemble_Option = ttk.Checkbutton(master=self.options_Frame, text=ENSEMBLE_WAVFORMS_TEXT, variable=self.is_wav_ensemble_var)
        self.is_wav_ensemble_Option_place = lambda:self.is_wav_ensemble_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=5/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.is_wav_ensemble_Option, text=IS_WAV_ENSEMBLE_HELP)

        ## ALIGN TOOL ##
        
        # Track 1
        self.fileOne_Label = self.main_window_LABEL_SUB_SET(self.options_Frame, self.file_one_sub_var)
        self.fileOne_Label_place = lambda: self.fileOne_Label.place(x=FILEONE_LABEL_X, y=LABEL_Y, width=FILEONE_LABEL_WIDTH, height=LABEL_HEIGHT, relx=1/3, rely=2/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)

        self.fileOne_Entry = ttk.Entry(master=self.options_Frame, textvariable=self.fileOneEntry_var, font=self.font_entry, state=tk.DISABLED)
        self.fileOne_Entry_place = lambda: self.fileOne_Entry.place(x=SUB_ENT_ROW_X, y=ENTRY_Y, width=ENTRY_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.fileOne_Entry, text=INPUT_SEC_FIELDS_HELP)
        self.fileOne_Entry.configure(cursor="hand2")
        
        self.fileOne_Open = ttk.Button(master=self.options_Frame, image=self.efile_img, command=lambda:OPEN_FILE_func(os.path.dirname(self.fileOneEntry_Full_var.get())))
        self.fileOne_Open_place = lambda:self.fileOne_Open.place(x=ENTRY_OPEN_BUTT_X_OFF, y=ENTRY_Y, width=ENTRY_OPEN_BUTT_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=3/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)#OPEN_FILE_func(Path(self.export_path_var.get())) if os.path.isdir(self.export_path_var.get()) else self.error_dialoge(INVALID_EXPORT))
        self.help_hints(self.fileOne_Open, text=INPUT_FOLDER_BUTTON_HELP)

        # Track 2
        self.fileTwo_Label = self.main_window_LABEL_SUB_SET(self.options_Frame, self.file_two_sub_var)
        self.fileTwo_Label_place = lambda: self.fileTwo_Label.place(x=FILETWO_LABEL_X, y=LABEL_Y, width=FILETWO_LABEL_WIDTH, height=LABEL_HEIGHT, relx=1/3, rely=4.5/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)

        self.fileTwo_Entry = ttk.Entry(master=self.options_Frame, textvariable=self.fileTwoEntry_var, font=self.font_entry, state=tk.DISABLED)
        self.fileTwo_Entry_place = lambda:self.fileTwo_Entry.place(x=SUB_ENT_ROW_X, y=ENTRY_Y, width=ENTRY_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=5.5/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.fileTwo_Entry, text=INPUT_SEC_FIELDS_HELP)
        self.fileTwo_Entry.configure(cursor="hand2")
        
        self.fileTwo_Open = ttk.Button(master=self.options_Frame, image=self.efile_img, command=lambda:OPEN_FILE_func(os.path.dirname(self.fileTwoEntry_Full_var.get())))
        self.fileTwo_Open_place = lambda:self.fileTwo_Open.place(x=ENTRY_OPEN_BUTT_X_OFF, y=ENTRY_Y, width=ENTRY_OPEN_BUTT_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=5.5/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.fileTwo_Open, text=INPUT_FOLDER_BUTTON_HELP)

        # Time Window
        self.time_window_Label = self.main_window_LABEL_SET(self.options_Frame, TIME_WINDOW_MAIN_LABEL)
        self.time_window_Label_place = lambda: self.time_window_Label.place(x=TIME_WINDOW_LABEL_X, y=LABEL_Y, width=TIME_WINDOW_LABEL_WIDTH, height=LABEL_HEIGHT, relx=1/3, rely=7.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.time_window_Option = ComboBoxMenu(self.options_Frame, textvariable=self.time_window_var, values=tuple(TIME_WINDOW_MAPPER.keys()))
        self.time_window_Option_place = lambda: self.time_window_Option.place(x=SUB_ENT_ROW_X, y=ENTRY_Y, width=OPTION_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=8.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.time_window_Label, text=TIME_WINDOW_ALIGN_HELP)

        # Align Shifts
        self.intro_analysis_Label = self.main_window_LABEL_SET(self.options_Frame, INTRO_ANALYSIS_MAIN_LABEL)
        self.intro_analysis_Label_place = lambda: self.intro_analysis_Label.place(x=INTRO_ANALYSIS_LABEL_X, y=LABEL_Y, width=INTRO_ANALYSIS_LABEL_WIDTH, height=LABEL_HEIGHT, relx=2/3, rely=7.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.intro_analysis_Option = ComboBoxMenu(self.options_Frame, textvariable=self.intro_analysis_var, values=tuple(INTRO_MAPPER.keys()))
        self.intro_analysis_Option_place = lambda: self.intro_analysis_Option.place(x=INTRO_ANALYSIS_OPTION_X, y=ENTRY_Y, width=OPTION_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=8.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.intro_analysis_Label, text=INTRO_ANALYSIS_ALIGN_HELP)

        # Volume Adjustment
        self.db_analysis_Label = self.main_window_LABEL_SET(self.options_Frame, VOLUME_ADJUSTMENT_MAIN_LABEL)
        self.db_analysis_Label_place = lambda: self.db_analysis_Label.place(x=DB_ANALYSIS_LABEL_X, y=LABEL_Y, width=DB_ANALYSIS_LABEL_WIDTH, height=LABEL_HEIGHT, relx=2/3, rely=7.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.db_analysis_Option = ComboBoxMenu(self.options_Frame, textvariable=self.db_analysis_var, values=tuple(VOLUME_MAPPER.keys()))
        self.db_analysis_Option_place = lambda: self.db_analysis_Option.place(x=DB_ANALYSIS_OPTION_X, y=ENTRY_Y, width=OPTION_WIDTH, height=OPTION_HEIGHT, relx=2/3, rely=8.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.db_analysis_Label, text=VOLUME_ANALYSIS_ALIGN_HELP)

        # Wav-Type
        self.wav_type_set_Label = self.main_window_LABEL_SET(self.options_Frame, WAVE_TYPE_TEXT)
        self.wav_type_set_Label_place = lambda: self.wav_type_set_Label.place(x=WAV_TYPE_SET_LABEL_X, y=LABEL_Y, width=WAV_TYPE_SET_LABEL_WIDTH, height=LABEL_HEIGHT, relx=1/3, rely=7.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.wav_type_set_Option = ComboBoxMenu(self.options_Frame, textvariable=self.wav_type_set_var, values=WAV_TYPE)
        self.wav_type_set_Option_place = lambda: self.wav_type_set_Option.place(x=SUB_ENT_ROW_X, y=ENTRY_Y, width=OPTION_WIDTH, height=OPTION_HEIGHT, relx=1/3, rely=8.37/self.COL1_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)

        ### SHARED SETTINGS ###
        
        # GPU Selection
        self.is_gpu_conversion_Option = ttk.Checkbutton(master=self.options_Frame, text=GPU_CONVERSION_MAIN_LABEL, variable=self.is_gpu_conversion_var)
        self.is_gpu_conversion_Option_place = lambda:self.is_gpu_conversion_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=5/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.is_gpu_conversion_Disable = lambda:(self.is_gpu_conversion_Option.configure(state=tk.DISABLED), self.is_gpu_conversion_var.set(False))
        self.is_gpu_conversion_Enable = lambda:self.is_gpu_conversion_Option.configure(state=tk.NORMAL)
        self.help_hints(self.is_gpu_conversion_Option, text=IS_GPU_CONVERSION_HELP)

        # Vocal Only
        self.is_primary_stem_only_Option = ttk.Checkbutton(master=self.options_Frame, textvariable=self.is_primary_stem_only_Text_var, variable=self.is_primary_stem_only_var, command=lambda:self.is_primary_stem_only_Option_toggle())
        self.is_primary_stem_only_Option_place = lambda:self.is_primary_stem_only_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=6/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.is_primary_stem_only_Option_toggle = lambda:self.is_secondary_stem_only_var.set(False) if self.is_primary_stem_only_var.get() else self.is_secondary_stem_only_Option.configure(state=tk.NORMAL)
        self.help_hints(self.is_primary_stem_only_Option, text=SAVE_STEM_ONLY_HELP)
        
        # Instrumental Only 
        self.is_secondary_stem_only_Option = ttk.Checkbutton(master=self.options_Frame, textvariable=self.is_secondary_stem_only_Text_var, variable=self.is_secondary_stem_only_var, command=lambda:self.is_secondary_stem_only_Option_toggle())
        self.is_secondary_stem_only_Option_place = lambda:self.is_secondary_stem_only_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=7/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.is_secondary_stem_only_Option_toggle = lambda:self.is_primary_stem_only_var.set(False) if self.is_secondary_stem_only_var.get() else self.is_primary_stem_only_Option.configure(state=tk.NORMAL)
        self.is_stem_only_Options_Enable = lambda:(self.is_primary_stem_only_Option.configure(state=tk.NORMAL), self.is_secondary_stem_only_Option.configure(state=tk.NORMAL))
        self.help_hints(self.is_secondary_stem_only_Option, text=SAVE_STEM_ONLY_HELP)
        
        # Sample Mode
        self.model_sample_mode_Option = ttk.Checkbutton(master=self.options_Frame, textvariable=self.model_sample_mode_duration_checkbox_var, variable=self.model_sample_mode_var)#f'Sample ({self.model_sample_mode_duration_var.get()} Seconds)'
        self.model_sample_mode_Option_place = lambda rely=8:self.model_sample_mode_Option.place(x=CHECK_BOX_X, y=CHECK_BOX_Y, width=CHECK_BOX_WIDTH, height=CHECK_BOX_HEIGHT, relx=1/3, rely=rely/self.COL2_ROWS, relwidth=1/3, relheight=1/self.COL2_ROWS)
        self.help_hints(self.model_sample_mode_Option, text=MODEL_SAMPLE_MODE_HELP)
        
        self.GUI_LIST = (self.vr_model_Label,
        self.vr_model_Option,
        self.aggression_setting_Label,
        self.aggression_setting_Option,
        self.window_size_Label,
        self.window_size_Option,
        self.demucs_model_Label,
        self.demucs_model_Option,
        self.demucs_stems_Label,
        self.demucs_stems_Option,
        self.segment_Label,
        self.segment_Option,
        self.mdx_net_model_Label,
        self.mdx_net_model_Option,
        self.overlap_mdx_Label,
        self.overlap_mdx_Option,
        self.overlap_mdx23_Option,
        self.mdxnet_stems_Label,
        self.mdxnet_stems_Option,
        self.mdx_segment_size_Label,
        self.mdx_segment_size_Option,
        self.chosen_ensemble_Label,
        self.chosen_ensemble_Option,
        self.save_current_settings_Label,
        self.save_current_settings_Option,
        self.ensemble_main_stem_Label,
        self.ensemble_main_stem_Option,
        self.ensemble_type_Label,
        self.ensemble_type_Option,
        self.ensemble_listbox_Label,
        self.ensemble_listbox_Frame,
        self.ensemble_listbox_Option,
        self.ensemble_listbox_scroll,
        self.chosen_audio_tool_Label,
        self.chosen_audio_tool_Option,
        self.choose_algorithm_Label,
        self.choose_algorithm_Option,
        self.time_stretch_rate_Label,
        self.time_stretch_rate_Option,
        self.wav_type_set_Label,
        self.wav_type_set_Option,
        self.pitch_rate_Label,
        self.pitch_rate_Option,
        self.fileOne_Label,
        self.fileOne_Entry,
        self.fileOne_Open,
        self.fileTwo_Label,
        self.fileTwo_Entry,
        self.fileTwo_Open,
        self.intro_analysis_Label,
        self.intro_analysis_Option,
        self.time_window_Label,
        self.time_window_Option,
        self.db_analysis_Label,
        self.db_analysis_Option,
        self.is_gpu_conversion_Option,
        self.is_primary_stem_only_Option,
        self.is_secondary_stem_only_Option,
        self.is_primary_stem_only_Demucs_Option,
        self.is_secondary_stem_only_Demucs_Option,
        self.model_sample_mode_Option,
        self.is_time_correction_Option,
        self.is_wav_ensemble_Option)
        
        REFRESH_VARS = (self.mdx_net_model_var,
                        self.vr_model_var,
                        self.demucs_model_var,
                        # self.demucs_stems_var,
                        # self.mdxnet_stems_var,
                        self.is_chunk_demucs_var,
                        self.is_chunk_mdxnet_var,
                        # self.is_primary_stem_only_Demucs_var,
                        # self.is_secondary_stem_only_Demucs_var,
                        # self.is_primary_stem_only_var,
                        # self.is_secondary_stem_only_var,
                        self.model_download_demucs_var,
                        self.model_download_mdx_var,
                        self.model_download_vr_var,
                        self.select_download_var,
                        # self.is_primary_stem_only_Demucs_Text_var,
                        # self.is_secondary_stem_only_Demucs_Text_var,
                        self.chosen_process_method_var,
                        self.ensemble_main_stem_var)
        
        # Change States
        for var in REFRESH_VARS:
            var.trace_add('write', lambda *args: self.update_button_states())
    
    def combo_box_selection_clear(self, frame:tk.Frame):
        for option in frame.winfo_children():
            if type(option) is ttk.Combobox or type(option) is ComboBoxEditableMenu:
                option.selection_clear()

    def focus_out_widgets(self, all_widgets, frame):
        for option in all_widgets:
            if not type(option) is ComboBoxEditableMenu:
                option.bind('<Button-1>', lambda e:(option.focus(), self.combo_box_selection_clear(frame)))

    def bind_widgets(self):
        """Bind widgets to the drag & drop mechanic"""
        
        self.chosen_audio_tool_align = tk.BooleanVar(value=True)        
        other_items = [self.options_Frame, self.filePaths_Frame, self.title_Label, self.progressbar, self.conversion_Button, self.settings_Button, self.stop_Button, self.command_Text]
        all_widgets = self.options_Frame.winfo_children() + self.filePaths_Frame.winfo_children() + other_items
        self.focus_out_widgets(all_widgets, self.options_Frame)
        
        if is_dnd_compatible:
            self.filePaths_saveTo_Button.drop_target_register(DND_FILES)
            self.filePaths_saveTo_Entry.drop_target_register(DND_FILES)
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', lambda e: drop(e, accept_mode='files'))
            self.filePaths_saveTo_Button.dnd_bind('<<Drop>>', lambda e: drop(e, accept_mode='folder'))
            self.filePaths_saveTo_Entry.dnd_bind('<<Drop>>', lambda e: drop(e, accept_mode='folder'))    
            
            self.fileOne_Entry.drop_target_register(DND_FILES)
            self.fileTwo_Entry.drop_target_register(DND_FILES)
            self.fileOne_Entry.dnd_bind('<<Drop>>', lambda e: drop(e, accept_mode=FILE_1))
            self.fileTwo_Entry.dnd_bind('<<Drop>>', lambda e: drop(e, accept_mode=FILE_2))    
            
        self.ensemble_listbox_Option.bind('<<ListboxSelect>>', lambda e: self.chosen_ensemble_var.set(CHOOSE_ENSEMBLE_OPTION))
        self.options_Frame.bind(right_click_button, lambda e:(self.right_click_menu_popup(e, main_menu=True), self.options_Frame.focus()))
        self.filePaths_musicFile_Entry.bind(right_click_button, lambda e:(self.input_right_click_menu(e), self.filePaths_musicFile_Entry.focus()))
        self.filePaths_musicFile_Entry.bind('<Button-1>', lambda e:(self.check_is_menu_open(INPUTS_MENU), self.filePaths_musicFile_Entry.focus()))

        self.fileOne_Entry.bind('<Button-1>', lambda e:self.menu_batch_dual())
        self.fileTwo_Entry.bind('<Button-1>', lambda e:self.menu_batch_dual())
        self.fileOne_Entry.bind(right_click_button, lambda e:self.input_dual_right_click_menu(e, is_primary=True))
        self.fileTwo_Entry.bind(right_click_button, lambda e:self.input_dual_right_click_menu(e, is_primary=False))
        if not is_macos:
            self.bind("<Configure>", self.adjust_toplevel_positions)
        
    def auto_save(self):
        try:
            self.save_values(app_close=False, is_auto_save=True)
        except Exception as e:
            print(e)

    #--Input/Export Methods--
    
    def linux_filebox_fix(self, is_on=True):
        self.file_inputs().linux_filebox_fix(is_on)

    def show_file_dialog(self, text='Select Audio files', dialoge_type=None):
        return self.file_inputs().show_file_dialog(text=text, dialoge_type=dialoge_type)

    def input_select_filedialog(self):
        """Make user select music files"""
        self.file_inputs().input_select_filedialog()

    def export_select_filedialog(self):
        """Make user select a folder to export the converted files in"""
        return self.file_inputs().export_select_filedialog()
     
    def update_inputPaths(self):
        """Update the music file entry"""
        self.file_inputs().update_input_paths()

    def select_audiofile(self, path=None, is_primary=True): 
        """Make user select music files"""
        self.file_inputs().select_audiofile(path=path, is_primary=is_primary)
            
    #--Utility Methods--

    def restart(self):
        """Restart the application after asking for confirmation"""
        
        confirm = messagebox.askyesno(parent=root,
                                         title=CONFIRM_RESTART_TEXT[0],
                                         message=CONFIRM_RESTART_TEXT[1])
        
        if confirm:
            self.save_values(app_close=True, is_restart=True)
        
    def delete_temps(self, is_start_up=False):  
        """Deletes temp files"""
        
        DIRECTORIES = (BASE_PATH, VR_MODELS_DIR, MDX_MODELS_DIR, DEMUCS_MODELS_DIR, DEMUCS_NEWER_REPO_DIR)
        EXTENSIONS = (('.aes', '.txt', '.tmp'))
        
        try:
            if os.path.isfile(f"{current_patch}{application_extension}"):
                os.remove(f"{current_patch}{application_extension}")
            
            if not is_start_up:
                if os.path.isfile(SPLASH_DOC):
                    os.remove(SPLASH_DOC)
            
            for dir in DIRECTORIES:
                for temp_file in os.listdir(dir):
                    if temp_file.endswith(EXTENSIONS):
                        if os.path.isfile(os.path.join(dir, temp_file)):
                            os.remove(os.path.join(dir, temp_file))
        except Exception as e:
            self.error_log_var.set(error_text(TEMP_FILE_DELETION_TEXT, e))
        
    def get_files_from_dir(self, directory, ext, is_mdxnet=False):
        """Gets files from specified directory that ends with specified extention"""
        
        return tuple(
            x if is_mdxnet and x.endswith(CKPT) else os.path.splitext(x)[0]
            for x in os.listdir(directory)
            if x.endswith(ext)
        )
        
    def return_ensemble_stems(self, is_primary=False): 
        """Grabs and returns the chosen ensemble stems."""
        
        ensemble_stem = self.ensemble_main_stem_var.get().partition("/")
        
        if is_primary:
            return ensemble_stem[0]
        else:
            return ensemble_stem[0], ensemble_stem[2]

    def message_box(self, message):
        """Template for confirmation box"""
        
        confirm = messagebox.askyesno(title=message[0],
                                         message=message[1],
                                         parent=root)
        
        return confirm

    def error_dialoge(self, message):
        """Template for messagebox that informs user of error"""

        messagebox.showerror(master=self,
                                  title=message[0],
                                  message=message[1],
                                  parent=root) 
      
    def model_list(self, primary_stem: str, secondary_stem: str, is_4_stem_check=False, is_multi_stem=False, is_dry_check=False, is_no_demucs=False, is_check_vocal_split=False):
        
        stem_check = self.assemble_model_data(arch_type=ENSEMBLE_STEM_CHECK, is_dry_check=is_dry_check)
        
        def matches_stem(model: ModelData):
            primary_match = model.primary_stem in {primary_stem, secondary_stem}
            mdx_stem_match = primary_stem in model.mdx_model_stems and model.mdx_stem_count <= 2
            return primary_match or mdx_stem_match if is_no_demucs else primary_match or primary_stem in model.mdx_model_stems

        result = []

        for model in stem_check:
            if is_multi_stem:
                result.append(model.model_and_process_tag)
            elif is_4_stem_check and (model.demucs_stem_count == 4 or model.mdx_stem_count == 4):
                result.append(model.model_and_process_tag)
            elif matches_stem(model) or (not is_no_demucs and primary_stem.lower() in model.demucs_source_list):
                if is_check_vocal_split:
                    model_name = None if model.is_karaoke or not model.vocal_split_model else model.model_basename
                else: 
                    model_name = model.model_and_process_tag
                    
                result.append(model_name)

        return result

    def help_hints(self, widget, text):
        toolTip = ToolTip(widget)
        def enter(event):
            if self.help_hints_var.get():
                toolTip.showtip(text)
        def leave(event):
            toolTip.hidetip()
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)
        widget.bind(right_click_button, lambda e:copy_help_hint(e))

        def copy_help_hint(event):
            if self.help_hints_var.get():
                right_click_menu = tk.Menu(self, font=(MAIN_FONT_NAME, FONT_SIZE_1), tearoff=0)
                right_click_menu.add_command(label='Copy Help Hint Text', command=right_click_menu_copy_hint)
                
                try:
                    right_click_menu.tk_popup(event.x_root,event.y_root)
                    right_click_release_linux(right_click_menu)
                finally:
                    right_click_menu.grab_release()
            else:
                if widget.winfo_toplevel() == root:
                    self.right_click_menu_popup(event, main_menu=True)

        def right_click_menu_copy_hint():
            pyperclip.copy(text)

    def check_is_menu_open(self, menu):
        try:
            menu_mapping = {
                VR_OPTION: (self.is_open_menu_advanced_vr_options, self.menu_advanced_vr_options, self.menu_advanced_vr_options_close_window),
                DEMUCS_OPTION: (self.is_open_menu_advanced_demucs_options, self.menu_advanced_demucs_options, self.menu_advanced_demucs_options_close_window),
                MDX_OPTION: (self.is_open_menu_advanced_mdx_options, self.menu_advanced_mdx_options, self.menu_advanced_mdx_options_close_window),
                ENSEMBLE_OPTION: (self.is_open_menu_advanced_ensemble_options, self.menu_advanced_ensemble_options, self.menu_advanced_ensemble_options_close_window),
                HELP_OPTION: (self.is_open_menu_help, self.menu_help, self.menu_help_close_window),
                ERROR_OPTION: (self.is_open_menu_error_log, self.menu_error_log, self.menu_error_log_close_window),
                INPUTS_MENU: (self.is_open_menu_view_inputs, self.menu_view_inputs, self.menu_view_inputs_close_window),
                ALIGNMENT_TOOL: (self.is_open_menu_advanced_align_options, self.menu_advanced_align_options, self.menu_advanced_align_options_close_window)
            }

            is_open, open_method, close_method = menu_mapping.get(menu, (None, None, None))
            if is_open and is_open.get():
                close_method()
            open_method()
        except Exception as e:
            self.error_log_var.set("{}".format(error_text(menu, e)))

    def input_right_click_menu(self, event):
        self.input_menus().input_right_click_menu(event)

    def input_dual_right_click_menu(self, event, is_primary:bool):
        self.input_menus().input_dual_right_click_menu(event, is_primary=is_primary)

    def cached_sources_clear(self):

        self.vr_cache_source_mapper = {}
        self.mdx_cache_source_mapper = {}
        self.demucs_cache_source_mapper = {}

    def cached_source_callback(self, process_method, model_name=None):
        
        model, sources = None, None
        
        if process_method == VR_ARCH_TYPE:
            mapper = self.vr_cache_source_mapper
        if process_method == MDX_ARCH_TYPE:
            mapper = self.mdx_cache_source_mapper
        if process_method == DEMUCS_ARCH_TYPE:
            mapper = self.demucs_cache_source_mapper
        
        for key, value in mapper.items():
            if model_name in key:
                model = key
                sources = value
        
        return model, sources

    def cached_model_source_holder(self, process_method, sources, model_name=None):
        
        if process_method == VR_ARCH_TYPE:
            self.vr_cache_source_mapper = {**self.vr_cache_source_mapper, **{model_name: sources}}
        if process_method == MDX_ARCH_TYPE:
            self.mdx_cache_source_mapper = {**self.mdx_cache_source_mapper, **{model_name: sources}}
        if process_method == DEMUCS_ARCH_TYPE:
            self.demucs_cache_source_mapper = {**self.demucs_cache_source_mapper, **{model_name: sources}}
  
    def cached_source_model_list_check(self, model_list: List[ModelData]):

        model: ModelData
        primary_model_names = lambda process_method:[model.model_basename if model.process_method == process_method else None for model in model_list]
        secondary_model_names = lambda process_method:[model.secondary_model.model_basename if model.is_secondary_model_activated and model.process_method == process_method else None for model in model_list]

        self.vr_primary_model_names = primary_model_names(VR_ARCH_TYPE)
        self.mdx_primary_model_names = primary_model_names(MDX_ARCH_TYPE)
        self.demucs_primary_model_names = primary_model_names(DEMUCS_ARCH_TYPE)
        self.vr_secondary_model_names = secondary_model_names(VR_ARCH_TYPE)
        self.mdx_secondary_model_names = secondary_model_names(MDX_ARCH_TYPE)
        self.demucs_secondary_model_names = [model.secondary_model.model_basename if model.is_secondary_model_activated and model.process_method == DEMUCS_ARCH_TYPE and not model.secondary_model is None else None for model in model_list]
        self.demucs_pre_proc_model_name = [model.pre_proc_model.model_basename if model.pre_proc_model else None for model in model_list]#list(dict.fromkeys())
        
        for model in model_list:
            if model.process_method == DEMUCS_ARCH_TYPE and model.is_demucs_4_stem_secondaries:
                if not model.is_4_stem_ensemble:
                    self.demucs_secondary_model_names = model.secondary_model_4_stem_model_names_list
                    break
                else:
                    for i in model.secondary_model_4_stem_model_names_list:
                        self.demucs_secondary_model_names.append(i)
        
        self.all_models = self.vr_primary_model_names + self.mdx_primary_model_names + self.demucs_primary_model_names + self.vr_secondary_model_names + self.mdx_secondary_model_names + self.demucs_secondary_model_names + self.demucs_pre_proc_model_name
      
    def verify_audio(self, audio_file, is_process=True, sample_path=None):
        is_good = False
        error_data = ''
        
        if not type(audio_file) is tuple:
            audio_file = [audio_file]

        for i in audio_file:
            if os.path.isfile(i):
                try:
                    librosa.load(i, duration=3, mono=False, sr=44100) if not type(sample_path) is str else self.create_sample(i, sample_path)
                    is_good = True
                except Exception as e:
                    error_name = f'{type(e).__name__}'
                    traceback_text = ''.join(traceback.format_tb(e.__traceback__))
                    message = f'{error_name}: "{e}"\n{traceback_text}"'
                    if is_process:
                        audio_base_name = os.path.basename(i)
                        self.error_log_var.set(f'{ERROR_LOADING_FILE_TEXT[0]}:\n\n\"{audio_base_name}\"\n\n{ERROR_LOADING_FILE_TEXT[1]}:\n\n{message}')
                    else:
                        error_data = AUDIO_VERIFICATION_CHECK(i, message)

        if is_process:
            return is_good
        else:
            return is_good, error_data
      
    def create_sample(self, audio_file, sample_path=SAMPLE_CLIP_PATH):
        try:
            with audioread.audio_open(audio_file) as f:
                track_length = int(f.duration)
        except Exception as e:
            print('Audioread failed to get duration. Trying Librosa...')
            y, sr = librosa.load(audio_file, mono=False, sr=44100)
            track_length = int(librosa.get_duration(y=y, sr=sr))
        
        clip_duration = int(self.model_sample_mode_duration_var.get())
        
        if track_length >= clip_duration:
            offset_cut = track_length//3
            off_cut = offset_cut + track_length
            if not off_cut >= clip_duration:
                offset_cut = 0
            name_apped = f'{clip_duration}_second_'
        else:
            offset_cut, clip_duration = 0, track_length
            name_apped = ''

        sample = librosa.load(audio_file, offset=offset_cut, duration=clip_duration, mono=False, sr=44100)[0].T
        audio_sample = os.path.join(sample_path, f'{os.path.splitext(os.path.basename(audio_file))[0]}_{name_apped}sample.wav')
        sf.write(audio_sample, sample, 44100)
        
        return audio_sample

    #--Right Click Menu Pop-Ups--

    def right_click_select_settings_sub(self, parent_menu, process_method):
        saved_settings_sub_menu = tk.Menu(parent_menu, font=(MAIN_FONT_NAME, FONT_SIZE_1), tearoff=False)
        settings_options = self.last_found_settings + tuple(SAVE_SET_OPTIONS)
        
        for settings_options in settings_options:
            settings_options = settings_options.replace("_", " ")
            saved_settings_sub_menu.add_command(label=settings_options, command=lambda o=settings_options:self.selection_action_saved_settings(o, process_method=process_method))

        saved_settings_sub_menu.insert_separator(len(self.last_found_settings))
        
        return saved_settings_sub_menu

    def right_click_menu_popup(self, event, text_box=False, main_menu=False):
        
        def add_text_edit_options(menu):
            """Add options related to text editing."""
            menu.add_command(label='Copy', command=self.right_click_menu_copy)
            menu.add_command(label='Paste', command=lambda: self.right_click_menu_paste(text_box=text_box))
            menu.add_command(label='Delete', command=lambda: self.right_click_menu_delete(text_box=text_box))
        
        def add_advanced_settings_options(menu, settings_mapper, var_mapper):
            """Add advanced settings options to the menu."""
            current_method = self.chosen_process_method_var.get()
            
            if current_method in settings_mapper and (var_mapper[current_method] or (current_method == DEMUCS_ARCH_TYPE and self.is_demucs_pre_proc_model_activate_var.get())):
                menu.add_cascade(label='Select Saved Settings', menu=saved_settings_sub_load_for_menu)
                menu.add_separator()
                for method, option in settings_mapper.items():
                    if method != ENSEMBLE_MODE or current_method == ENSEMBLE_MODE:
                        menu.add_command(label=f'Advanced {method} Settings', command=option)
            elif current_method in settings_mapper:
                menu.add_command(label=f'Advanced {current_method} Settings', command=settings_mapper[current_method])

        # Create the right-click menu
        right_click_menu = tk.Menu(self, font=(MAIN_FONT_NAME, FONT_SIZE_1), tearoff=0)

        # Mappings
        settings_mapper = {
            ENSEMBLE_MODE: lambda: self.check_is_menu_open(ENSEMBLE_OPTION),
            VR_ARCH_PM: lambda: self.check_is_menu_open(VR_OPTION),
            MDX_ARCH_TYPE: lambda: self.check_is_menu_open(MDX_OPTION),
            DEMUCS_ARCH_TYPE: lambda: self.check_is_menu_open(DEMUCS_OPTION)
        }
        
        var_mapper = {
            ENSEMBLE_MODE: True,
            VR_ARCH_PM: self.vr_is_secondary_model_activate_var.get(),
            MDX_ARCH_TYPE: self.mdx_is_secondary_model_activate_var.get(),
            DEMUCS_ARCH_TYPE: self.demucs_is_secondary_model_activate_var.get()
        }

        # Submenu for saved settings
        saved_settings_sub_load_for_menu = tk.Menu(right_click_menu, font=(MAIN_FONT_NAME, FONT_SIZE_1), tearoff=False)
        for label, arch_type in [(VR_ARCH_SETTING_LOAD, VR_ARCH_PM), (MDX_SETTING_LOAD, MDX_ARCH_TYPE), (DEMUCS_SETTING_LOAD, DEMUCS_ARCH_TYPE), (ALL_ARCH_SETTING_LOAD, None)]:
            submenu = self.right_click_select_settings_sub(saved_settings_sub_load_for_menu, arch_type)
            saved_settings_sub_load_for_menu.add_cascade(label=label, menu=submenu)

        if not main_menu:
            add_text_edit_options(right_click_menu)
        else:
            if self.chosen_process_method_var.get() == AUDIO_TOOLS and self.chosen_audio_tool_var.get() == ALIGN_INPUTS:
                right_click_menu.add_command(label='Advanced Align Tool Settings', command=lambda: self.check_is_menu_open(ALIGNMENT_TOOL))
            else:
                add_advanced_settings_options(right_click_menu, settings_mapper, var_mapper)

            # Additional Settings and Help Hints
            if not self.is_menu_settings_open:
                right_click_menu.add_command(label='Additional Settings', command=lambda: self.menu_settings(select_tab_2=True))
                
            help_hints_label = 'Enable' if not self.help_hints_var.get() else 'Disable'
            right_click_menu.add_command(label=f'{help_hints_label} Help Hints', command=lambda: self.help_hints_var.set(not self.help_hints_var.get()))
                
            if self.error_log_var.get():
                right_click_menu.add_command(label='Error Log', command=lambda: self.check_is_menu_open(ERROR_OPTION))

        try:
            right_click_menu.tk_popup(event.x_root, event.y_root)
            right_click_release_linux(right_click_menu)
        finally:
            right_click_menu.grab_release()

    def right_click_menu_copy(self):
        hightlighted_text = self.current_text_box.selection_get()
        self.clipboard_clear()
        self.clipboard_append(hightlighted_text)

    def right_click_menu_paste(self, text_box=False):
        clipboard = self.clipboard_get()
        self.right_click_menu_delete(text_box=True) if text_box else self.right_click_menu_delete()
        self.current_text_box.insert(self.current_text_box.index(tk.INSERT), clipboard)

    def right_click_menu_delete(self, text_box=False):
        if text_box:
            try:
                s0 = self.current_text_box.index("sel.first")
                s1 = self.current_text_box.index("sel.last")
                self.current_text_box.tag_configure('highlight')
                self.current_text_box.tag_add("highlight", s0, s1)
                start_indexes = self.current_text_box.tag_ranges("highlight")[0::2]
                end_indexes = self.current_text_box.tag_ranges("highlight")[1::2]

                for start, end in zip(start_indexes, end_indexes):
                    self.current_text_box.tag_remove("highlight", start, end)

                for start, end in zip(start_indexes, end_indexes):
                    self.current_text_box.delete(start, end)
            except Exception as e:
                print('RIGHT-CLICK-DELETE ERROR: \n', e)
        else:
            self.current_text_box.delete(0, tk.END)
    
    def right_click_console(self, event):
        right_click_menu = tk.Menu(self, font=(MAIN_FONT_NAME, FONT_SIZE_1), tearoff=0)
        right_click_menu.add_command(label='Copy', command=self.command_Text.copy_text)
        right_click_menu.add_command(label='Select All', command=self.command_Text.select_all_text)
        
        try:
            right_click_menu.tk_popup(event.x_root,event.y_root)
            right_click_release_linux(right_click_menu)
        finally:
            right_click_menu.grab_release()

    #--Secondary Window Methods--

    def vocal_splitter_Button_opt(self, top_window, frame, pady, width=15):
        self.menu_helpers().vocal_splitter_button_opt(top_window, frame, pady, width)

    def adjust_toplevel_positions(self, event):
        # Copy the list to avoid modifying while iterating
        for toplevel in self.toplevels.copy():
            # Check if the toplevel window is still alive
            if not toplevel.winfo_exists():
                self.toplevels.remove(toplevel)
            else:
                menu_offset_x = (root.winfo_width() - toplevel.winfo_width()) // 2
                menu_offset_y = (root.winfo_height() - toplevel.winfo_height()) // 2
                toplevel.geometry("+%d+%d" % (root.winfo_x() + menu_offset_x, root.winfo_y() + menu_offset_y))

    def menu_placement(self, window: tk.Toplevel, title, pop_up=False, is_help_hints=False, close_function=None, frame_list=None, top_window=None):
        """Prepares and centers each secondary window relative to the main window"""
        self.menu_helpers().menu_placement(
            window,
            title,
            pop_up=pop_up,
            is_help_hints=is_help_hints,
            close_function=close_function,
            frame_list=frame_list,
            top_window=top_window,
        )
            
    def adjust_widget_widths(self, frame):
        self.menu_helpers().adjust_widget_widths(frame)

    def menu_move_tab(notebook: ttk.Notebook, tab_text, new_position):
        common_menus_module.MenuHelpers(None).menu_move_tab(notebook, tab_text, new_position)
          
    def menu_tab_control(self, toplevel, ai_network_vars, is_demucs=False, is_mdxnet=False):
        """Prepares the tabs setup for some windows"""
        return self.menu_helpers().menu_tab_control(
            toplevel,
            ai_network_vars,
            is_demucs=is_demucs,
            is_mdxnet=is_mdxnet,
        )

    def menu_view_inputs(self):
        self.input_menus().menu_view_inputs()

    def menu_batch_dual(self):
        self.input_menus().menu_batch_dual()

    def check_dual_paths(self, is_fill_menu=False):
        return self.file_inputs().check_dual_paths(is_fill_menu=is_fill_menu)

    def fill_gpu_list(self):
        try:
            if cuda_available:
                self.cuda_device_list = [f"{torch.cuda.get_device_properties(i).name}:{i}" for i in range(torch.cuda.device_count())]
                self.cuda_device_list.insert(0, DEFAULT)
                #print(self.cuda_device_list)
            
            # if directml_available:
            #     self.opencl_list = [f"{torch_directml.device_name(i)}:{i}" for i in range(torch_directml.device_count())]
            #     self.opencl_list.insert(0, DEFAULT)
        except Exception as e:
            print(e)
            
        # if is_cuda_only:
        #     self.is_use_opencl_var.set(False)
            
        check_gpu_list = self.cuda_device_list#self.opencl_list if is_opencl_only or self.is_use_opencl_var.get() else self.cuda_device_list
        if not self.device_set_var.get() in check_gpu_list:
            self.device_set_var.set(DEFAULT)

    def loop_gpu_list(self, option_menu:ComboBoxMenu, menu_name, option_list):
        option_menu['values'] = option_list
        option_menu.update_dropdown_size(option_list, menu_name)

    def menu_settings(self, select_tab_2=False, select_tab_3=False):#**
        """Open Settings and Download Center"""

        settings_menu = tk.Toplevel()
        
        option_var = tk.StringVar(value=SELECT_SAVED_SETTING)
        self.is_menu_settings_open = True
        
        tabControl = ttk.Notebook(settings_menu)
  
        tab1 = ttk.Frame(tabControl)
        tab2 = ttk.Frame(tabControl)
        tab3 = ttk.Frame(tabControl)

        tabControl.add(tab1, text = SETTINGS_GUIDE_TEXT)
        tabControl.add(tab2, text = ADDITIONAL_SETTINGS_TEXT)
        tabControl.add(tab3, text = DOWNLOAD_CENTER_TEXT)

        tabControl.pack(expand = 1, fill ="both")
        
        tab1.grid_rowconfigure(0, weight=1)
        tab1.grid_columnconfigure(0, weight=1)
        
        tab2.grid_rowconfigure(0, weight=1)
        tab2.grid_columnconfigure(0, weight=1)
        
        tab3.grid_rowconfigure(0, weight=1)
        tab3.grid_columnconfigure(0, weight=1)

        self.disable_tabs = lambda:(tabControl.tab(0, state="disabled"), tabControl.tab(1, state="disabled"))
        self.enable_tabs = lambda:(tabControl.tab(0, state="normal"), tabControl.tab(1, state="normal"))        
        self.main_menu_var = tk.StringVar(value=CHOOSE_ADVANCED_MENU_TEXT) 

        self.download_progress_bar_var.set(0)
        self.download_progress_info_var.set('')
        self.download_progress_percent_var.set('')
                
        def set_vars_for_sample_mode(event):
            value = int(float(event))
            value = round(value / 5) * 5
            self.model_sample_mode_duration_var.set(value)
            self.model_sample_mode_duration_checkbox_var.set(SAMPLE_MODE_CHECKBOX(value))
            self.model_sample_mode_duration_label_var.set(f'{value} {SECONDS_TEXT}')
            
        #Settings Tab 1
        settings_menu_main_Frame = self.menu_FRAME_SET(tab1)
        settings_menu_main_Frame.grid(row=0)  
        settings_title_Label = self.menu_title_LABEL_SET(settings_menu_main_Frame, GENERAL_MENU_TEXT)
        settings_title_Label.grid(pady=MENU_PADDING_2)
        
        select_Label = self.menu_sub_LABEL_SET(settings_menu_main_Frame, ADDITIONAL_MENUS_INFORMATION_TEXT)
        select_Label.grid(pady=MENU_PADDING_1)
        
        select_Option = ComboBoxMenu(settings_menu_main_Frame, textvariable=self.main_menu_var, values=OPTION_LIST, width=GEN_SETTINGS_WIDTH+3)
        select_Option.update_dropdown_size(OPTION_LIST, 'menuchoose', command=lambda e:(self.check_is_menu_open(self.main_menu_var.get()), close_window()))
        select_Option.grid(pady=MENU_PADDING_1)
        
        help_hints_Option = ttk.Checkbutton(settings_menu_main_Frame, text=ENABLE_HELP_HINTS_TEXT, variable=self.help_hints_var, width=HELP_HINT_CHECKBOX_WIDTH) 
        help_hints_Option.grid(pady=MENU_PADDING_1)
        
        open_app_dir_Button = ttk.Button(settings_menu_main_Frame, text=OPEN_APPLICATION_DIRECTORY_TEXT, command=lambda:OPEN_FILE_func(BASE_PATH), width=SETTINGS_BUT_WIDTH)
        open_app_dir_Button.grid(pady=MENU_PADDING_1)
        
        reset_all_app_settings_Button = ttk.Button(settings_menu_main_Frame, text=RESET_ALL_SETTINGS_TO_DEFAULT_TEXT, command=lambda:self.load_to_default_confirm(), width=SETTINGS_BUT_WIDTH)#pop_up_change_model_defaults
        reset_all_app_settings_Button.grid(pady=MENU_PADDING_1)
        
        if is_windows:
            restart_app_Button = ttk.Button(settings_menu_main_Frame, text=RESTART_APPLICATION_TEXT, command=lambda:self.restart())
            restart_app_Button.grid(pady=MENU_PADDING_1)

        delete_your_settings_Label = self.menu_title_LABEL_SET(settings_menu_main_Frame, DELETE_USER_SAVED_SETTING_TEXT)
        delete_your_settings_Label.grid(pady=MENU_PADDING_2)
        self.help_hints(delete_your_settings_Label, text=DELETE_YOUR_SETTINGS_HELP)
        
        delete_your_settings_Option = ComboBoxMenu(settings_menu_main_Frame, textvariable=option_var, width=GEN_SETTINGS_WIDTH+3)
        delete_your_settings_Option.grid(padx=20,pady=MENU_PADDING_1)
        self.deletion_list_fill(delete_your_settings_Option, option_var, SETTINGS_CACHE_DIR, SELECT_SAVED_SETTING, menu_name='deletesetting')

        app_update_Label = self.menu_title_LABEL_SET(settings_menu_main_Frame, APPLICATION_UPDATES_TEXT)
        app_update_Label.grid(pady=MENU_PADDING_2)
        
        self.app_update_button = ttk.Button(settings_menu_main_Frame, textvariable=self.app_update_button_Text_var, width=SETTINGS_BUT_WIDTH-2, command=lambda:self.pop_up_update_confirmation())
        self.app_update_button.grid(pady=MENU_PADDING_1)
        
        self.app_update_status_Label = tk.Label(settings_menu_main_Frame, textvariable=self.app_update_status_Text_var, padx=3, pady=3, font=(MAIN_FONT_NAME,  f"{FONT_SIZE_4}"), width=UPDATE_LABEL_WIDTH, justify="center", relief="ridge", fg="#13849f")
        self.app_update_status_Label.grid(pady=20)
        
        donate_Button = ttk.Button(settings_menu_main_Frame, image=self.donate_img, command=lambda:webbrowser.open_new_tab(DONATE_LINK_BMAC))
        donate_Button.grid(pady=MENU_PADDING_2)
        self.help_hints(donate_Button, text=DONATE_HELP)
        
        close_settings_win_Button = ttk.Button(settings_menu_main_Frame, text=CLOSE_WINDOW, command=lambda:close_window())
        close_settings_win_Button.grid(pady=MENU_PADDING_1)      
          
        #Settings Tab 2
        settings_menu_format_Frame = self.menu_FRAME_SET(tab2)
        settings_menu_format_Frame.grid(row=0)  
        
        audio_format_title_Label = self.menu_title_LABEL_SET(settings_menu_format_Frame, AUDIO_FORMAT_SETTINGS_TEXT, width=20)
        audio_format_title_Label.grid(pady=MENU_PADDING_2)
        
        wav_type_set_Label = self.menu_sub_LABEL_SET(settings_menu_format_Frame, WAV_TYPE_TEXT)
        wav_type_set_Label.grid(pady=MENU_PADDING_1)
        
        wav_type_set_Option = ComboBoxMenu(settings_menu_format_Frame, textvariable=self.wav_type_set_var, values=WAV_TYPE, width=HELP_HINT_CHECKBOX_WIDTH)
        wav_type_set_Option.grid(padx=20,pady=MENU_PADDING_1)
        
        mp3_bit_set_Label = self.menu_sub_LABEL_SET(settings_menu_format_Frame, MP3_BITRATE_TEXT)
        mp3_bit_set_Label.grid(pady=MENU_PADDING_1)
        
        mp3_bit_set_Option = ComboBoxMenu(settings_menu_format_Frame, textvariable=self.mp3_bit_set_var, values=MP3_BIT_RATES, width=HELP_HINT_CHECKBOX_WIDTH)
        mp3_bit_set_Option.grid(padx=20,pady=MENU_PADDING_1)

        audio_format_title_Label = self.menu_title_LABEL_SET(settings_menu_format_Frame, GENERAL_PROCESS_SETTINGS_TEXT)
        audio_format_title_Label.grid(pady=MENU_PADDING_2)
        
        is_testing_audio_Option = ttk.Checkbutton(settings_menu_format_Frame, text=SETTINGS_TEST_MODE_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_testing_audio_var) 
        is_testing_audio_Option.grid()
        self.help_hints(is_testing_audio_Option, text=IS_TESTING_AUDIO_HELP)
        
        is_add_model_name_Option = ttk.Checkbutton(settings_menu_format_Frame, text=MODEL_TEST_MODE_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_add_model_name_var) 
        is_add_model_name_Option.grid()
        self.help_hints(is_add_model_name_Option, text=IS_MODEL_TESTING_AUDIO_HELP)
        
        is_create_model_folder_Option = ttk.Checkbutton(settings_menu_format_Frame, text=GENERATE_MODEL_FOLDER_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_create_model_folder_var) 
        is_create_model_folder_Option.grid()
        self.help_hints(is_create_model_folder_Option, text=IS_CREATE_MODEL_FOLDER_HELP)
        
        is_accept_any_input_Option = ttk.Checkbutton(settings_menu_format_Frame, text=ACCEPT_ANY_INPUT_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_accept_any_input_var) 
        is_accept_any_input_Option.grid()
        self.help_hints(is_accept_any_input_Option, text=IS_ACCEPT_ANY_INPUT_HELP)
        
        is_task_complete_Option = ttk.Checkbutton(settings_menu_format_Frame, text=NOTIFICATION_CHIMES_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_task_complete_var) 
        is_task_complete_Option.grid()
        self.help_hints(is_task_complete_Option, text=IS_TASK_COMPLETE_HELP)
        
        is_normalization_Option = ttk.Checkbutton(settings_menu_format_Frame, text=NORMALIZE_OUTPUT_TEXT, width=GEN_SETTINGS_WIDTH, variable=self.is_normalization_var) 
        is_normalization_Option.grid()
        self.help_hints(is_normalization_Option, text=IS_NORMALIZATION_HELP)
        
        change_model_default_Button = ttk.Button(settings_menu_format_Frame, text=CHANGE_MODEL_DEFAULTS_TEXT, command=lambda:self.pop_up_change_model_defaults(settings_menu), width=SETTINGS_BUT_WIDTH-2)#
        change_model_default_Button.grid(pady=MENU_PADDING_4)

        #if not is_choose_arch:
        self.vocal_splitter_Button_opt(settings_menu, settings_menu_format_Frame, width=SETTINGS_BUT_WIDTH-2, pady=MENU_PADDING_4)

        if not is_macos and self.is_gpu_available:
            gpu_list_options = lambda:self.loop_gpu_list(device_set_Option, 'gpudevice', self.cuda_device_list)#self.opencl_list if is_opencl_only or self.is_use_opencl_var.get() else self.cuda_device_list)
            device_set_Label = self.menu_title_LABEL_SET(settings_menu_format_Frame, CUDA_NUM_TEXT)
            device_set_Label.grid(pady=MENU_PADDING_2)
            
            device_set_Option = ComboBoxMenu(settings_menu_format_Frame, textvariable=self.device_set_var, values=GPU_DEVICE_NUM_OPTS, width=GEN_SETTINGS_WIDTH+1)
            device_set_Option.grid(padx=20,pady=MENU_PADDING_1)
            gpu_list_options()
            self.help_hints(device_set_Label, text=IS_CUDA_SELECT_HELP)
            
            # if is_choose_arch:
            #     is_use_opencl_Option = ttk.Checkbutton(settings_menu_format_Frame, 
            #                                            text=USE_OPENCL_TEXT, 
            #                                            width=9, 
            #                                            variable=self.is_use_opencl_var, 
            #                                            command=lambda:(gpu_list_options(), self.device_set_var.set(DEFAULT))) 
            #     is_use_opencl_Option.grid()
            #     self.help_hints(is_use_opencl_Option, text=IS_NORMALIZATION_HELP)

        model_sample_mode_Label = self.menu_title_LABEL_SET(settings_menu_format_Frame, MODEL_SAMPLE_MODE_SETTINGS_TEXT)
        model_sample_mode_Label.grid(pady=MENU_PADDING_2)
        
        model_sample_mode_duration_Label = self.menu_sub_LABEL_SET(settings_menu_format_Frame, SAMPLE_CLIP_DURATION_TEXT)
        model_sample_mode_duration_Label.grid(pady=MENU_PADDING_1)
        
        tk.Label(settings_menu_format_Frame, textvariable=self.model_sample_mode_duration_label_var, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground=FG_COLOR).grid(pady=2)
        model_sample_mode_duration_Option = ttk.Scale(settings_menu_format_Frame, variable=self.model_sample_mode_duration_var, from_=5, to=120, command=set_vars_for_sample_mode, orient='horizontal')
        model_sample_mode_duration_Option.grid(pady=2)
        
        #Settings Tab 3
        settings_menu_download_center_Frame = self.menu_FRAME_SET(tab3)
        settings_menu_download_center_Frame.grid(row=0)  
        
        download_center_title_Label = self.menu_title_LABEL_SET(settings_menu_download_center_Frame, APPLICATION_DOWNLOAD_CENTER_TEXT)
        download_center_title_Label.grid(padx=20,pady=MENU_PADDING_2)

        select_download_Label = self.menu_sub_LABEL_SET(settings_menu_download_center_Frame, SELECT_DOWNLOAD_TEXT)
        select_download_Label.grid(pady=MENU_PADDING_2)
        
        self.model_download_vr_Button = ttk.Radiobutton(settings_menu_download_center_Frame, text='VR Arch', width=8, variable=self.select_download_var, value='VR Arc', command=lambda:self.download_list_state())
        self.model_download_vr_Button.grid(pady=MENU_PADDING_1)
        self.model_download_vr_Option = ComboBoxMenu(settings_menu_download_center_Frame, textvariable=self.model_download_vr_var, width=READ_ONLY_COMBO_WIDTH)
        self.model_download_vr_Option.grid(pady=MENU_PADDING_1)
        
        self.model_download_mdx_Button = ttk.Radiobutton(settings_menu_download_center_Frame, text='MDX-Net', width=8, variable=self.select_download_var, value='MDX-Net', command=lambda:self.download_list_state())
        self.model_download_mdx_Button.grid(pady=MENU_PADDING_1)
        self.model_download_mdx_Option = ComboBoxMenu(settings_menu_download_center_Frame, textvariable=self.model_download_mdx_var, width=READ_ONLY_COMBO_WIDTH)
        self.model_download_mdx_Option.grid(pady=MENU_PADDING_1)

        self.model_download_demucs_Button = ttk.Radiobutton(settings_menu_download_center_Frame, text='Demucs', width=8, variable=self.select_download_var, value='Demucs', command=lambda:self.download_list_state())
        self.model_download_demucs_Button.grid(pady=MENU_PADDING_1)
        self.model_download_demucs_Option = ComboBoxMenu(settings_menu_download_center_Frame, textvariable=self.model_download_demucs_var, width=READ_ONLY_COMBO_WIDTH)
        self.model_download_demucs_Option.grid(pady=MENU_PADDING_1)
        
        self.download_Button = ttk.Button(settings_menu_download_center_Frame, image=self.download_img, command=lambda:self.download_item())#, command=download_model)
        self.download_Button.grid(pady=MENU_PADDING_1)
        
        self.download_progress_info_Label = tk.Label(settings_menu_download_center_Frame, textvariable=self.download_progress_info_var, font=(MAIN_FONT_NAME, f"{FONT_SIZE_2}"), foreground=FG_COLOR, borderwidth=0)
        self.download_progress_info_Label.grid(pady=MENU_PADDING_1)
        
        self.download_progress_percent_Label = tk.Label(settings_menu_download_center_Frame, textvariable=self.download_progress_percent_var, font=(MAIN_FONT_NAME, f"{FONT_SIZE_2}"), wraplength=350, foreground=FG_COLOR)
        self.download_progress_percent_Label.grid(pady=MENU_PADDING_1)
        
        self.download_progress_bar_Progressbar = ttk.Progressbar(settings_menu_download_center_Frame, variable=self.download_progress_bar_var)
        self.download_progress_bar_Progressbar.grid(pady=MENU_PADDING_1)
        
        self.stop_download_Button = ttk.Button(settings_menu_download_center_Frame, textvariable=self.download_stop_var, width=15, command=lambda:self.download_post_action(DOWNLOAD_STOPPED))
        self.stop_download_Button.grid(pady=MENU_PADDING_1)
        self.stop_download_Button_DISABLE = lambda:(self.download_stop_var.set(""), self.stop_download_Button.configure(state=tk.DISABLED))
        self.stop_download_Button_ENABLE = lambda:(self.download_stop_var.set(STOP_DOWNLOAD_TEXT), self.stop_download_Button.configure(state=tk.NORMAL))

        self.refresh_list_Button = ttk.Button(settings_menu_download_center_Frame, text=REFRESH_LIST_TEXT, command=lambda:self.online_data_refresh(refresh_list_Button=True))#, command=refresh_list)
        self.refresh_list_Button.grid(pady=MENU_PADDING_1)
        
        self.download_key_Button = ttk.Button(settings_menu_download_center_Frame, image=self.key_img, command=lambda:self.pop_up_user_code_input())
        self.download_key_Button.grid(pady=MENU_PADDING_1)
                            
        self.manual_download_Button = ttk.Button(settings_menu_download_center_Frame, text=TRY_MANUAL_DOWNLOAD_TEXT, command=self.menu_manual_downloads)
        self.manual_download_Button.grid(pady=MENU_PADDING_1)

        self.download_center_Buttons = (self.model_download_vr_Button,
                                        self.model_download_mdx_Button,
                                        self.model_download_demucs_Button,
                                        self.download_Button,
                                        self.download_key_Button)
        
        self.download_lists = (self.model_download_vr_Option,
                               self.model_download_mdx_Option,
                               self.model_download_demucs_Option)
        
        self.download_list_vars = (self.model_download_vr_var,
                                   self.model_download_mdx_var,
                                   self.model_download_demucs_var)
        
        self.online_data_refresh()

        self.menu_placement(settings_menu, SETTINGS_GUIDE_TEXT, is_help_hints=True, close_function=lambda:close_window())

        if select_tab_2:
            tabControl.select(tab2)
            settings_menu.update_idletasks()
            
        if select_tab_3:
            tabControl.select(tab3)
            settings_menu.update_idletasks()

        def close_window():
            self.active_download_thread.terminate() if self.thread_check(self.active_download_thread) else None
            self.is_menu_settings_open = False
            self.select_download_var.set('')
            settings_menu.destroy()

        #self.update_checkbox_text()
        settings_menu.protocol("WM_DELETE_WINDOW", close_window)

    def menu_advanced_vr_options(self):#**
        self.advanced_menus().menu_advanced_vr_options()

    def menu_advanced_demucs_options(self):#**
        self.advanced_menus().menu_advanced_demucs_options()
        
    def menu_advanced_mdx_options(self):#**
        self.advanced_menus().menu_advanced_mdx_options()

    def menu_advanced_ensemble_options(self):#**
        self.advanced_menus().menu_advanced_ensemble_options()

    def menu_advanced_align_options(self):#**
        self.advanced_menus().menu_advanced_align_options()
 
    def menu_help(self):#**
        self.advanced_menus().menu_help()

    def menu_error_log(self):#
        """Open Error Log"""

        self.is_confirm_error_var.set(False)
        
        copied_var = tk.StringVar(value='')
        error_log_screen = tk.Toplevel()
        
        self.is_open_menu_error_log.set(True)
        self.menu_error_log_close_window = lambda:(self.is_open_menu_error_log.set(False), error_log_screen.destroy())
        error_log_screen.protocol("WM_DELETE_WINDOW", self.menu_error_log_close_window)
        
        error_log_frame = self.menu_FRAME_SET(error_log_screen)
        error_log_frame.grid(row=0)  
        
        error_consol_title_Label = self.menu_title_LABEL_SET(error_log_frame, ERROR_CONSOLE_TEXT)
        error_consol_title_Label.grid(row=1,column=0,padx=20,pady=MENU_PADDING_2)
        
        error_details_Text = tk.Text(error_log_frame, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), fg="#D37B7B", bg="black", width=110, wrap=tk.WORD, borderwidth=0)
        error_details_Text.grid(row=2,column=0,padx=0,pady=0)
        error_details_Text.insert("insert", self.error_log_var.get())
        error_details_Text.bind(right_click_button, lambda e:self.right_click_menu_popup(e, text_box=True))
        self.current_text_box = error_details_Text
        error_details_Text_scroll = ttk.Scrollbar(error_log_frame, orient=tk.VERTICAL)
        error_details_Text.config(yscrollcommand=error_details_Text_scroll.set)
        error_details_Text_scroll.configure(command=error_details_Text.yview)
        error_details_Text.grid(row=2,sticky=tk.W)
        error_details_Text_scroll.grid(row=2, column=1, sticky=tk.NS)

        copy_text_Label = tk.Label(error_log_frame, textvariable=copied_var, font=(MAIN_FONT_NAME,  f"{FONT_SIZE_0}"), justify="center", fg="#f4f4f4")
        copy_text_Label.grid(padx=20,pady=0)
        
        copy_text_Button = ttk.Button(error_log_frame, text=COPY_ALL_TEXT_TEXT, width=14, command=lambda:(pyperclip.copy(error_details_Text.get(1.0, tk.END+"-1c")), copied_var.set('Copied!')))
        copy_text_Button.grid(padx=20,pady=MENU_PADDING_1)
        
        report_issue_Button = ttk.Button(error_log_frame, text=REPORT_ISSUE_TEXT, width=14, command=lambda:webbrowser.open_new_tab(ISSUE_LINK))
        report_issue_Button.grid(padx=20,pady=MENU_PADDING_1)

        error_log_return_Button = ttk.Button(error_log_frame, text=BACK_TO_MAIN_MENU, command=lambda:(self.menu_error_log_close_window(), self.menu_settings()))
        error_log_return_Button.grid(padx=20,pady=MENU_PADDING_1)
        
        error_log_close_Button = ttk.Button(error_log_frame, text=CLOSE_WINDOW, command=lambda:self.menu_error_log_close_window())
        error_log_close_Button.grid(padx=20,pady=MENU_PADDING_1)
        
        self.menu_placement(error_log_screen, UVR_ERROR_LOG_TEXT)

    def menu_secondary_model(self, tab, ai_network_vars: dict):
        
        #Settings Tab 1
        secondary_model_Frame = self.menu_FRAME_SET(tab)
        secondary_model_Frame.grid(row=0)  
        
        settings_title_Label = self.menu_title_LABEL_SET(secondary_model_Frame, SECONDARY_MODEL_TEXT)
        settings_title_Label.grid(row=0,column=0,padx=0,pady=MENU_PADDING_3)
        
        voc_inst_list = self.model_list(VOCAL_STEM, INST_STEM, is_dry_check=True)
        other_list = self.model_list(OTHER_STEM, NO_OTHER_STEM, is_dry_check=True)
        bass_list = self.model_list(BASS_STEM, NO_BASS_STEM, is_dry_check=True)
        drum_list = self.model_list(DRUM_STEM, NO_DRUM_STEM, is_dry_check=True)
        
        voc_inst_secondary_model_var = ai_network_vars["voc_inst_secondary_model"]
        other_secondary_model_var = ai_network_vars["other_secondary_model"]
        bass_secondary_model_var = ai_network_vars["bass_secondary_model"]
        drums_secondary_model_var = ai_network_vars["drums_secondary_model"]
        voc_inst_secondary_model_scale_var = ai_network_vars['voc_inst_secondary_model_scale']
        other_secondary_model_scale_var = ai_network_vars['other_secondary_model_scale']
        bass_secondary_model_scale_var = ai_network_vars['bass_secondary_model_scale']
        drums_secondary_model_scale_var = ai_network_vars['drums_secondary_model_scale']
        is_secondary_model_activate_var = ai_network_vars["is_secondary_model_activate"]
        
        change_state_lambda = lambda:change_state(tk.NORMAL if is_secondary_model_activate_var.get() else tk.DISABLED)
        init_convert_to_percentage = lambda raw_value:f"{int(float(raw_value)*100)}%"
        
        voc_inst_secondary_model_scale_LABEL_var = tk.StringVar(value=init_convert_to_percentage(voc_inst_secondary_model_scale_var.get()))
        other_secondary_model_scale_LABEL_var = tk.StringVar(value=init_convert_to_percentage(other_secondary_model_scale_var.get()))
        bass_secondary_model_scale_LABEL_var = tk.StringVar(value=init_convert_to_percentage(bass_secondary_model_scale_var.get()))
        drums_secondary_model_scale_LABEL_var = tk.StringVar(value=init_convert_to_percentage(drums_secondary_model_scale_var.get()))

        def change_state(change_state):
            for child_widget in secondary_model_Frame.winfo_children():
                if type(child_widget) is ComboBoxMenu:
                    change_state = READ_ONLY if change_state == tk.NORMAL else change_state
                    child_widget.configure(state=change_state)
                elif type(child_widget) is ttk.Scale:
                    child_widget.configure(state=change_state)
        
        def convert_to_percentage(raw_value, scale_var: tk.StringVar, label_var: tk.StringVar):
            raw_value = '%0.2f' % float(raw_value)
            scale_var.set(raw_value)
            label_var.set(f"{int(float(raw_value)*100)}%")

        def build_widgets(stem_pair: str, model_list: list, option_var: tk.StringVar, label_var: tk.StringVar, scale_var: tk.DoubleVar):
            model_list.insert(0, NO_MODEL)
            secondary_model_Label = self.menu_sub_LABEL_SET(secondary_model_Frame, f'{stem_pair}', font_size=FONT_SIZE_3)
            secondary_model_Label.grid(pady=MENU_PADDING_1)
            secondary_model_Option = ComboBoxMenu(secondary_model_Frame, textvariable=option_var, values=model_list, dropdown_name=stem_pair, offset=310, width=READ_ONLY_COMBO_WIDTH)
            secondary_model_Option.grid(pady=MENU_PADDING_1)
            secondary_scale_info_Label = tk.Label(secondary_model_Frame, textvariable=label_var, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground=FG_COLOR)
            secondary_scale_info_Label.grid(pady=0)   
            secondary_model_scale_Option = ttk.Scale(secondary_model_Frame, variable=scale_var, from_=0.01, to=0.99, command=lambda s:convert_to_percentage(s, scale_var, label_var), orient='horizontal')
            secondary_model_scale_Option.grid(pady=2)
            self.help_hints(secondary_model_Label, text=SECONDARY_MODEL_HELP)
            self.help_hints(secondary_scale_info_Label, text=SECONDARY_MODEL_SCALE_HELP)

        build_widgets(stem_pair=VOCAL_PAIR,
                      model_list=voc_inst_list,
                      option_var=voc_inst_secondary_model_var,
                      label_var=voc_inst_secondary_model_scale_LABEL_var,
                      scale_var=voc_inst_secondary_model_scale_var)
        
        build_widgets(stem_pair=OTHER_PAIR,
                      model_list=other_list,
                      option_var=other_secondary_model_var,
                      label_var=other_secondary_model_scale_LABEL_var,
                      scale_var=other_secondary_model_scale_var)
        
        build_widgets(stem_pair=BASS_PAIR,
                      model_list=bass_list,
                      option_var=bass_secondary_model_var,
                      label_var=bass_secondary_model_scale_LABEL_var,
                      scale_var=bass_secondary_model_scale_var)
        
        build_widgets(stem_pair=DRUM_PAIR,
                      model_list=drum_list,
                      option_var=drums_secondary_model_var,
                      label_var=drums_secondary_model_scale_LABEL_var,
                      scale_var=drums_secondary_model_scale_var)
     
        is_secondary_model_activate_Option = ttk.Checkbutton(secondary_model_Frame, text=ACTIVATE_SECONDARY_MODEL_TEXT, variable=is_secondary_model_activate_var, command=change_state_lambda) 
        is_secondary_model_activate_Option.grid(row=21,pady=MENU_PADDING_1)
        self.help_hints(is_secondary_model_activate_Option, text=SECONDARY_MODEL_ACTIVATE_HELP)
        
        change_state_lambda()
        
        self.change_state_lambda = change_state_lambda
        
    def menu_preproc_model(self, tab):
        
        preproc_model_Frame = self.menu_FRAME_SET(tab)
        preproc_model_Frame.grid(row=0)  

        demucs_pre_proc_model_title_Label = self.menu_title_LABEL_SET(preproc_model_Frame, PREPROCESS_MODEL_CHOOSE_TEXT)
        demucs_pre_proc_model_title_Label.grid(pady=MENU_PADDING_3)
        
        pre_proc_list = self.model_list(VOCAL_STEM, INST_STEM, is_dry_check=True, is_no_demucs=True)
        pre_proc_list.insert(0, NO_MODEL)
        
        enable_pre_proc_model = lambda:(is_demucs_pre_proc_model_inst_mix_Option.configure(state=tk.NORMAL), demucs_pre_proc_model_Option.configure(state=READ_ONLY))
        disable_pre_proc_model = lambda:(is_demucs_pre_proc_model_inst_mix_Option.configure(state=tk.DISABLED), demucs_pre_proc_model_Option.configure(state=tk.DISABLED), self.is_demucs_pre_proc_model_inst_mix_var.set(False))
        pre_proc_model_toggle = lambda:enable_pre_proc_model() if self.is_demucs_pre_proc_model_activate_var.get() else disable_pre_proc_model()
        
        demucs_pre_proc_model_Label = self.menu_sub_LABEL_SET(preproc_model_Frame, SELECT_MODEL_TEXT, font_size=FONT_SIZE_3)
        demucs_pre_proc_model_Label.grid()
        demucs_pre_proc_model_Option = ComboBoxMenu(preproc_model_Frame, textvariable=self.demucs_pre_proc_model_var, values=pre_proc_list, dropdown_name='demucspre', offset=310, width=READ_ONLY_COMBO_WIDTH)
        demucs_pre_proc_model_Option.grid(pady=MENU_PADDING_2)

        is_demucs_pre_proc_model_inst_mix_Option = ttk.Checkbutton(preproc_model_Frame, text='Save Instrumental Mixture', width=DEMUCS_PRE_CHECKBOXS_WIDTH, variable=self.is_demucs_pre_proc_model_inst_mix_var) 
        is_demucs_pre_proc_model_inst_mix_Option.grid()
        self.help_hints(is_demucs_pre_proc_model_inst_mix_Option, text=PRE_PROC_MODEL_INST_MIX_HELP)
        
        is_demucs_pre_proc_model_activate_Option = ttk.Checkbutton(preproc_model_Frame, text=ACTIVATE_PRE_PROCESS_MODEL_TEXT, width=DEMUCS_PRE_CHECKBOXS_WIDTH, variable=self.is_demucs_pre_proc_model_activate_var, command=pre_proc_model_toggle) 
        is_demucs_pre_proc_model_activate_Option.grid()
        self.help_hints(is_demucs_pre_proc_model_activate_Option, text=PRE_PROC_MODEL_ACTIVATE_HELP)
        
        pre_proc_model_toggle()
        
    def menu_manual_downloads(self):
        self.download_menus().menu_manual_downloads()
        
    def invalid_tooltip(self, widget, pattern=None):
        tooltip = ToolTip(widget)
        invalid_message = lambda:tooltip.showtip(INVALID_INPUT_E, True)
        
        def invalid_message_():
            tooltip.showtip(INVALID_INPUT_E, True)
        
        def validation(value):
            if re.fullmatch(modified_pattern, value) is None:
                return False
            else:
                return True
        
        if not pattern:
            pattern = r'^[a-zA-Z0-9 -]{0,25}$'

        modified_pattern = f"({pattern}|)"

        widget.configure(
            validate='key', 
            validatecommand=(self.register(validation), '%P'),
            invalidcommand=(self.register(invalid_message))
        )
        
        return invalid_message_
        
    def pop_up_save_current_settings(self):
        """Save current application settings as..."""
        
        settings_save = tk.Toplevel(root)
        
        settings_save_var = tk.StringVar(value='')

        settings_save_Frame = self.menu_FRAME_SET(settings_save)
        settings_save_Frame.grid(row=1)  

        save_func = lambda:(self.pop_up_save_current_settings_sub_json_dump(settings_save_var.get()), settings_save.destroy())
        validation = lambda value:False if re.fullmatch(REG_SAVE_INPUT, value) is None else True

        settings_save_title = self.menu_title_LABEL_SET(settings_save_Frame, SAVE_CURRENT_SETTINGS_TEXT)
        settings_save_title.grid()
        
        settings_save_name_Label = self.menu_sub_LABEL_SET(settings_save_Frame, NAME_SETTINGS_TEXT)
        settings_save_name_Label.grid(pady=MENU_PADDING_1)
        settings_save_name_Entry = ttk.Entry(settings_save_Frame, textvariable=settings_save_var, justify='center', width=25)
        settings_save_name_Entry.grid(pady=MENU_PADDING_1)
        invalid_message = self.invalid_tooltip(settings_save_name_Entry)
        settings_save_name_Entry.bind(right_click_button, self.right_click_menu_popup)
        self.current_text_box = settings_save_name_Entry
        settings_save_name_Entry.focus_set()
        
        self.spacer_label(settings_save_Frame)
        
        entry_rules_Label = tk.Label(settings_save_Frame, text=ENSEMBLE_INPUT_RULE, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground='#868687', justify="left")
        entry_rules_Label.grid()     
        
        settings_save_Button = ttk.Button(settings_save_Frame, text=SAVE_TEXT, command=lambda:save_func() if validation(settings_save_var.get()) else invalid_message())
        settings_save_Button.grid(pady=MENU_PADDING_1)
        
        stop_process_Button = ttk.Button(settings_save_Frame, text=CANCEL_TEXT, command=lambda:settings_save.destroy())
        stop_process_Button.grid(pady=MENU_PADDING_1)
            
        self.menu_placement(settings_save, SAVE_CURRENT_SETTINGS_TEXT, pop_up=True)

    def pop_up_save_current_settings_sub_json_dump(self, settings_save_name: str):
        """Dumps current application settings to a json named after user input"""
        
        if settings_save_name:
            self.save_current_settings_var.set(settings_save_name)
            settings_save_name = settings_save_name.replace(" ", "_")
            current_settings = self.save_values(app_close=False)
            
            saved_data_dump = json.dumps(current_settings, indent=4)
            with open(os.path.join(SETTINGS_CACHE_DIR, f'{settings_save_name}.json'), "w") as outfile:
                outfile.write(saved_data_dump)

    def pop_up_update_confirmation(self):
        self.download_menus().pop_up_update_confirmation()

    def pop_up_user_code_input(self):
        self.download_menus().pop_up_user_code_input()

    def pop_up_change_model_defaults(self, top_window):
        """
        Change model defaults...
        """
        
        def message_box_(text, is_success_message):
            tooltip.hidetip()
            tooltip.showtip(text, True, is_success_message)
        
        def delete_entry():
            model_data = self.assemble_model_data(model=change_model_defaults_var.get(), arch_type=ENSEMBLE_CHECK, is_change_def=True, is_get_hash_dir_only=True)[0]
            hash_file = model_data.model_hash_dir
            if hash_file:
                if os.path.isfile(hash_file):
                    os.remove(hash_file)
                    message_box_("Defined Parameters Deleted", True)
                else:
                    message_box_("No Defined Parameters Found", False)
                    
                self.update_checkbox_text()
                
        def change_default():
            model_data = self.assemble_model_data(model=change_model_defaults_var.get(), arch_type=ENSEMBLE_CHECK, is_change_def=True)[0]
            if model_data.model_status:
                message_box_("Model Parameters Changed", True)
                self.update_checkbox_text()

        change_model_defaults = tk.Toplevel(root)
        change_model_defaults_var = tk.StringVar(value=NO_MODEL)

        default_change_model_list = list(self.default_change_model_list)
        default_change_model_list.insert(0, NO_MODEL)

        change_model_defaults_Frame = self.menu_FRAME_SET(change_model_defaults)
        change_model_defaults_Frame.grid(row=1)  

        change_model_defaults_title = self.menu_title_LABEL_SET(change_model_defaults_Frame, CHANGE_MODEL_DEFAULT_TEXT)
        change_model_defaults_title.grid()
        
        model_param_Label = self.menu_sub_LABEL_SET(change_model_defaults_Frame, SELECT_MODEL_TEXT)
        model_param_Label.grid(pady=MENU_PADDING_1)
        model_param_Option = ComboBoxMenu(change_model_defaults_Frame, dropdown_name='changemodeldefault', textvariable=change_model_defaults_var, values=default_change_model_list, offset=310, width=READ_ONLY_COMBO_WIDTH)
        model_param_Option.grid(pady=MENU_PADDING_1)
        tooltip = ToolTip(model_param_Option)
        
        self.spacer_label(change_model_defaults_Frame)

        change_params_Button = ttk.Button(change_model_defaults_Frame, text=CHANGE_PARAMETERS_TEXT, command=change_default, width=20)
        change_params_Button.grid(pady=MENU_PADDING_1)
        
        delete_params_Button = ttk.Button(change_model_defaults_Frame, text=DELETE_PARAMETERS_TEXT, command=delete_entry, width=20)
        delete_params_Button.grid(pady=MENU_PADDING_1)
        
        cancel_Button = ttk.Button(change_model_defaults_Frame, text=CANCEL_TEXT, command=lambda:change_model_defaults.destroy())
        cancel_Button.grid(pady=MENU_PADDING_1)
            
        self.menu_placement(change_model_defaults, CHANGE_MODEL_DEFAULT_TEXT, top_window=top_window)

    def pop_up_set_vocal_splitter(self, top_window):
        """
        Set vocal splitter
        """

        try:
            set_vocal_splitter = tk.Toplevel(root)

            model_list = self.assemble_model_data(arch_type=KARAOKEE_CHECK, is_dry_check=True)
            if not model_list:
                self.set_vocal_splitter_var.set(NO_MODEL)
            model_list.insert(0, NO_MODEL)

            enable_voc_split_model = lambda:(model_select_Option.configure(state=READ_ONLY), save_inst_Button.configure(state=tk.NORMAL))
            disable_voc_split_model = lambda:(model_select_Option.configure(state=tk.DISABLED), save_inst_Button.configure(state=tk.DISABLED), self.is_save_inst_set_vocal_splitter_var.set(False))
            voc_split_model_toggle = lambda:enable_voc_split_model() if self.is_set_vocal_splitter_var.get() else disable_voc_split_model()
            
            enable_deverb_opt = lambda:(deverb_vocals_Option.configure(state=READ_ONLY))
            disable_deverb_opt= lambda:(deverb_vocals_Option.configure(state=tk.DISABLED))
            deverb_opt_toggle = lambda:enable_deverb_opt() if self.is_deverb_vocals_var.get() else disable_deverb_opt()

            set_vocal_splitter_Frame = self.menu_FRAME_SET(set_vocal_splitter)
            set_vocal_splitter_Frame.grid(row=1)  

            set_vocal_splitter_title = self.menu_title_LABEL_SET(set_vocal_splitter_Frame, VOCAL_SPLIT_MODE_OPTIONS_TEXT)
            set_vocal_splitter_title.grid(pady=MENU_PADDING_2)
            
            model_select_Label = self.menu_sub_LABEL_SET(set_vocal_splitter_Frame, SELECT_MODEL_TEXT)
            model_select_Label.grid(pady=MENU_PADDING_1)
            model_select_Option = ComboBoxMenu(set_vocal_splitter_Frame, dropdown_name='setvocalsplit', textvariable=self.set_vocal_splitter_var, values=model_list, offset=310, width=READ_ONLY_COMBO_WIDTH)
            model_select_Option.grid(pady=7)
            self.help_hints(model_select_Option, text=VOC_SPLIT_MODEL_SELECT_HELP)#
            
            save_inst_Button = ttk.Checkbutton(set_vocal_splitter_Frame, text=SAVE_SPLIT_VOCAL_INSTRUMENTALS_TEXT, variable=self.is_save_inst_set_vocal_splitter_var, width=SET_VOC_SPLIT_CHECK_WIDTH, command=voc_split_model_toggle)
            save_inst_Button.grid()#
            self.help_hints(save_inst_Button, text=IS_VOC_SPLIT_INST_SAVE_SELECT_HELP)#
            
            change_params_Button = ttk.Checkbutton(set_vocal_splitter_Frame, text=ENABLE_VOCAL_SPLIT_MODE_TEXT, variable=self.is_set_vocal_splitter_var, width=SET_VOC_SPLIT_CHECK_WIDTH, command=voc_split_model_toggle)
            change_params_Button.grid()#
            self.help_hints(change_params_Button, text=IS_VOC_SPLIT_MODEL_SELECT_HELP)#
            
            set_vocal_splitter_title = self.menu_title_LABEL_SET(set_vocal_splitter_Frame, VOCAL_DEVERB_OPTIONS_TEXT)
            set_vocal_splitter_title.grid(pady=MENU_PADDING_2)
            
            deverb_vocals_Label = self.menu_sub_LABEL_SET(set_vocal_splitter_Frame, 'Select Vocal Type to Deverb')
            deverb_vocals_Label.grid(pady=MENU_PADDING_1)
            deverb_vocals_Option = ComboBoxMenu(set_vocal_splitter_Frame, dropdown_name='setvocaldeverb', textvariable=self.deverb_vocal_opt_var, values=list(DEVERB_MAPPER.keys()), width=23)
            deverb_vocals_Option.grid(pady=7)
            self.help_hints(deverb_vocals_Option, text=IS_DEVERB_OPT_HELP)#
            
            is_deverb_vocals_Option = ttk.Checkbutton(set_vocal_splitter_Frame, text=DEVERB_VOCALS_TEXT, width=15 if is_windows else 11, variable=self.is_deverb_vocals_var, command=deverb_opt_toggle) 
            is_deverb_vocals_Option.grid(pady=0)
            self.help_hints(is_deverb_vocals_Option, text=IS_DEVERB_VOC_HELP)#
            
            if not os.path.isfile(DEVERBER_MODEL_PATH):
                self.is_deverb_vocals_var.set(False)
                is_deverb_vocals_Option.configure(state=tk.DISABLED)
                disable_deverb_opt()
            
            cancel_Button = ttk.Button(set_vocal_splitter_Frame, text=CLOSE_WINDOW, command=lambda:set_vocal_splitter.destroy(), width=16)
            cancel_Button.grid(pady=MENU_PADDING_3)
                
            voc_split_model_toggle()
            deverb_opt_toggle()
                
            self.menu_placement(set_vocal_splitter, VOCAL_SPLIT_OPTIONS_TEXT, top_window=top_window, pop_up=True)
        except Exception as e:
            error_name = f'{type(e).__name__}'
            traceback_text = ''.join(traceback.format_tb(e.__traceback__))
            message = f'{error_name}: "{e}"\n{traceback_text}"'
            self.error_log_var.set(message)

    def pop_up_mdx_model(self, mdx_model_hash, model_path):
        """Opens MDX-Net model settings"""
    
        is_compatible_model = True
        is_ckpt = False
        primary_stem = VOCAL_STEM
        
        try:
            if model_path.endswith(ONNX):
                model = onnx.load(model_path)
                model_shapes = [[d.dim_value for d in _input.type.tensor_type.shape.dim] for _input in model.graph.input][0]
                dim_f = model_shapes[2]
                dim_t = int(math.log(model_shapes[3], 2))
                n_fft = '6144'
                
            if model_path.endswith(CKPT):
                is_ckpt = True
                model_params = torch.load(model_path, map_location=lambda storage, loc: storage)
                model_params = model_params['hyper_parameters']
                dim_f = model_params['dim_f']
                dim_t = int(math.log(model_params['dim_t'], 2))
                n_fft = model_params['n_fft']
                
                for stem in STEM_SET_MENU:
                    if model_params['target_name'] == stem.lower():
                        primary_stem = INST_STEM if model_params['target_name'] == OTHER_STEM.lower() else stem
                
        except Exception as e:
            error_name = f'{type(e).__name__}'
            traceback_text = ''.join(traceback.format_tb(e.__traceback__))
            message = f'{error_name}: "{e}"\n{traceback_text}"'
            #self.error_log_var.set(message)
            is_compatible_model = False
            if is_ckpt:
                self.pop_up_mdx_c_param(mdx_model_hash)
            else:
                dim_f = 0
                dim_t = 0
                self.error_dialoge(INVALID_ONNX_MODEL_ERROR)
                self.error_log_var.set("{}".format(error_text('MDX-Net Model Settings', e)))
                self.mdx_model_params = None
            
        if is_compatible_model:
            mdx_model_set = tk.Toplevel(root)
            mdx_n_fft_scale_set_var = tk.StringVar(value=n_fft)
            mdx_dim_f_set_var = tk.StringVar(value=dim_f)
            mdx_dim_t_set_var = tk.StringVar(value=dim_t)
            primary_stem_var = tk.StringVar(value=primary_stem)
            mdx_compensate_var = tk.StringVar(value=1.035)
            
            balance_value_var = tk.StringVar(value=0)
            is_kara_model_var = tk.BooleanVar(value=False)
            is_bv_model_var = tk.BooleanVar(value=False)
                
            def toggle_kara():
                if is_kara_model_var.get():
                    is_bv_model_var.set(False)
                    balance_value_Option.configure(state=tk.DISABLED)
                    
            def toggle_bv():
                if is_bv_model_var.get():
                    is_kara_model_var.set(False)
                    balance_value_Option.configure(state=READ_ONLY)
                else:
                    balance_value_Option.configure(state=tk.DISABLED)

            def opt_menu_selection(selection):
                if not selection in [VOCAL_STEM, INST_STEM]:
                    balance_value_Option.configure(state=tk.DISABLED)
                    is_kara_model_Option.configure(state=tk.DISABLED)
                    is_bv_model_Option.configure(state=tk.DISABLED)
                    is_kara_model_var.set(False)
                    is_bv_model_var.set(False)
                    balance_value_var.set(0)
                else:
                    is_kara_model_Option.configure(state=tk.NORMAL)
                    is_bv_model_Option.configure(state=tk.NORMAL)
                
            mdx_model_set_Frame = self.menu_FRAME_SET(mdx_model_set)
            mdx_model_set_Frame.grid(row=2)  
            
            mdx_model_set_title = self.menu_title_LABEL_SET(mdx_model_set_Frame, SPECIFY_MDX_NET_MODEL_PARAMETERS_TEXT)
            mdx_model_set_title.grid(pady=MENU_PADDING_3)
                    
            set_stem_name_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, PRIMARY_STEM_TEXT)
            set_stem_name_Label.grid(pady=MENU_PADDING_1)
            set_stem_name_Option = ttk.OptionMenu(mdx_model_set_Frame, primary_stem_var, None, *STEM_SET_MENU, command=opt_menu_selection)
            set_stem_name_Option.configure(width=15)
            set_stem_name_Option.grid(pady=MENU_PADDING_1)
            set_stem_name_Option['menu'].insert_separator(len(STEM_SET_MENU))
            set_stem_name_Option['menu'].add_radiobutton(label=INPUT_STEM_NAME, command=tk._setit(primary_stem_var, INPUT_STEM_NAME, lambda e:self.pop_up_input_stem_name(primary_stem_var, mdx_model_set)))
            self.help_hints(set_stem_name_Label, text=SET_STEM_NAME_HELP)

            is_kara_model_Option = ttk.Checkbutton(mdx_model_set_Frame, text=KARAOKE_MODEL_TEXT, width=SET_MENUS_CHECK_WIDTH, variable=is_kara_model_var, command=toggle_kara) 
            is_kara_model_Option.grid(pady=0)

            is_bv_model_Option = ttk.Checkbutton(mdx_model_set_Frame, text=BV_MODEL_TEXT, width=SET_MENUS_CHECK_WIDTH, variable=is_bv_model_var, command=toggle_bv) 
            is_bv_model_Option.grid(pady=0)

            balance_value_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, BALANCE_VALUE_TEXT)
            balance_value_Label.grid(pady=MENU_PADDING_1)
            balance_value_Option = ComboBoxMenu(mdx_model_set_Frame, textvariable=balance_value_var, values=BALANCE_VALUES, width=COMBO_WIDTH)
            balance_value_Option.configure(state=tk.DISABLED)
            balance_value_Option.grid(pady=MENU_PADDING_1)
            #self.help_hints(balance_value_Label, text=balance_value_HELP)

            mdx_dim_t_set_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, 'Dim_t')
            mdx_dim_t_set_Label.grid(pady=MENU_PADDING_1)
            mdx_dim_f_set_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, MDX_MENU_WAR_TEXT)
            mdx_dim_f_set_Label.grid(pady=MENU_PADDING_1)
            mdx_dim_t_set_Option = ComboBoxEditableMenu(mdx_model_set_Frame, values=('7', '8'), textvariable=mdx_dim_t_set_var, pattern=REG_SHIFTS, default=mdx_dim_t_set_var.get(), width=COMBO_WIDTH, is_stay_disabled=is_ckpt)
            mdx_dim_t_set_Option.grid(pady=MENU_PADDING_1)
            self.help_hints(mdx_dim_t_set_Label, text=MDX_DIM_T_SET_HELP)
            
            mdx_dim_f_set_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, 'Dim_f')
            mdx_dim_f_set_Label.grid(pady=MENU_PADDING_1)
            mdx_dim_f_set_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, MDX_MENU_WAR_TEXT)
            mdx_dim_f_set_Label.grid(pady=MENU_PADDING_1)
            mdx_dim_f_set_Option = ComboBoxEditableMenu(mdx_model_set_Frame, values=(MDX_POP_DIMF), textvariable=mdx_dim_f_set_var, pattern=REG_SHIFTS, default=mdx_dim_f_set_var.get(), width=COMBO_WIDTH, is_stay_disabled=is_ckpt)
            mdx_dim_f_set_Option.grid(pady=MENU_PADDING_1)
            self.help_hints(mdx_dim_f_set_Label, text=MDX_DIM_F_SET_HELP)

            mdx_n_fft_scale_set_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, 'N_FFT Scale')
            mdx_n_fft_scale_set_Label.grid(pady=MENU_PADDING_1)
            mdx_n_fft_scale_set_Option = ComboBoxEditableMenu(mdx_model_set_Frame, values=(MDX_POP_NFFT), textvariable=mdx_n_fft_scale_set_var, pattern=REG_SHIFTS, default=mdx_n_fft_scale_set_var.get(), width=COMBO_WIDTH, is_stay_disabled=is_ckpt)
            mdx_n_fft_scale_set_Option.grid(pady=MENU_PADDING_1)
            self.help_hints(mdx_n_fft_scale_set_Label, text=MDX_N_FFT_SCALE_SET_HELP)
            
            mdx_compensate_Label = self.menu_sub_LABEL_SET(mdx_model_set_Frame, VOLUME_COMPENSATION_TEXT)
            mdx_compensate_Label.grid(pady=MENU_PADDING_1)
            mdx_compensate_Entry = ComboBoxEditableMenu(mdx_model_set_Frame, values=('1.035', '1.08'), textvariable=mdx_compensate_var, pattern=REG_VOL_COMP, default=mdx_compensate_var.get(), width=COMBO_WIDTH)
            mdx_compensate_Entry.grid(pady=MENU_PADDING_1)
            self.help_hints(mdx_compensate_Label, text=POPUP_COMPENSATE_HELP)

            mdx_param_set_Button = ttk.Button(mdx_model_set_Frame, text=CONFIRM_TEXT, command=lambda:pull_data())
            mdx_param_set_Button.grid(pady=MENU_PADDING_2)
            
            stop_process_Button = ttk.Button(mdx_model_set_Frame, text=CANCEL_TEXT, command=lambda:cancel())
            stop_process_Button.grid(pady=0)
            
            if is_ckpt:
                mdx_dim_t_set_Option.configure(state=tk.DISABLED)
                mdx_dim_f_set_Option.configure(state=tk.DISABLED)
                mdx_n_fft_scale_set_Option.configure(state=tk.DISABLED)
            
            def pull_data():
                mdx_model_params = {
                    'compensate': float(mdx_compensate_var.get()),
                    'mdx_dim_f_set': int(mdx_dim_f_set_var.get()),
                    'mdx_dim_t_set': int(mdx_dim_t_set_var.get()),
                    'mdx_n_fft_scale_set': int(mdx_n_fft_scale_set_var.get()),
                    'primary_stem': primary_stem_var.get(),
                    IS_KARAOKEE: bool(is_kara_model_var.get()),
                    IS_BV_MODEL: bool(is_bv_model_var.get()),
                    IS_BV_MODEL_REBAL: float(balance_value_var.get())
                    }
                
                self.pop_up_mdx_model_sub_json_dump(mdx_model_params, mdx_model_hash)
                mdx_model_set.destroy()

            def cancel():
                mdx_model_set.destroy()
                
            mdx_model_set.protocol("WM_DELETE_WINDOW", cancel)
   
            frame_list = [mdx_model_set_Frame]
            opt_menu_selection(primary_stem_var.get())
            self.menu_placement(mdx_model_set, SPECIFY_PARAMETERS_TEXT, pop_up=False if is_macos else True, frame_list=frame_list)
                        
    def pop_up_mdx_model_sub_json_dump(self, mdx_model_params, mdx_model_hash):
        """Dumps current selected MDX-Net model settings to a json named after model hash"""
        
        self.mdx_model_params = mdx_model_params

        mdx_model_params_dump = json.dumps(mdx_model_params, indent=4)
        with open(os.path.join(MDX_HASH_DIR, f'{mdx_model_hash}.json'), "w") as outfile:
            outfile.write(mdx_model_params_dump)
        
    def pop_up_mdx_c_param(self, mdx_model_hash):
        """Opens MDX-C param settings"""

        mdx_c_param_menu = tk.Toplevel()
        
        get_mdx_c_params = lambda dir, ext:tuple(os.path.splitext(x)[0] for x in os.listdir(dir) if x.endswith(ext))
        new_mdx_c_params = get_mdx_c_params(MDX_C_CONFIG_PATH, YAML)
        mdx_c_model_param_var = tk.StringVar(value=NONE_SELECTED)
        
        def pull_data():
            mdx_c_model_params = {
                'config_yaml': f"{mdx_c_model_param_var.get()}{YAML}"}
            
            if not mdx_c_model_param_var.get() == NONE_SELECTED:
                self.pop_up_mdx_model_sub_json_dump(mdx_c_model_params, mdx_model_hash)
                mdx_c_param_menu.destroy()
            else:
                self.mdx_model_params = None
        
        def cancel():
            self.mdx_model_params = None
            mdx_c_param_menu.destroy()
        
        mdx_c_param_Frame = self.menu_FRAME_SET(mdx_c_param_menu)
        mdx_c_param_Frame.grid(row=0)  
        
        mdx_c_param_title_title = self.menu_title_LABEL_SET(mdx_c_param_Frame, MDXNET_C_MODEL_PARAMETERS_TEXT, width=28)
        mdx_c_param_title_title.grid(row=0,column=0,padx=0,pady=0)
                
        mdx_c_model_param_Label = self.menu_sub_LABEL_SET(mdx_c_param_Frame, SELECT_MODEL_PARAM_TEXT)
        mdx_c_model_param_Label.grid(pady=MENU_PADDING_1)
        mdx_c_model_param_Option = ComboBoxMenu(mdx_c_param_Frame, textvariable=mdx_c_model_param_var, values=new_mdx_c_params, width=30)
        mdx_c_model_param_Option.grid(padx=20,pady=MENU_PADDING_1)
        self.help_hints(mdx_c_model_param_Label, text=VR_MODEL_PARAM_HELP)

        mdx_c_param_confrim_Button = ttk.Button(mdx_c_param_Frame, text=CONFIRM_TEXT, command=lambda:pull_data())
        mdx_c_param_confrim_Button.grid(pady=MENU_PADDING_1)
        
        mdx_c_param_cancel_Button = ttk.Button(mdx_c_param_Frame, text=CANCEL_TEXT, command=cancel)
        mdx_c_param_cancel_Button.grid(pady=MENU_PADDING_1)
        
        mdx_c_param_menu.protocol("WM_DELETE_WINDOW", cancel)
        
        self.menu_placement(mdx_c_param_menu, CHOOSE_MODEL_PARAM_TEXT, pop_up=True)
        
    def pop_up_vr_param(self, vr_model_hash):
        """Opens VR param settings"""

        vr_param_menu = tk.Toplevel()
        
        get_vr_params = lambda dir, ext:tuple(os.path.splitext(x)[0] for x in os.listdir(dir) if x.endswith(ext))
        new_vr_params = get_vr_params(VR_PARAM_DIR, JSON)
        vr_model_param_var = tk.StringVar(value=NONE_SELECTED)
        vr_model_stem_var = tk.StringVar(value='Vocals')
        vr_model_nout_var = tk.StringVar(value=32)
        vr_model_nout_lstm_var = tk.StringVar(value=128)
        is_new_vr_model_var = tk.BooleanVar(value=False)
        balance_value_var = tk.StringVar(value=0)
        is_kara_model_var = tk.BooleanVar(value=False)
        is_bv_model_var = tk.BooleanVar(value=False)
        
        enable_new_vr_op = lambda:(vr_model_nout_Option.configure(state=READ_ONLY), vr_model_nout_lstm_Option.configure(state=READ_ONLY))
        disable_new_vr_op = lambda:(vr_model_nout_Option.configure(state=tk.DISABLED), vr_model_nout_lstm_Option.configure(state=tk.DISABLED))
        vr_new_toggle = lambda:enable_new_vr_op() if is_new_vr_model_var.get() else disable_new_vr_op()
        
        def pull_data():
            if is_new_vr_model_var.get():
                vr_model_params = {
                    'vr_model_param': vr_model_param_var.get(),
                    'primary_stem': vr_model_stem_var.get(),
                    'nout': int(vr_model_nout_var.get()),
                    'nout_lstm': int(vr_model_nout_lstm_var.get()),
                    IS_KARAOKEE: bool(is_kara_model_var.get()),
                    IS_BV_MODEL: bool(is_bv_model_var.get()),
                    IS_BV_MODEL_REBAL: float(balance_value_var.get())
                    }
            else:
                vr_model_params = {
                    'vr_model_param': vr_model_param_var.get(),
                    'primary_stem': vr_model_stem_var.get(),
                    IS_KARAOKEE: bool(is_kara_model_var.get()),
                    IS_BV_MODEL: bool(is_bv_model_var.get()),
                    IS_BV_MODEL_REBAL: float(balance_value_var.get())}

            if not vr_model_param_var.get() == NONE_SELECTED:
                self.pop_up_vr_param_sub_json_dump(vr_model_params, vr_model_hash)
                vr_param_menu.destroy()
            else:
                self.vr_model_params = None
                self.error_dialoge(INVALID_PARAM_MODEL_ERROR)
                
        def cancel():
            self.vr_model_params = None
            vr_param_menu.destroy()
        
        def toggle_kara():
            if is_kara_model_var.get():
                is_bv_model_var.set(False)
                balance_value_Option.configure(state=tk.DISABLED)
                
        def toggle_bv():
            if is_bv_model_var.get():
                is_kara_model_var.set(False)
                balance_value_Option.configure(state=READ_ONLY)
            else:
                balance_value_Option.configure(state=tk.DISABLED)

        def opt_menu_selection(selection):
            if not selection in [VOCAL_STEM, INST_STEM]:
                balance_value_Option.configure(state=tk.DISABLED)
                is_kara_model_Option.configure(state=tk.DISABLED)
                is_bv_model_Option.configure(state=tk.DISABLED)
                is_kara_model_var.set(False)
                is_bv_model_var.set(False)
                balance_value_var.set(0)
            else:
                is_kara_model_Option.configure(state=tk.NORMAL)
                is_bv_model_Option.configure(state=tk.NORMAL)

        vr_param_Frame = self.menu_FRAME_SET(vr_param_menu)
        vr_param_Frame.grid(row=0, padx=20)  
            
        vr_param_title_title = self.menu_title_LABEL_SET(vr_param_Frame, SPECIFY_VR_MODEL_PARAMETERS_TEXT)
        vr_param_title_title.grid()
                
        vr_model_stem_Label = self.menu_sub_LABEL_SET(vr_param_Frame, PRIMARY_STEM_TEXT)
        vr_model_stem_Label.grid(pady=MENU_PADDING_1)    
        vr_model_stem_Option = ttk.OptionMenu(vr_param_Frame, vr_model_stem_var, None, *STEM_SET_MENU, command=opt_menu_selection)
        vr_model_stem_Option.configure(width=15)
        vr_model_stem_Option.grid(pady=MENU_PADDING_1)
        vr_model_stem_Option['menu'].insert_separator(len(STEM_SET_MENU))
        vr_model_stem_Option['menu'].add_radiobutton(label=INPUT_STEM_NAME, command=tk._setit(vr_model_stem_var, INPUT_STEM_NAME, lambda e:self.pop_up_input_stem_name(vr_model_stem_var, vr_param_menu)))
        self.help_hints(vr_model_stem_Label, text=SET_STEM_NAME_HELP)
                
        is_kara_model_Option = ttk.Checkbutton(vr_param_Frame, text=KARAOKE_MODEL_TEXT, width=SET_MENUS_CHECK_WIDTH, variable=is_kara_model_var, command=toggle_kara) 
        is_kara_model_Option.grid(pady=0)

        is_bv_model_Option = ttk.Checkbutton(vr_param_Frame, text=BV_MODEL_TEXT, width=SET_MENUS_CHECK_WIDTH, variable=is_bv_model_var, command=toggle_bv) 
        is_bv_model_Option.grid(pady=0)

        balance_value_Label = self.menu_sub_LABEL_SET(vr_param_Frame, BALANCE_VALUE_TEXT)
        balance_value_Label.grid(pady=MENU_PADDING_1)
        balance_value_Option = ComboBoxMenu(vr_param_Frame, textvariable=balance_value_var, values=BALANCE_VALUES, width=COMBO_WIDTH)
        balance_value_Option.configure(state=tk.DISABLED)
        balance_value_Option.grid(pady=MENU_PADDING_1)
                
        is_new_vr_model_Option = ttk.Checkbutton(vr_param_Frame, text=VR_51_MODEL_TEXT, width=SET_MENUS_CHECK_WIDTH, variable=is_new_vr_model_var, command=vr_new_toggle) 
        is_new_vr_model_Option.grid(pady=MENU_PADDING_1)
        
        vr_model_nout_Label = self.menu_sub_LABEL_SET(vr_param_Frame, 'Out Channels')
        vr_model_nout_Label.grid(pady=MENU_PADDING_1)
        vr_model_nout_Option = ComboBoxEditableMenu(vr_param_Frame, values=NOUT_SEL, textvariable=vr_model_nout_var, pattern=REG_SHIFTS, default='32', width=COMBO_WIDTH)
        vr_model_nout_Option.grid(pady=MENU_PADDING_1)
        #self.help_hints(vr_model_nout_Label, text=VR_MODEL_NOUT_HELP)

        vr_model_nout_lstm_Label = self.menu_sub_LABEL_SET(vr_param_Frame, 'Out Channels (LSTM layer)')
        vr_model_nout_lstm_Label.grid(pady=MENU_PADDING_1)
        vr_model_nout_lstm_Option = ComboBoxEditableMenu(vr_param_Frame, values=NOUT_LSTM_SEL, textvariable=vr_model_nout_lstm_var, pattern=REG_SHIFTS, default='128', width=COMBO_WIDTH)#
        vr_model_nout_lstm_Option.grid(pady=MENU_PADDING_1)
        #self.help_hints(vr_model_param_Label, text=VR_MODEL_NOUT_LSTM_HELP)

        vr_model_param_Label = self.menu_sub_LABEL_SET(vr_param_Frame, SELECT_MODEL_PARAM_TEXT)
        vr_model_param_Label.grid(pady=MENU_PADDING_1)
        vr_model_param_Option = ComboBoxMenu(vr_param_Frame, textvariable=vr_model_param_var, values=new_vr_params, width=30)
        vr_model_param_Option.grid(pady=MENU_PADDING_1)
        self.help_hints(vr_model_param_Label, text=VR_MODEL_PARAM_HELP)

        vr_param_confrim_Button = ttk.Button(vr_param_Frame, text=CONFIRM_TEXT, command=lambda:pull_data())
        vr_param_confrim_Button.grid(pady=MENU_PADDING_1)
        
        vr_param_cancel_Button = ttk.Button(vr_param_Frame, text=CANCEL_TEXT, command=cancel)
        vr_param_cancel_Button.grid(pady=MENU_PADDING_1)
        
        vr_new_toggle()
        opt_menu_selection(vr_model_stem_var.get())
        
        vr_param_menu.protocol("WM_DELETE_WINDOW", cancel)
        
        frame_list = [vr_param_Frame]
        self.menu_placement(vr_param_menu, CHOOSE_MODEL_PARAM_TEXT, pop_up=False if is_macos else True, frame_list=frame_list)

    def pop_up_vr_param_sub_json_dump(self, vr_model_params, vr_model_hash):
        """Dumps current selected VR model settings to a json named after model hash"""
        
        self.vr_model_params = vr_model_params

        vr_model_params_dump = json.dumps(vr_model_params, indent=4)
        
        with open(os.path.join(VR_HASH_DIR, f'{vr_model_hash}.json'), "w") as outfile:
            outfile.write(vr_model_params_dump)

    def pop_up_input_stem_name(self, stem_var:tk.StringVar, parent_window:tk.Toplevel):
        """
        Input Stem Name
        """
        
        stem_input_save = tk.Toplevel(root)
        
        def close_window(is_cancel=True):
            
            if is_cancel or not stem_input_save_var.get():
                stem_var.set(VOCAL_STEM)
            else:
                stem_input_save_text = stem_input_save_var.get().capitalize()
                
                if stem_input_save_text == VOCAL_STEM:
                    stem_text = INST_STEM if is_inverse_stem_var.get() else stem_input_save_text
                elif stem_input_save_text == INST_STEM:
                    stem_text = VOCAL_STEM if is_inverse_stem_var.get() else stem_input_save_text
                else:
                    stem_text = f"{NO_STEM}{stem_input_save_text}" if is_inverse_stem_var.get() else stem_input_save_text
                    
                stem_var.set(stem_text)

            stem_input_save.destroy()
            
            parent_window.attributes('-topmost', 'true') if OPERATING_SYSTEM == "Linux" else None
            parent_window.grab_set()
            root.wait_window(parent_window)
        
        stem_input_save_var = tk.StringVar(value='')
        is_inverse_stem_var = tk.BooleanVar(value=False)

        validation = lambda value:False if re.fullmatch(REG_INPUT_STEM_NAME, value) is None else True
        stem_input_save_Frame = self.menu_FRAME_SET(stem_input_save)
        stem_input_save_Frame.grid(row=1)  

        stem_input_save_title = self.menu_title_LABEL_SET(stem_input_save_Frame, INPUT_STEM_NAME_TEXT)
        stem_input_save_title.grid(pady=0)
        
        stem_input_name_Label = self.menu_sub_LABEL_SET(stem_input_save_Frame, STEM_NAME_TEXT)
        stem_input_name_Label.grid(pady=MENU_PADDING_1)
        stem_input_name_Entry = ttk.Combobox(stem_input_save_Frame, textvariable=stem_input_save_var, values=STEM_SET_MENU_2, justify='center', width=25)
        invalid_message = self.invalid_tooltip(stem_input_name_Entry, REG_INPUT_STEM_NAME)
        stem_input_name_Entry.grid(pady=MENU_PADDING_1)
        stem_input_name_Entry.focus_set()
        
        self.spacer_label(stem_input_save_Frame)
        
        is_inverse_stem_Button = ttk.Checkbutton(stem_input_save_Frame, text=IS_INVERSE_STEM_TEXT, variable=is_inverse_stem_var)
        is_inverse_stem_Button.grid(pady=0)

        entry_rules_Label = tk.Label(stem_input_save_Frame, text=STEM_INPUT_RULE, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground='#868687', justify="left")
        entry_rules_Label.grid(pady=MENU_PADDING_1)     
        
        mdx_param_set_Button = ttk.Button(stem_input_save_Frame, text=DONE_MENU_TEXT, command=lambda:close_window(is_cancel=False) if validation(stem_input_save_var.get()) else invalid_message())
        mdx_param_set_Button.grid(pady=MENU_PADDING_1)
        
        stop_process_Button = ttk.Button(stem_input_save_Frame, text=CANCEL_TEXT, command=close_window)
        stop_process_Button.grid(pady=MENU_PADDING_1)

        stem_input_save.protocol("WM_DELETE_WINDOW", close_window)

        frame_list = [stem_input_save_Frame]
        self.menu_placement(stem_input_save, INPUT_UNIQUE_STEM_NAME_TEXT, pop_up=True, frame_list=frame_list)

    def pop_up_save_ensemble(self):
        """
        Save Ensemble as...
        """
        
        ensemble_save = tk.Toplevel(root)
        
        ensemble_save_var = tk.StringVar(value='')

        ensemble_save_Frame = self.menu_FRAME_SET(ensemble_save)
        ensemble_save_Frame.grid(row=1)  
        
        validation = lambda value:False if re.fullmatch(REG_SAVE_INPUT, value) is None else True
        save_func = lambda:(self.pop_up_save_ensemble_sub_json_dump(self.ensemble_listbox_get_all_selected_models(), ensemble_save_var.get()), ensemble_save.destroy())

        if len(self.ensemble_listbox_get_all_selected_models()) <= 1:
            ensemble_save_title = self.menu_title_LABEL_SET(ensemble_save_Frame, ENSEMBLE_WARNING_NOT_ENOUGH_SHORT_TEXT, width=20)
            ensemble_save_title.grid()
            
            ensemble_save_title = self.menu_sub_LABEL_SET(ensemble_save_Frame, ENSEMBLE_WARNING_NOT_ENOUGH_TEXT)
            ensemble_save_title.grid(pady=MENU_PADDING_1)
            
            stop_process_Button = ttk.Button(ensemble_save_Frame, text=OK_TEXT, command=lambda:ensemble_save.destroy())
            stop_process_Button.grid()
        else:
            ensemble_save_title = self.menu_title_LABEL_SET(ensemble_save_Frame, SAVE_CURRENT_ENSEMBLE_TEXT)
            ensemble_save_title.grid()
            
            ensemble_name_Label = self.menu_sub_LABEL_SET(ensemble_save_Frame, ENSEMBLE_NAME_TEXT)
            ensemble_name_Label.grid(pady=MENU_PADDING_1)
            ensemble_name_Entry = ttk.Entry(ensemble_save_Frame, textvariable=ensemble_save_var, justify='center', width=25)
            ensemble_name_Entry.grid(pady=MENU_PADDING_1)
            invalid_message = self.invalid_tooltip(ensemble_name_Entry)
            ensemble_name_Entry.focus_set()
            self.spacer_label(ensemble_save_Frame)
            
            entry_rules_Label = tk.Label(ensemble_save_Frame, text=ENSEMBLE_INPUT_RULE, font=(MAIN_FONT_NAME, f"{FONT_SIZE_1}"), foreground='#868687', justify="left")
            entry_rules_Label.grid()     
            
            mdx_param_set_Button = ttk.Button(ensemble_save_Frame, text=SAVE_TEXT, command=lambda:save_func() if validation(ensemble_save_var.get()) else invalid_message())
            mdx_param_set_Button.grid(pady=MENU_PADDING_1)
            
            stop_process_Button = ttk.Button(ensemble_save_Frame, text=CANCEL_TEXT, command=lambda:ensemble_save.destroy())
            stop_process_Button.grid(pady=MENU_PADDING_1)
            
        self.menu_placement(ensemble_save, SAVE_CURRENT_ENSEMBLE_TEXT, pop_up=True)
        
    def pop_up_save_ensemble_sub_json_dump(self, selected_ensemble_model, ensemble_save_name: str):
        """Dumps current ensemble settings to a json named after user input"""
        
        if ensemble_save_name:
            self.chosen_ensemble_var.set(ensemble_save_name)
            ensemble_save_name = ensemble_save_name.replace(" ", "_")
            saved_data = {
                'ensemble_main_stem': self.ensemble_main_stem_var.get(),
                'ensemble_type': self.ensemble_type_var.get(),
                'selected_models': selected_ensemble_model,
                }
            
            saved_data_dump = json.dumps(saved_data, indent=4)
            with open(os.path.join(ENSEMBLE_CACHE_DIR, f'{ensemble_save_name}.json'), "w") as outfile:
                outfile.write(saved_data_dump)

    def deletion_list_fill(self, option_menu: ComboBoxMenu, selection_var: tk.StringVar, selection_dir, var_set, menu_name=None):
        """Fills the saved settings menu located in tab 2 of the main settings window"""
                
        def command_callback(event=None):
            self.deletion_entry(selection_var.get(), selection_dir, refresh_menu)
            selection_var.set(var_set)

        def refresh_menu(remove=None):
            selection_list = self.last_found_ensembles if menu_name == 'deleteensemble' else self.last_found_settings
            main_var = self.chosen_ensemble_var if menu_name == 'deleteensemble' else self.save_current_settings_var
            
            if remove and remove in selection_list:
                selection_list = list(selection_list)
                selection_list.remove(remove)
                main_var.set(CHOOSE_ENSEMBLE_OPTION)
            
            self.update_menus(option_widget=option_menu, 
                              style_name=menu_name, 
                              command=command_callback,
                              new_items=selection_list)

        refresh_menu()
        
    def deletion_entry(self, selection: str, path, callback):
        """Deletes selected user saved application settings"""
        
        if selection not in [SELECT_SAVED_SET, SELECT_SAVED_ENSEMBLE]:
            saved_path = os.path.join(path, f'{selection.replace(" ", "_")}.json')
            confirm = self.message_box(DELETE_ENS_ENTRY)
            if confirm:
                if os.path.isfile(saved_path):
                    os.remove(saved_path)
                    callback(selection)

    #--Download Center Methods--    

    def online_data_refresh(self, user_refresh=True, confirmation_box=False, refresh_list_Button=False, is_start_up=False, is_download_complete=False):
        """Checks for application updates"""
        
        def online_check():
            if not is_start_up:
                self.app_update_status_Text_var.set(LOADING_VERSION_INFO_TEXT)
                self.app_update_button_Text_var.set(CHECK_FOR_UPDATES_TEXT)

            is_new_update = False
            try:
                online_state = downloads_service_module.fetch_online_state()
                self.online_data = online_state.payload
                self.is_online = True

                try:
                    self.bulletin_data = online_state.bulletin or INFO_UNAVAILABLE_TEXT

                    if not is_windows:
                        self.bulletin_data = read_bulliten_text_mac(CR_TEXT, self.bulletin_data)
                    else:
                        self.bulletin_data = self.bulletin_data.replace("~", "•")

                except Exception as e:
                    self.bulletin_data = INFO_UNAVAILABLE_TEXT
                    print(e)

                if user_refresh:
                    self.download_list_state()
                    for widget in self.download_center_Buttons:
                        widget.configure(state=tk.NORMAL)
                    
                if refresh_list_Button:
                    self.download_progress_info_var.set('Download List Refreshed!')

                if OPERATING_SYSTEM=="Darwin":
                    self.lastest_version = self.online_data["current_version_mac"]
                elif OPERATING_SYSTEM=="Linux":
                    self.lastest_version = self.online_data["current_version_linux"]
                else:
                    self.lastest_version = self.online_data["current_version"]
                    
                if self.lastest_version == current_patch and not is_start_up:
                    self.app_update_status_Text_var.set('UVR Version Current')
                else:
                    is_new_update = True
                    is_beta_version = True if self.lastest_version == PREVIOUS_PATCH_WIN and BETA_VERSION in current_patch else False
                    
                    if not is_start_up:
                        if is_beta_version:
                            self.app_update_status_Text_var.set(f"Roll Back: {self.lastest_version}")
                            self.app_update_button_Text_var.set(ROLL_BACK_TEXT)
                        else:
                            self.app_update_status_Text_var.set(f"Update Found: {self.lastest_version}")
                            self.app_update_button_Text_var.set('Click Here to Update')
                        
                        if OPERATING_SYSTEM == "Windows":
                            self.download_update_link_var.set('{}{}{}'.format(UPDATE_REPO, self.lastest_version, application_extension))
                            self.download_update_path_var.set(os.path.join(BASE_PATH, f'{self.lastest_version}{application_extension}'))
                        elif OPERATING_SYSTEM == "Darwin":
                            self.download_update_link_var.set(UPDATE_MAC_ARM_REPO if SYSTEM_PROC == ARM or ARM in SYSTEM_ARCH else UPDATE_MAC_X86_64_REPO)
                        elif OPERATING_SYSTEM == "Linux":
                            self.download_update_link_var.set(UPDATE_LINUX_REPO)
                    
                    if not user_refresh:
                        if not is_beta_version and not self.lastest_version == current_patch:
                            self.command_Text.write(NEW_UPDATE_FOUND_TEXT(self.lastest_version))


                is_update_params = self.is_auto_update_model_params if is_start_up else self.is_auto_update_model_params_var.get()
                
                if is_update_params and is_start_up or is_download_complete:
                    self.download_model_settings()
                    
                # if is_download_complete:
                #     self.download_model_settings()

            except Exception as e:
                self.offline_state_set(is_start_up)
                is_new_update = False
                
                if user_refresh:
                    self.download_list_state(disable_only=True)
                    for widget in self.download_center_Buttons:
                        widget.configure(state=tk.DISABLED)
                        
                try:
                    self.error_log_var.set(error_text('Online Data Refresh', e))
                except Exception as e:
                    print(e)

            return is_new_update
            
        if confirmation_box:
            return online_check()
        else:
            self.current_thread = KThread(target=online_check)
            self.current_thread.setDaemon(True) if not is_windows else None
            self.current_thread.start()

    def offline_state_set(self, is_start_up=False):
        """Changes relevant settings and "Download Center" buttons if no internet connection is available"""
        
        if not is_start_up and self.is_menu_settings_open:
            self.app_update_status_Text_var.set(f'Version Status: {NO_CONNECTION}')
            self.download_progress_info_var.set(NO_CONNECTION) 
            self.app_update_button_Text_var.set('Refresh')
            self.refresh_list_Button.configure(state=tk.NORMAL)
            self.stop_download_Button_DISABLE()
            self.enable_tabs()
            
        self.is_online = False

    def download_validate_code(self, confirm=False, code_message=None):
        """Verifies the VIP download code"""
        
        self.decoded_vip_link = downloads_service_module.validate_vip_code(self.user_code_var.get())
        
        if confirm:
            if not self.decoded_vip_link == NO_CODE:
                info_text = 'VIP Models Added!'
                is_success_message = True
            else:
                info_text = 'Incorrect Code'
                is_success_message = False
                
            self.download_progress_info_var.set(info_text)
            self.user_code_validation_var.set(info_text)
            
            if code_message:
                code_message(info_text, is_success_message)
                
            self.download_list_fill()

    def download_list_fill(self, model_type=ALL_TYPES):
        """Fills the download lists with the data retrieved from the update check."""
        
        self.download_demucs_models_list.clear()

        model_download_mdx_list, model_download_mdx_name = [], "mdxdownload"
        model_download_vr_list, model_download_vr_name = [], "vrdownload"
        model_download_demucs_list, model_download_demucs_name = [], "demucsmdxdownload"

        download_catalog = downloads_service_module.build_download_catalog(
            self.online_data,
            decoded_vip_link=self.decoded_vip_link,
        )
        self.vr_download_list = download_catalog.vr_download_list
        self.mdx_download_list = download_catalog.mdx_download_list
        self.demucs_download_list = download_catalog.demucs_download_list
                     
        def configure_combobox(combobox:ComboBoxMenu, values:list, variable:tk.StringVar, arch_type, name):
            values = [NO_NEW_MODELS] if not values else values
            combobox['values'] = values
            combobox.update_dropdown_size(values, name, offset=310,
                                          command=lambda s: self.download_model_select(variable.get(), arch_type, variable))
                                     
        if model_type in [VR_ARCH_TYPE, ALL_TYPES]:
            model_download_vr_list = downloads_service_module.list_downloadable_items(download_catalog, VR_ARCH_TYPE)
            configure_combobox(self.model_download_vr_Option, model_download_vr_list, self.model_download_vr_var, VR_ARCH_TYPE, model_download_vr_name)

        if model_type in [MDX_ARCH_TYPE, ALL_TYPES]:
            model_download_mdx_list = downloads_service_module.list_downloadable_items(download_catalog, MDX_ARCH_TYPE)
            configure_combobox(self.model_download_mdx_Option, model_download_mdx_list, self.model_download_mdx_var, MDX_ARCH_TYPE, model_download_mdx_name)

        if model_type in [DEMUCS_ARCH_TYPE, ALL_TYPES]:
            model_download_demucs_list = downloads_service_module.list_downloadable_items(download_catalog, DEMUCS_ARCH_TYPE)
            configure_combobox(self.model_download_demucs_Option, model_download_demucs_list, self.model_download_demucs_var, DEMUCS_ARCH_TYPE, model_download_demucs_name)

    def download_model_settings(self):
        '''Update the newest model settings'''
        
        try:
            bundle = downloads_service_module.load_or_fetch_model_settings()
            self.vr_hash_MAPPER = bundle.vr_hash_mapper
            self.mdx_hash_MAPPER = bundle.mdx_hash_mapper
            self.mdx_name_select_MAPPER = bundle.mdx_name_select_mapper
            self.demucs_name_select_MAPPER = bundle.demucs_name_select_mapper
        except Exception as e:
            self.error_log_var.set(e)
            print(e)

    def download_list_state(self, reset=True, disable_only=False):
        """Makes sure only the models from the chosen AI network are selectable."""
        
        for widget in self.download_lists:
            widget.configure(state=tk.DISABLED)
        
        if reset:
            for download_list_var in self.download_list_vars:
                if self.is_online:
                    download_list_var.set(NO_MODEL)
                    self.download_Button.configure(state=tk.NORMAL)
                else:
                    download_list_var.set(NO_CONNECTION)
                    self.download_Button.configure(state=tk.DISABLED)
                    disable_only = True
            
        if not disable_only:
            self.download_Button.configure(state=tk.NORMAL)
            if self.select_download_var.get() == VR_ARCH_TYPE:
                self.model_download_vr_Option.configure(state=READ_ONLY)
                self.selected_download_var = self.model_download_vr_var
                self.download_list_fill(model_type=VR_ARCH_TYPE)
            if self.select_download_var.get() == MDX_ARCH_TYPE:
                self.model_download_mdx_Option.configure(state=READ_ONLY)
                self.selected_download_var = self.model_download_mdx_var
                self.download_list_fill(model_type=MDX_ARCH_TYPE)
            if self.select_download_var.get() == DEMUCS_ARCH_TYPE:
                self.model_download_demucs_Option.configure(state=READ_ONLY)
                self.selected_download_var = self.model_download_demucs_var
                self.download_list_fill(model_type=DEMUCS_ARCH_TYPE)
                
            self.stop_download_Button_DISABLE()

    def download_model_select(self, selection, type, var:tk.StringVar):
        """Prepares the data needed to download selected model."""
        
        self.download_demucs_newer_models.clear()
        self.current_download_plan = None

        if selection == NO_NEW_MODELS:
            selection = NO_MODEL
            var.set(NO_MODEL)
            return

        try:
            download_catalog = downloads_service_module.build_download_catalog(
                self.online_data,
                decoded_vip_link=self.decoded_vip_link,
            )
            plan = downloads_service_module.resolve_download_plan(
                selection,
                type,
                download_catalog,
                decoded_vip_link=self.decoded_vip_link,
            )
            self.current_download_plan = plan

            if plan.tasks:
                self.download_link_path_var.set(str(plan.tasks[0].url))
                self.download_save_path_var.set(str(plan.tasks[0].destination))
            for task in plan.tasks[1:]:
                self.download_demucs_newer_models.append([str(task.destination), task.url])
        except Exception:
            self.current_download_plan = None

    def download_item(self, is_update_app=False):
        """Downloads the model selected."""
        
        if not is_update_app:
            if self.selected_download_var.get() == NO_MODEL:
                self.download_progress_info_var.set(NO_MODEL)
                return        

        for widget in self.download_center_Buttons:
            widget.configure(state=tk.DISABLED)
        self.refresh_list_Button.configure(state=tk.DISABLED)
        self.manual_download_Button.configure(state=tk.DISABLED)
        
        is_demucs_newer = [True for x in DEMUCS_NEWER_ARCH_TYPES if x in self.selected_download_var.get()]

        self.download_list_state(reset=False, disable_only=True)
        self.stop_download_Button_ENABLE()
        self.disable_tabs()
        
        def download_progress_bar(item_index, total_items, current, total, task):
            if total:
                progress = ('%s' % (100 * current // total))
                self.download_progress_bar_var.set(int(progress))
                self.download_progress_percent_var.set(progress + ' %')
            self.download_progress_info_var.set(f'{DOWNLOADING_ITEM} {item_index}/{total_items}...')
            
        def push_download():
            self.is_download_thread_active = True
            try:
                if is_update_app:
                    self.download_progress_info_var.set(DOWNLOADING_UPDATE)
                    plan = downloads_service_module.DownloadPlan(
                        selection="update",
                        model_type="update",
                        tasks=(
                            downloads_service_module.DownloadTask(
                                name="update",
                                url=self.download_update_link_var.get(),
                                destination=Path(self.download_update_path_var.get()),
                            ),
                        ),
                    )
                    result = downloads_service_module.execute_download_plan(plan, progress=download_progress_bar)
                    if result.skipped_existing:
                        self.download_progress_info_var.set(FILE_EXISTS)
                    self.download_post_action(DOWNLOAD_UPDATE_COMPLETE)
                else:
                    plan = getattr(self, "current_download_plan", None)
                    if plan is None:
                        self.download_progress_info_var.set(DOWNLOAD_FAILED)
                        self.download_post_action(DOWNLOAD_FAILED)
                        return
                    if len(plan.tasks) == 1:
                        self.download_progress_info_var.set(SINGLE_DOWNLOAD)
                    result = downloads_service_module.execute_download_plan(plan, progress=download_progress_bar)
                    if result.skipped_existing and not result.completed:
                        self.download_progress_info_var.set(FILE_EXISTS)
                    self.download_post_action(DOWNLOAD_COMPLETE)
                
            except Exception as e:
                self.error_log_var.set(error_text(DOWNLOADING_ITEM, e))
                self.download_progress_info_var.set(DOWNLOAD_FAILED)
                
                if type(e).__name__ == 'URLError':
                    self.offline_state_set()
                else:
                    self.download_progress_percent_var.set(f"{type(e).__name__}")
                    self.download_post_action(DOWNLOAD_FAILED)
                          
        self.active_download_thread = KThread(target=push_download)
        self.active_download_thread.start()

    def download_post_action(self, action):
        """Resets the widget variables in the "Download Center" based on the state of the download."""
        
        for widget in self.download_center_Buttons:
            widget.configure(state=tk.NORMAL)
        self.refresh_list_Button.configure(state=tk.NORMAL)
        self.manual_download_Button.configure(state=tk.NORMAL)
        
        self.enable_tabs()
        self.stop_download_Button_DISABLE()
        
        if action == DOWNLOAD_FAILED:
            try:
                self.active_download_thread.terminate()
            finally:
                self.download_progress_info_var.set(DOWNLOAD_FAILED)
                self.download_list_state(reset=False)
        if action == DOWNLOAD_STOPPED:
            try:
                self.active_download_thread.terminate()
            finally:
                self.download_progress_info_var.set(DOWNLOAD_STOPPED)
                self.download_list_state(reset=False)
        if action == DOWNLOAD_COMPLETE:
            self.online_data_refresh(is_download_complete=True)
            self.download_progress_info_var.set(DOWNLOAD_COMPLETE)
            self.download_list_state()
        if action == DOWNLOAD_UPDATE_COMPLETE:
            self.download_progress_info_var.set(DOWNLOAD_UPDATE_COMPLETE)
            if os.path.isfile(self.download_update_path_var.get()):
                subprocess.Popen(self.download_update_path_var.get())
            self.download_list_state()
        
        
        self.is_download_thread_active = False
        
        self.delete_temps()
   
    #--Refresh/Loop Methods--    

    def update_loop(self):
        """Update the model dropdown menus"""

        if self.clear_cache_torch:
            clear_gpu_cache()
            self.clear_cache_torch = False

        if self.is_process_stopped:
            if self.thread_check(self.active_processing_thread):
                self.conversion_Button_Text_var.set(STOP_PROCESSING)
                self.conversion_Button.configure(state=tk.DISABLED)
                self.stop_Button.configure(state=tk.DISABLED)
            else:
                self.stop_Button.configure(state=tk.NORMAL)
                self.conversion_Button_Text_var.set(START_PROCESSING)
                self.conversion_Button.configure(state=tk.NORMAL)
                self.progress_bar_main_var.set(0)
                clear_gpu_cache()
                self.is_process_stopped = False
            
        if self.is_confirm_error_var.get():
            self.check_is_menu_open(ERROR_OPTION)
            self.is_confirm_error_var.set(False)

        if self.is_check_splash and is_windows:
            
            while not self.msg_queue.empty():
                message = self.msg_queue.get_nowait()
                print(message)
            
            close_process(self.msg_queue)
            self.is_check_splash = False

        #self.auto_save()

        self.update_available_models()
        self.after(600, self.update_loop)
          
    def update_menus(self, option_widget:ComboBoxMenu, style_name, command, new_items, last_items=None, base_options=None):
                
        if new_items != last_items:
            formatted_items = [item.replace("_", " ") for item in new_items]
            if not formatted_items and base_options:
                base_options = [option for option in base_options if option != OPT_SEPARATOR_SAVE]
            
            final_options = formatted_items + base_options if base_options else formatted_items
            option_widget['values'] = final_options
            option_widget.update_dropdown_size(formatted_items, style_name, command=command)
            return new_items
        return last_items
          
    def update_available_models(self):
        """
        Loops through all models in each model directory and adds them to the appropriate model menu.
        Also updates ensemble listbox and user saved settings list.
        """
        
        def fix_name(name, mapper:dict): return next((new_name for old_name, new_name in mapper.items() if name in old_name), name)
        
        new_vr_models = self.get_files_from_dir(VR_MODELS_DIR, PTH)
        new_mdx_models = self.get_files_from_dir(MDX_MODELS_DIR, (ONNX, CKPT), is_mdxnet=True)
        new_demucs_models = self.get_files_from_dir(DEMUCS_MODELS_DIR, (CKPT, '.gz', '.th')) + self.get_files_from_dir(DEMUCS_NEWER_REPO_DIR, YAML)
        new_ensembles_found = self.get_files_from_dir(ENSEMBLE_CACHE_DIR, JSON)
        new_settings_found = self.get_files_from_dir(SETTINGS_CACHE_DIR, JSON)
        new_models_found = new_vr_models + new_mdx_models + new_demucs_models
        is_online = self.is_online_model_menu
        
        def loop_directories(option_menu:ComboBoxMenu, option_var, model_list, model_type, name_mapper=None):
            current_selection = option_menu.get()
            option_list = [fix_name(file_name, name_mapper) for file_name in model_list] if name_mapper else model_list
            sorted_options = natsort.natsorted(option_list)
            option_list_option_menu = sorted_options + [OPT_SEPARATOR, DOWNLOAD_MORE] if self.is_online else sorted_options
            
            if not option_list and self.is_online:
                option_list_option_menu = [option for option in option_list_option_menu if option != OPT_SEPARATOR]
            
            option_menu['values'] = option_list_option_menu
            option_menu.set(current_selection)
            option_menu.update_dropdown_size(option_list, model_type)
            
            if self.is_root_defined_var.get() and model_type == MDX_ARCH_TYPE and self.chosen_process_method_var.get() == MDX_ARCH_TYPE:
                self.selection_action_models_sub(current_selection, model_type, option_var)
                
            return tuple(f"{model_type}{ENSEMBLE_PARTITION}{model_name}" for model_name in sorted_options)

        if new_models_found != self.last_found_models or is_online != self.is_online:
            self.model_data_table = []
            
            vr_model_list = loop_directories(self.vr_model_Option, self.vr_model_var, new_vr_models, VR_ARCH_TYPE, name_mapper=None)
            mdx_model_list = loop_directories(self.mdx_net_model_Option, self.mdx_net_model_var, new_mdx_models, MDX_ARCH_TYPE, name_mapper=self.mdx_name_select_MAPPER)
            demucs_model_list = loop_directories(self.demucs_model_Option, self.demucs_model_var, new_demucs_models, DEMUCS_ARCH_TYPE, name_mapper=self.demucs_name_select_MAPPER)
            
            self.ensemble_model_list = vr_model_list + mdx_model_list + demucs_model_list
            self.default_change_model_list = vr_model_list + mdx_model_list
            self.last_found_models = new_models_found
            self.is_online_model_menu = self.is_online
            
            if not self.chosen_ensemble_var.get() == CHOOSE_ENSEMBLE_OPTION:
                self.selection_action_chosen_ensemble(self.chosen_ensemble_var.get())
            else:
                if not self.ensemble_main_stem_var.get() == CHOOSE_STEM_PAIR:
                    self.selection_action_ensemble_stems(self.ensemble_main_stem_var.get(), auto_update=self.ensemble_listbox_get_all_selected_models())
                else:
                    self.ensemble_listbox_clear_and_insert_new(self.ensemble_model_list)

        self.last_found_ensembles = self.update_menus(option_widget=self.chosen_ensemble_Option, 
                                                      style_name='savedensembles',
                                                      command=None, 
                                                      new_items=new_ensembles_found, 
                                                      last_items=self.last_found_ensembles, 
                                                      base_options=ENSEMBLE_OPTIONS
        )

        self.last_found_settings = self.update_menus(option_widget=self.save_current_settings_Option, 
                                                      style_name='savedsettings',
                                                      command=None, 
                                                      new_items=new_settings_found, 
                                                      last_items=self.last_found_settings, 
                                                      base_options=SAVE_SET_OPTIONS
        )

    def update_main_widget_states_mdx(self):
        self.ui_actions().update_main_widget_states_mdx()

    def move_widget_offscreen(self, widget, step=10):
        current_x = widget.winfo_x()
        current_y = widget.winfo_y()
        if current_x > -1000:  # assuming -1000 is your off-screen target
            widget.place(x=current_x - step, y=current_y)
            widget.after(10, lambda: self.move_widget_offscreen(widget, step))

    def update_main_widget_states(self):
        """Updates main widget states based on chosen process method"""
        self.ui_actions().update_main_widget_states()

    def update_button_states(self):
        """Updates the available stems for selected Demucs model"""
        self.ui_actions().update_button_states()

    def update_button_states_mdx(self, model_stems):
        """Updates the available stems for selected Demucs model"""
        self.ui_actions().update_button_states_mdx(model_stems)
                            
    def update_stem_checkbox_labels(self, selection, demucs=False, disable_boxes=False, is_disable_demucs_boxes=True):
        """Updates the "save only" checkboxes based on the model selected"""
        self.ui_actions().update_stem_checkbox_labels(selection, demucs, disable_boxes, is_disable_demucs_boxes)
     
    def update_ensemble_algorithm_menu(self, is_4_stem=False):
        self.ui_actions().update_ensemble_algorithm_menu(is_4_stem)

    def selection_action(self, event, option_var, is_mdx_net=False):
        self.ui_actions().selection_action(event, option_var, is_mdx_net)

    def selection_action_models(self, selection):
        """Accepts model names and verifies their state."""
        return self.ui_actions().selection_action_models(selection)

    def _handle_model_by_chosen_method(self, selection):
        """Handles model selection based on the currently chosen method."""
        self.ui_actions()._handle_model_by_chosen_method(selection)

    def _handle_ensemble_mode_selection(self, selection):
        """Handles the case where the current method is 'ENSEMBLE_MODE'."""
        return self.ui_actions()._handle_ensemble_mode_selection(selection)

    def selection_action_models_sub(self, selection, ai_type, var: tk.StringVar):
        """Takes input directly from the selection_action_models parent function"""
        self.ui_actions().selection_action_models_sub(selection, ai_type, var)

    def selection_action_process_method(self, selection, from_widget=False, is_from_conv_menu=False):
        """Checks model and variable status when toggling between process methods"""
        self.ui_actions().selection_action_process_method(selection, from_widget, is_from_conv_menu)

    def selection_action_chosen_ensemble(self, selection):
        """Activates specific actions depending on selected ensemble option"""
        self.ui_actions().selection_action_chosen_ensemble(selection)
           
    def selection_action_chosen_ensemble_load_saved(self, saved_ensemble):
        """Loads the data from selected saved ensemble"""
        self.ui_actions().selection_action_chosen_ensemble_load_saved(saved_ensemble)
            
    def selection_action_ensemble_stems(self, selection: str, from_menu=True, auto_update=None):
        """Filters out all models from ensemble listbox that are incompatible with selected ensemble stem"""
        self.ui_actions().selection_action_ensemble_stems(selection, from_menu, auto_update)

    def selection_action_saved_settings(self, selection, process_method=None):
        """Activates specific action based on the selected settings from the saved settings selections"""
        self.ui_actions().selection_action_saved_settings(selection, process_method)

    def handle_special_options(self, selection, process_method):
        """Handles actions for special options."""
        self.ui_actions().handle_special_options(selection, process_method)

    def handle_saved_settings(self, selection, process_method):
        """Handles actions for saved settings."""
        self.ui_actions().handle_saved_settings(selection, process_method)

    #--Processing Methods-- 

    def process_input_selections(self):
        """Grabbing all audio files from selected directories."""
        self.file_inputs().process_input_selections()

    def process_check_wav_type(self):
        if self.wav_type_set_var.get() == '32-bit Float':
            self.wav_type_set = 'FLOAT'
        elif self.wav_type_set_var.get() == '64-bit Float':#
            self.wav_type_set = 'FLOAT' if not self.save_format_var.get() == WAV else 'DOUBLE'
        else:
            self.wav_type_set = self.wav_type_set_var.get()
            
    def process_preliminary_checks(self):
        """Verifies a valid model is chosen"""
        
        self.process_check_wav_type()
        
        if self.chosen_process_method_var.get() == ENSEMBLE_MODE:
            continue_process = lambda:False if len(self.ensemble_listbox_get_all_selected_models()) <= 1 else True
        if self.chosen_process_method_var.get() == VR_ARCH_PM:
            continue_process = lambda:False if self.vr_model_var.get() == CHOOSE_MODEL else True
        if self.chosen_process_method_var.get() == MDX_ARCH_TYPE:
            continue_process = lambda:False if self.mdx_net_model_var.get() == CHOOSE_MODEL else True
        if self.chosen_process_method_var.get() == DEMUCS_ARCH_TYPE:
            continue_process = lambda:False if self.demucs_model_var.get() == CHOOSE_MODEL else True

        return continue_process()

    def process_storage_check(self):
        """Verifies storage requirments"""
        
        total, used, free = shutil.disk_usage("/") 
        
        space_details = f'Detected Total Space: {int(total/1.074e+9)} GB\'s\n' +\
                        f'Detected Used Space: {int(used/1.074e+9)} GB\'s\n' +\
                        f'Detected Free Space: {int(free/1.074e+9)} GB\'s\n'
            
        appropriate_storage = True
            
        if int(free/1.074e+9) <= int(2):
            self.error_dialoge([STORAGE_ERROR[0], f'{STORAGE_ERROR[1]}{space_details}'])
            appropriate_storage = False
        
        if int(free/1.074e+9) in [3, 4, 5, 6, 7, 8]:
            appropriate_storage = self.message_box([STORAGE_WARNING[0], f'{STORAGE_WARNING[1]}{space_details}{CONFIRM_WARNING}'])
                        
        return appropriate_storage

    def process_initialize(self):
        """Verifies the input/output directories are valid and prepares to thread the main process."""
        self.processing_controller().process_initialize()

    def process_button_init(self):
        self.processing_controller().process_button_init()

    def process_get_baseText(self, total_files, file_num, is_dual=False):
        """Create the base text for the command widget"""
        return self.processing_controller().process_get_base_text(total_files, file_num, is_dual)

    def process_update_progress(self, total_files, step: float = 1):
        """Calculate the progress for the progress widget in the GUI"""
        self.processing_controller().process_update_progress(total_files, step)

    def confirm_stop_process(self):
        """Asks for confirmation before halting active process"""
        self.processing_controller().confirm_stop_process()

    def process_end(self, error=None):
        """End of process actions"""
        self.processing_controller().process_end(error)

    def process_tool_start(self):
        """Start the conversion for all the given mp3 and wav files"""
        self.processing_controller().process_tool_start()

    def process_determine_secondary_model(self, process_method, main_model_primary_stem, is_primary_stem_only=False, is_secondary_stem_only=False):
        """Obtains the correct secondary model data for conversion."""
        return self.processing_controller().process_determine_secondary_model(
            process_method,
            main_model_primary_stem,
            is_primary_stem_only,
            is_secondary_stem_only,
        )
        
    def process_determine_demucs_pre_proc_model(self, primary_stem=None):
        """Obtains the correct pre-process secondary model data for conversion."""
        return self.processing_controller().process_determine_demucs_pre_proc_model(primary_stem)

    def process_determine_vocal_split_model(self):
        """Obtains the correct vocal splitter secondary model data for conversion."""
        return self.processing_controller().process_determine_vocal_split_model()

    def check_only_selection_stem(self, checktype):
        return self.processing_controller().check_only_selection_stem(checktype)

    def determine_voc_split(self, models):
        return self.processing_controller().determine_voc_split(models)
        
    def process_start(self):
        """Start the conversion for all the given mp3 and wav files"""
        self.processing_controller().process_start()

    #--Varible Methods--

    def load_to_default_confirm(self):
        """Reset settings confirmation after asking for confirmation"""
        if self.thread_check(self.active_processing_thread):
            self.error_dialogue(SET_TO_DEFAULT_PROCESS_ERROR)
            return
        
        confirm = messagebox.askyesno(
            parent=root, 
            title=RESET_ALL_TO_DEFAULT_WARNING[0], 
            message=RESET_ALL_TO_DEFAULT_WARNING[1]
        )
        if not confirm:
            return
        
        self.load_saved_settings(DEFAULT_DATA, is_default_reset=True)
        self.update_checkbox_text()

        if self.pre_proc_model_toggle is not None and self.is_open_menu_advanced_demucs_options.get():
            self.pre_proc_model_toggle()

        if (self.change_state_lambda is not None and (
            self.is_open_menu_advanced_vr_options.get() or 
            self.is_open_menu_advanced_mdx_options.get() or 
            self.is_open_menu_advanced_demucs_options.get()
        )):
            self.change_state_lambda()

    def load_saved_vars(self, data):
        """Initializes primary Tkinter vars"""
        data = normalize_app_settings_dict(data)

        ## ADD_BUTTON
        self.chosen_process_method_var = tk.StringVar(value=data['chosen_process_method'])
        
        #VR Architecture Vars
        self.vr_model_var = tk.StringVar(value=data['vr_model'])
        self.aggression_setting_var = tk.StringVar(value=data['aggression_setting'])
        self.window_size_var = tk.StringVar(value=data['window_size'])
        self.mdx_segment_size_var = tk.StringVar(value=data['mdx_segment_size'])
        self.batch_size_var = tk.StringVar(value=data['batch_size'])
        self.crop_size_var = tk.StringVar(value=data['crop_size'])
        self.is_tta_var = tk.BooleanVar(value=data['is_tta'])
        self.is_output_image_var = tk.BooleanVar(value=data['is_output_image'])
        self.is_post_process_var = tk.BooleanVar(value=data['is_post_process'])
        self.is_high_end_process_var = tk.BooleanVar(value=data['is_high_end_process'])
        self.post_process_threshold_var = tk.StringVar(value=data['post_process_threshold'])
        self.vr_voc_inst_secondary_model_var = tk.StringVar(value=data['vr_voc_inst_secondary_model'])
        self.vr_other_secondary_model_var = tk.StringVar(value=data['vr_other_secondary_model'])
        self.vr_bass_secondary_model_var = tk.StringVar(value=data['vr_bass_secondary_model'])
        self.vr_drums_secondary_model_var = tk.StringVar(value=data['vr_drums_secondary_model'])
        self.vr_is_secondary_model_activate_var = tk.BooleanVar(value=data['vr_is_secondary_model_activate'])
        self.vr_voc_inst_secondary_model_scale_var = tk.StringVar(value=data['vr_voc_inst_secondary_model_scale'])
        self.vr_other_secondary_model_scale_var = tk.StringVar(value=data['vr_other_secondary_model_scale'])
        self.vr_bass_secondary_model_scale_var = tk.StringVar(value=data['vr_bass_secondary_model_scale'])
        self.vr_drums_secondary_model_scale_var = tk.StringVar(value=data['vr_drums_secondary_model_scale'])

        #Demucs Vars
        self.demucs_model_var = tk.StringVar(value=data['demucs_model'])
        self.segment_var = tk.StringVar(value=data['segment'])
        self.overlap_var = tk.StringVar(value=data['overlap'])
        self.overlap_mdx_var = tk.StringVar(value=data['overlap_mdx'])
        self.overlap_mdx23_var = tk.StringVar(value=data['overlap_mdx23'])
        self.shifts_var = tk.StringVar(value=data['shifts'])
        self.chunks_demucs_var = tk.StringVar(value=data['chunks_demucs'])
        self.margin_demucs_var = tk.StringVar(value=data['margin_demucs'])
        self.is_chunk_demucs_var = tk.BooleanVar(value=data['is_chunk_demucs'])
        self.is_chunk_mdxnet_var = tk.BooleanVar(value=False)
        self.is_primary_stem_only_Demucs_var = tk.BooleanVar(value=data['is_primary_stem_only_Demucs'])
        self.is_secondary_stem_only_Demucs_var = tk.BooleanVar(value=data['is_secondary_stem_only_Demucs'])
        self.is_split_mode_var = tk.BooleanVar(value=data['is_split_mode'])
        self.is_demucs_combine_stems_var = tk.BooleanVar(value=data['is_demucs_combine_stems'])#is_mdx23_combine_stems
        self.is_mdx23_combine_stems_var = tk.BooleanVar(value=data['is_mdx23_combine_stems'])
        self.demucs_voc_inst_secondary_model_var = tk.StringVar(value=data['demucs_voc_inst_secondary_model'])
        self.demucs_other_secondary_model_var = tk.StringVar(value=data['demucs_other_secondary_model'])
        self.demucs_bass_secondary_model_var = tk.StringVar(value=data['demucs_bass_secondary_model'])
        self.demucs_drums_secondary_model_var = tk.StringVar(value=data['demucs_drums_secondary_model'])
        self.demucs_is_secondary_model_activate_var = tk.BooleanVar(value=data['demucs_is_secondary_model_activate'])
        self.demucs_voc_inst_secondary_model_scale_var = tk.StringVar(value=data['demucs_voc_inst_secondary_model_scale'])
        self.demucs_other_secondary_model_scale_var = tk.StringVar(value=data['demucs_other_secondary_model_scale'])
        self.demucs_bass_secondary_model_scale_var = tk.StringVar(value=data['demucs_bass_secondary_model_scale'])
        self.demucs_drums_secondary_model_scale_var = tk.StringVar(value=data['demucs_drums_secondary_model_scale'])
        self.demucs_pre_proc_model_var = tk.StringVar(value=data['demucs_pre_proc_model'])
        self.is_demucs_pre_proc_model_activate_var = tk.BooleanVar(value=data['is_demucs_pre_proc_model_activate'])
        self.is_demucs_pre_proc_model_inst_mix_var = tk.BooleanVar(value=data['is_demucs_pre_proc_model_inst_mix'])
        
        #MDX-Net Vars
        self.mdx_net_model_var = tk.StringVar(value=data['mdx_net_model'])
        self.chunks_var = tk.StringVar(value=data['chunks'])
        self.margin_var = tk.StringVar(value=data['margin'])
        self.compensate_var = tk.StringVar(value=data['compensate'])
        self.denoise_option_var = tk.StringVar(value=data['denoise_option'])#
        self.phase_option_var = tk.StringVar(value=data['phase_option'])#
        self.phase_shifts_var = tk.StringVar(value=data['phase_shifts'])#
        self.is_save_align_var = tk.BooleanVar(value=data['is_save_align'])#,
        self.is_match_silence_var = tk.BooleanVar(value=data['is_match_silence'])#
        self.is_spec_match_var = tk.BooleanVar(value=data['is_spec_match'])#
        self.is_match_frequency_pitch_var = tk.BooleanVar(value=data['is_match_frequency_pitch'])#
        self.is_mdx_c_seg_def_var = tk.BooleanVar(value=data['is_mdx_c_seg_def'])#
        self.is_invert_spec_var = tk.BooleanVar(value=data['is_invert_spec'])#
        self.is_deverb_vocals_var = tk.BooleanVar(value=data['is_deverb_vocals'])#
        self.deverb_vocal_opt_var = tk.StringVar(value=data['deverb_vocal_opt'])#
        self.voc_split_save_opt_var = tk.StringVar(value=data['voc_split_save_opt'])#
        self.is_mixer_mode_var = tk.BooleanVar(value=data['is_mixer_mode'])
        self.mdx_batch_size_var = tk.StringVar(value=data['mdx_batch_size'])
        self.mdx_voc_inst_secondary_model_var = tk.StringVar(value=data['mdx_voc_inst_secondary_model'])
        self.mdx_other_secondary_model_var = tk.StringVar(value=data['mdx_other_secondary_model'])
        self.mdx_bass_secondary_model_var = tk.StringVar(value=data['mdx_bass_secondary_model'])
        self.mdx_drums_secondary_model_var = tk.StringVar(value=data['mdx_drums_secondary_model'])
        self.mdx_is_secondary_model_activate_var = tk.BooleanVar(value=data['mdx_is_secondary_model_activate'])
        self.mdx_voc_inst_secondary_model_scale_var = tk.StringVar(value=data['mdx_voc_inst_secondary_model_scale'])
        self.mdx_other_secondary_model_scale_var = tk.StringVar(value=data['mdx_other_secondary_model_scale'])
        self.mdx_bass_secondary_model_scale_var = tk.StringVar(value=data['mdx_bass_secondary_model_scale'])
        self.mdx_drums_secondary_model_scale_var = tk.StringVar(value=data['mdx_drums_secondary_model_scale'])
        self.is_mdxnet_c_model_var = tk.BooleanVar(value=False)

        #Ensemble Vars
        self.is_save_all_outputs_ensemble_var = tk.BooleanVar(value=data['is_save_all_outputs_ensemble'])
        self.is_append_ensemble_name_var = tk.BooleanVar(value=data['is_append_ensemble_name'])

        #Audio Tool Vars
        self.chosen_audio_tool_var = tk.StringVar(value=data['chosen_audio_tool'])
        self.choose_algorithm_var = tk.StringVar(value=data['choose_algorithm'])
        self.time_stretch_rate_var = tk.StringVar(value=data['time_stretch_rate'])
        self.pitch_rate_var = tk.StringVar(value=data['pitch_rate'])
        self.is_time_correction_var = tk.BooleanVar(value=data['is_time_correction'])

        #Shared Vars
        self.semitone_shift_var = tk.StringVar(value=data['semitone_shift'])
        self.mp3_bit_set_var = tk.StringVar(value=data['mp3_bit_set'])
        self.save_format_var = tk.StringVar(value=data['save_format'])
        self.wav_type_set_var = tk.StringVar(value=data['wav_type_set'])#
        self.device_set_var = tk.StringVar(value=data['device_set'])#
        self.user_code_var = tk.StringVar(value=data['user_code']) 
        self.is_gpu_conversion_var = tk.BooleanVar(value=data['is_gpu_conversion'])
        self.is_primary_stem_only_var = tk.BooleanVar(value=data['is_primary_stem_only'])
        self.is_secondary_stem_only_var = tk.BooleanVar(value=data['is_secondary_stem_only'])
        self.is_testing_audio_var = tk.BooleanVar(value=data['is_testing_audio'])#
        self.is_auto_update_model_params_var = tk.BooleanVar(value=True)#
        self.is_auto_update_model_params = data['is_auto_update_model_params']
        self.is_add_model_name_var = tk.BooleanVar(value=data['is_add_model_name'])
        self.is_accept_any_input_var = tk.BooleanVar(value=data['is_accept_any_input'])
        self.is_task_complete_var = tk.BooleanVar(value=data['is_task_complete'])
        self.is_normalization_var = tk.BooleanVar(value=data['is_normalization'])#
        self.is_use_opencl_var = tk.BooleanVar(value=False)#True if is_opencl_only else data['is_use_opencl'])#
        self.is_wav_ensemble_var = tk.BooleanVar(value=data['is_wav_ensemble'])#
        self.is_create_model_folder_var = tk.BooleanVar(value=data['is_create_model_folder'])
        self.help_hints_var = tk.BooleanVar(value=data['help_hints_var'])
        self.model_sample_mode_var = tk.BooleanVar(value=data['model_sample_mode'])
        self.model_sample_mode_duration_var = tk.StringVar(value=data['model_sample_mode_duration'])
        self.model_sample_mode_duration_checkbox_var = tk.StringVar(value=SAMPLE_MODE_CHECKBOX(self.model_sample_mode_duration_var.get()))
        self.model_sample_mode_duration_label_var = tk.StringVar(value=f'{self.model_sample_mode_duration_var.get()} Seconds')
        self.set_vocal_splitter_var = tk.StringVar(value=data['set_vocal_splitter'])
        self.is_set_vocal_splitter_var = tk.BooleanVar(value=data['is_set_vocal_splitter'])#
        self.is_save_inst_set_vocal_splitter_var = tk.BooleanVar(value=data['is_save_inst_set_vocal_splitter'])#
        
        #Path Vars
        self.export_path_var = tk.StringVar(value=data['export_path'])
        self.inputPaths = data['input_paths']
        self.lastDir = data['lastDir']
        
        #DualPaths-Align
        self.time_window_var = tk.StringVar(value=data['time_window'])#
        self.intro_analysis_var = tk.StringVar(value=data['intro_analysis'])
        self.db_analysis_var = tk.StringVar(value=data['db_analysis'])
        
        self.fileOneEntry_var = tk.StringVar(value=data['fileOneEntry'])
        self.fileOneEntry_Full_var = tk.StringVar(value=data['fileOneEntry_Full'])
        self.fileTwoEntry_var = tk.StringVar(value=data['fileTwoEntry'])
        self.fileTwoEntry_Full_var = tk.StringVar(value=data['fileTwoEntry_Full'])
        self.DualBatch_inputPaths = data['DualBatch_inputPaths']
   
    def load_saved_settings(self, loaded_setting: dict, process_method=None, is_default_reset=False):
        """Loads user saved application settings or resets to default"""
        loaded_setting = normalize_app_settings_dict(loaded_setting)
                
        is_default_reset = True if process_method == ENSEMBLE_MODE or is_default_reset else False
        
        if process_method == VR_ARCH_PM or is_default_reset:
            self.vr_model_var.set(loaded_setting['vr_model'])
            self.aggression_setting_var.set(loaded_setting['aggression_setting'])
            self.window_size_var.set(loaded_setting['window_size'])
            self.mdx_segment_size_var.set(loaded_setting['mdx_segment_size'])
            self.batch_size_var.set(loaded_setting['batch_size'])
            self.crop_size_var.set(loaded_setting['crop_size'])
            self.is_tta_var.set(loaded_setting['is_tta'])
            self.is_output_image_var.set(loaded_setting['is_output_image'])
            self.is_post_process_var.set(loaded_setting['is_post_process'])
            self.is_high_end_process_var.set(loaded_setting['is_high_end_process'])
            self.post_process_threshold_var.set(loaded_setting['post_process_threshold'])
            self.vr_voc_inst_secondary_model_var.set(loaded_setting['vr_voc_inst_secondary_model'])
            self.vr_other_secondary_model_var.set(loaded_setting['vr_other_secondary_model'])
            self.vr_bass_secondary_model_var.set(loaded_setting['vr_bass_secondary_model'])
            self.vr_drums_secondary_model_var.set(loaded_setting['vr_drums_secondary_model'])
            self.vr_is_secondary_model_activate_var.set(loaded_setting['vr_is_secondary_model_activate'])
            self.vr_voc_inst_secondary_model_scale_var.set(loaded_setting['vr_voc_inst_secondary_model_scale'])
            self.vr_other_secondary_model_scale_var.set(loaded_setting['vr_other_secondary_model_scale'])
            self.vr_bass_secondary_model_scale_var.set(loaded_setting['vr_bass_secondary_model_scale'])
            self.vr_drums_secondary_model_scale_var.set(loaded_setting['vr_drums_secondary_model_scale'])
        
        if process_method == DEMUCS_ARCH_TYPE or is_default_reset:
            self.demucs_model_var.set(loaded_setting['demucs_model'])
            self.segment_var.set(loaded_setting['segment'])
            self.overlap_var.set(loaded_setting['overlap'])
            self.shifts_var.set(loaded_setting['shifts'])
            self.chunks_demucs_var.set(loaded_setting['chunks_demucs'])
            self.margin_demucs_var.set(loaded_setting['margin_demucs'])
            self.is_chunk_demucs_var.set(loaded_setting['is_chunk_demucs'])
            self.is_chunk_mdxnet_var.set(loaded_setting['is_chunk_mdxnet'])
            self.is_primary_stem_only_Demucs_var.set(loaded_setting['is_primary_stem_only_Demucs'])
            self.is_secondary_stem_only_Demucs_var.set(loaded_setting['is_secondary_stem_only_Demucs'])
            self.is_split_mode_var.set(loaded_setting['is_split_mode'])
            self.is_demucs_combine_stems_var.set(loaded_setting['is_demucs_combine_stems'])#
            self.is_mdx23_combine_stems_var.set(loaded_setting['is_mdx23_combine_stems'])#
            self.demucs_voc_inst_secondary_model_var.set(loaded_setting['demucs_voc_inst_secondary_model'])
            self.demucs_other_secondary_model_var.set(loaded_setting['demucs_other_secondary_model'])
            self.demucs_bass_secondary_model_var.set(loaded_setting['demucs_bass_secondary_model'])
            self.demucs_drums_secondary_model_var.set(loaded_setting['demucs_drums_secondary_model'])
            self.demucs_is_secondary_model_activate_var.set(loaded_setting['demucs_is_secondary_model_activate'])
            self.demucs_voc_inst_secondary_model_scale_var.set(loaded_setting['demucs_voc_inst_secondary_model_scale'])
            self.demucs_other_secondary_model_scale_var.set(loaded_setting['demucs_other_secondary_model_scale'])
            self.demucs_bass_secondary_model_scale_var.set(loaded_setting['demucs_bass_secondary_model_scale'])
            self.demucs_drums_secondary_model_scale_var.set(loaded_setting['demucs_drums_secondary_model_scale'])
            self.demucs_stems_var.set(loaded_setting['demucs_stems'])
            self.mdxnet_stems_var.set(loaded_setting['mdx_stems'])
            self.update_stem_checkbox_labels(self.demucs_stems_var.get(), demucs=True)
            self.demucs_pre_proc_model_var.set(loaded_setting['demucs_pre_proc_model'])
            self.is_demucs_pre_proc_model_activate_var.set(loaded_setting['is_demucs_pre_proc_model_activate'])
            self.is_demucs_pre_proc_model_inst_mix_var.set(loaded_setting['is_demucs_pre_proc_model_inst_mix'])
        
        if process_method == MDX_ARCH_TYPE or is_default_reset:
            self.mdx_net_model_var.set(loaded_setting['mdx_net_model'])
            self.chunks_var.set(loaded_setting['chunks'])
            self.margin_var.set(loaded_setting['margin'])
            self.compensate_var.set(loaded_setting['compensate'])
            self.denoise_option_var.set(loaded_setting['denoise_option'])
            self.is_match_frequency_pitch_var.set(loaded_setting['is_match_frequency_pitch'])#
            self.overlap_mdx_var.set(loaded_setting['overlap_mdx'])
            self.overlap_mdx23_var.set(loaded_setting['overlap_mdx23'])
            self.is_mdx_c_seg_def_var.set(loaded_setting['is_mdx_c_seg_def'])#
            self.is_invert_spec_var.set(loaded_setting['is_invert_spec'])#
            self.is_mixer_mode_var.set(loaded_setting['is_mixer_mode'])
            self.mdx_batch_size_var.set(loaded_setting['mdx_batch_size'])
            self.mdx_voc_inst_secondary_model_var.set(loaded_setting['mdx_voc_inst_secondary_model'])
            self.mdx_other_secondary_model_var.set(loaded_setting['mdx_other_secondary_model'])
            self.mdx_bass_secondary_model_var.set(loaded_setting['mdx_bass_secondary_model'])
            self.mdx_drums_secondary_model_var.set(loaded_setting['mdx_drums_secondary_model'])
            self.mdx_is_secondary_model_activate_var.set(loaded_setting['mdx_is_secondary_model_activate'])
            self.mdx_voc_inst_secondary_model_scale_var.set(loaded_setting['mdx_voc_inst_secondary_model_scale'])
            self.mdx_other_secondary_model_scale_var.set(loaded_setting['mdx_other_secondary_model_scale'])
            self.mdx_bass_secondary_model_scale_var.set(loaded_setting['mdx_bass_secondary_model_scale'])
            self.mdx_drums_secondary_model_scale_var.set(loaded_setting['mdx_drums_secondary_model_scale'])
        
        if is_default_reset:
            self.is_save_all_outputs_ensemble_var.set(loaded_setting['is_save_all_outputs_ensemble'])
            self.is_append_ensemble_name_var.set(loaded_setting['is_append_ensemble_name'])
            self.choose_algorithm_var.set(loaded_setting['choose_algorithm'])
            self.time_stretch_rate_var.set(loaded_setting['time_stretch_rate'])
            self.pitch_rate_var.set(loaded_setting['pitch_rate'])#
            self.is_time_correction_var.set(loaded_setting['is_time_correction'])#
            self.is_primary_stem_only_var.set(loaded_setting['is_primary_stem_only'])
            self.is_secondary_stem_only_var.set(loaded_setting['is_secondary_stem_only'])
            self.is_testing_audio_var.set(loaded_setting['is_testing_audio'])#
            self.is_auto_update_model_params_var.set(loaded_setting['is_auto_update_model_params'])
            self.is_add_model_name_var.set(loaded_setting['is_add_model_name'])
            self.is_accept_any_input_var.set(loaded_setting["is_accept_any_input"])
            self.is_task_complete_var.set(loaded_setting['is_task_complete'])
            self.is_create_model_folder_var.set(loaded_setting['is_create_model_folder'])
            self.mp3_bit_set_var.set(loaded_setting['mp3_bit_set'])
            self.semitone_shift_var.set(loaded_setting['semitone_shift'])#
            self.save_format_var.set(loaded_setting['save_format'])
            self.wav_type_set_var.set(loaded_setting['wav_type_set'])#
            self.device_set_var.set(loaded_setting['device_set'])#
            self.user_code_var.set(loaded_setting['user_code'])
            self.phase_option_var.set(loaded_setting['phase_option'])#
            self.phase_shifts_var.set(loaded_setting['phase_shifts'])#
            self.is_save_align_var.set(loaded_setting['is_save_align'])#i
            self.time_window_var.set(loaded_setting['time_window'])#
            self.is_match_silence_var.set(loaded_setting['is_match_silence'])#
            self.is_spec_match_var.set(loaded_setting['is_spec_match'])#
            self.intro_analysis_var.set(loaded_setting['intro_analysis'])#
            self.db_analysis_var.set(loaded_setting['db_analysis'])#
            self.fileOneEntry_var.set(loaded_setting['fileOneEntry'])#
            self.fileOneEntry_Full_var.set(loaded_setting['fileOneEntry_Full'])#
            self.fileTwoEntry_var.set(loaded_setting['fileTwoEntry'])#
            self.fileTwoEntry_Full_var.set(loaded_setting['fileTwoEntry_Full'])#
            self.DualBatch_inputPaths = []
            
        self.is_gpu_conversion_var.set(loaded_setting['is_gpu_conversion'])
        self.is_normalization_var.set(loaded_setting['is_normalization'])#
        self.is_use_opencl_var.set(False)#True if is_opencl_only else loaded_setting['is_use_opencl'])#
        self.is_wav_ensemble_var.set(loaded_setting['is_wav_ensemble'])#
        self.help_hints_var.set(loaded_setting['help_hints_var'])
        self.is_wav_ensemble_var.set(loaded_setting['is_wav_ensemble'])
        self.set_vocal_splitter_var.set(loaded_setting['set_vocal_splitter'])
        self.is_set_vocal_splitter_var.set(loaded_setting['is_set_vocal_splitter'])#
        self.is_save_inst_set_vocal_splitter_var.set(loaded_setting['is_save_inst_set_vocal_splitter'])#
        self.deverb_vocal_opt_var.set(loaded_setting['deverb_vocal_opt'])#
        self.voc_split_save_opt_var.set(loaded_setting['voc_split_save_opt'])#
        self.is_deverb_vocals_var.set(loaded_setting['is_deverb_vocals'])#
        
        self.model_sample_mode_var.set(loaded_setting['model_sample_mode'])
        self.model_sample_mode_duration_var.set(loaded_setting['model_sample_mode_duration'])
        self.model_sample_mode_duration_checkbox_var.set(SAMPLE_MODE_CHECKBOX(self.model_sample_mode_duration_var.get()))
        self.model_sample_mode_duration_label_var.set(f'{self.model_sample_mode_duration_var.get()} Seconds')
              
    def save_values(self, app_close=True, is_restart=False, is_auto_save=False):
        """Saves application data"""

        # -Save Data-
        main_settings={
            'vr_model': self.vr_model_var.get(),
            'aggression_setting': self.aggression_setting_var.get(),
            'window_size': self.window_size_var.get(),
            'mdx_segment_size': self.mdx_segment_size_var.get(),
            'batch_size': self.batch_size_var.get(),
            'crop_size': self.crop_size_var.get(),
            'is_tta': self.is_tta_var.get(),
            'is_output_image': self.is_output_image_var.get(),
            'is_post_process': self.is_post_process_var.get(),
            'is_high_end_process': self.is_high_end_process_var.get(),
            'post_process_threshold': self.post_process_threshold_var.get(),
            'vr_voc_inst_secondary_model': self.vr_voc_inst_secondary_model_var.get(),
            'vr_other_secondary_model': self.vr_other_secondary_model_var.get(),
            'vr_bass_secondary_model': self.vr_bass_secondary_model_var.get(),
            'vr_drums_secondary_model': self.vr_drums_secondary_model_var.get(),
            'vr_is_secondary_model_activate': self.vr_is_secondary_model_activate_var.get(),
            'vr_voc_inst_secondary_model_scale': self.vr_voc_inst_secondary_model_scale_var.get(),
            'vr_other_secondary_model_scale': self.vr_other_secondary_model_scale_var.get(),
            'vr_bass_secondary_model_scale': self.vr_bass_secondary_model_scale_var.get(),
            'vr_drums_secondary_model_scale': self.vr_drums_secondary_model_scale_var.get(),
            'demucs_model': self.demucs_model_var.get(),
            'segment': self.segment_var.get(),
            'overlap': self.overlap_var.get(),
            'overlap_mdx': self.overlap_mdx_var.get(),
            'overlap_mdx23': self.overlap_mdx23_var.get(),
            'shifts': self.shifts_var.get(),
            'chunks_demucs': self.chunks_demucs_var.get(),
            'margin_demucs': self.margin_demucs_var.get(),
            'is_chunk_demucs': self.is_chunk_demucs_var.get(),
            'is_chunk_mdxnet': self.is_chunk_mdxnet_var.get(),
            'is_primary_stem_only_Demucs': self.is_primary_stem_only_Demucs_var.get(),
            'is_secondary_stem_only_Demucs': self.is_secondary_stem_only_Demucs_var.get(),
            'is_split_mode': self.is_split_mode_var.get(),
            'is_demucs_combine_stems': self.is_demucs_combine_stems_var.get(),#
            'is_mdx23_combine_stems': self.is_mdx23_combine_stems_var.get(),#
            'demucs_voc_inst_secondary_model': self.demucs_voc_inst_secondary_model_var.get(),
            'demucs_other_secondary_model': self.demucs_other_secondary_model_var.get(),
            'demucs_bass_secondary_model': self.demucs_bass_secondary_model_var.get(),
            'demucs_drums_secondary_model': self.demucs_drums_secondary_model_var.get(),
            'demucs_is_secondary_model_activate': self.demucs_is_secondary_model_activate_var.get(),
            'demucs_voc_inst_secondary_model_scale': self.demucs_voc_inst_secondary_model_scale_var.get(),
            'demucs_other_secondary_model_scale': self.demucs_other_secondary_model_scale_var.get(),
            'demucs_bass_secondary_model_scale': self.demucs_bass_secondary_model_scale_var.get(),
            'demucs_drums_secondary_model_scale': self.demucs_drums_secondary_model_scale_var.get(),
            'demucs_pre_proc_model': self.demucs_pre_proc_model_var.get(),
            'is_demucs_pre_proc_model_activate': self.is_demucs_pre_proc_model_activate_var.get(),
            'is_demucs_pre_proc_model_inst_mix': self.is_demucs_pre_proc_model_inst_mix_var.get(),
            'mdx_net_model': self.mdx_net_model_var.get(),
            'chunks': self.chunks_var.get(),
            'margin': self.margin_var.get(),
            'compensate': self.compensate_var.get(),
            'denoise_option': self.denoise_option_var.get(),#
            'is_match_frequency_pitch': self.is_match_frequency_pitch_var.get(),#
            'phase_option': self.phase_option_var.get(),#
            'phase_shifts': self.phase_shifts_var.get(),#
            'is_save_align': self.is_save_align_var.get(),#
            'is_match_silence': self.is_match_silence_var.get(),#
            'is_spec_match': self.is_spec_match_var.get(),#
            'is_mdx_c_seg_def': self.is_mdx_c_seg_def_var.get(),#
            'is_invert_spec': self.is_invert_spec_var.get(),#
            'is_deverb_vocals': self.is_deverb_vocals_var.get(),##, 
            'deverb_vocal_opt': self.deverb_vocal_opt_var.get(),#
            'voc_split_save_opt': self.voc_split_save_opt_var.get(),##, 
            'is_mixer_mode': self.is_mixer_mode_var.get(),
            'mdx_batch_size':self.mdx_batch_size_var.get(),
            'mdx_voc_inst_secondary_model': self.mdx_voc_inst_secondary_model_var.get(),
            'mdx_other_secondary_model': self.mdx_other_secondary_model_var.get(),
            'mdx_bass_secondary_model': self.mdx_bass_secondary_model_var.get(),
            'mdx_drums_secondary_model': self.mdx_drums_secondary_model_var.get(),
            'mdx_is_secondary_model_activate': self.mdx_is_secondary_model_activate_var.get(),
            'mdx_voc_inst_secondary_model_scale': self.mdx_voc_inst_secondary_model_scale_var.get(),
            'mdx_other_secondary_model_scale': self.mdx_other_secondary_model_scale_var.get(),
            'mdx_bass_secondary_model_scale': self.mdx_bass_secondary_model_scale_var.get(),
            'mdx_drums_secondary_model_scale': self.mdx_drums_secondary_model_scale_var.get(),
            'is_save_all_outputs_ensemble': self.is_save_all_outputs_ensemble_var.get(),
            'is_append_ensemble_name': self.is_append_ensemble_name_var.get(),
            'chosen_audio_tool': self.chosen_audio_tool_var.get(),
            'choose_algorithm': self.choose_algorithm_var.get(),
            'time_stretch_rate': self.time_stretch_rate_var.get(),
            'pitch_rate': self.pitch_rate_var.get(),#
            'is_time_correction': self.is_time_correction_var.get(),#
            'is_gpu_conversion': self.is_gpu_conversion_var.get(),
            'is_primary_stem_only': self.is_primary_stem_only_var.get(),
            'is_secondary_stem_only': self.is_secondary_stem_only_var.get(),
            'is_testing_audio': self.is_testing_audio_var.get(),#
            'is_auto_update_model_params': self.is_auto_update_model_params_var.get(),
            'is_add_model_name': self.is_add_model_name_var.get(),
            'is_accept_any_input': self.is_accept_any_input_var.get(),
            'is_task_complete': self.is_task_complete_var.get(),
            'is_normalization': self.is_normalization_var.get(),#
            'is_use_opencl': self.is_use_opencl_var.get(),#
            'is_wav_ensemble': self.is_wav_ensemble_var.get(),#
            'is_create_model_folder': self.is_create_model_folder_var.get(),
            'mp3_bit_set': self.mp3_bit_set_var.get(),
            'semitone_shift': self.semitone_shift_var.get(),#
            'save_format': self.save_format_var.get(),
            'wav_type_set': self.wav_type_set_var.get(),#
            'device_set': self.device_set_var.get(),#
            'user_code': self.user_code_var.get(),
            'help_hints_var': self.help_hints_var.get(),
            'set_vocal_splitter': self.set_vocal_splitter_var.get(),
            'is_set_vocal_splitter': self.is_set_vocal_splitter_var.get(),#
            'is_save_inst_set_vocal_splitter': self.is_save_inst_set_vocal_splitter_var.get(),#
            'model_sample_mode': self.model_sample_mode_var.get(),
            'model_sample_mode_duration': self.model_sample_mode_duration_var.get()
            }

        other_data = {
            'chosen_process_method': self.chosen_process_method_var.get(),
            'input_paths': self.inputPaths,
            'lastDir': self.lastDir,
            'export_path': self.export_path_var.get(),
            'time_window': self.time_window_var.get(),
            'intro_analysis': self.intro_analysis_var.get(),
            'db_analysis': self.db_analysis_var.get(),
            'fileOneEntry': self.fileOneEntry_var.get(),
            'fileOneEntry_Full': self.fileOneEntry_Full_var.get(),
            'fileTwoEntry': self.fileTwoEntry_var.get(),
            'fileTwoEntry_Full': self.fileTwoEntry_Full_var.get(),
            'DualBatch_inputPaths': self.DualBatch_inputPaths,
            #'model_hash_table': model_hash_table,
        }

        user_saved_extras = {
            'demucs_stems': self.demucs_stems_var.get(),
            'mdx_stems': self.mdxnet_stems_var.get()}

        persisted_settings = AppSettings.from_legacy_dict(
            {**main_settings, **other_data, **user_saved_extras},
            DEFAULT_DATA,
        )

        if app_close:
            persistence_helpers.save_settings(persisted_settings)
            
            if self.thread_check(self.active_download_thread):
                self.error_dialoge(EXIT_DOWNLOAD_ERROR)
                return

            if self.thread_check(self.active_processing_thread):
                if self.is_process_stopped: 
                    self.error_dialoge(EXIT_HALTED_PROCESS_ERROR)
                else:
                    self.error_dialoge(EXIT_PROCESS_ERROR)
                return
            
            remove_temps(ENSEMBLE_TEMP_PATH)
            remove_temps(SAMPLE_CLIP_PATH)
            self.delete_temps()
            
            if is_restart:
                try:
                    subprocess.Popen(f'UVR_Launcher.exe')
                except Exception:
                    subprocess.Popen(f'python "{__file__}"', shell=True)
            
            self.destroy()
            
        elif is_auto_save:
            persistence_helpers.save_settings(persisted_settings)
        else:
            return persisted_settings.to_legacy_dict()

    def get_settings_list(self):
        
        settings_dict = self.save_values(app_close=False)
        settings_list = '\n'.join(''.join(f"{key}: {value}") for key, value in settings_dict.items() if not key == 'user_code')

        return f"\n{FULL_APP_SET_TEXT}:\n\n{settings_list}"

def read_bulliten_text_mac(path, data):
    try:
        with open(path, 'w') as f:
            f.write(data)

        if os.path.isfile(path):
            with open(path, 'r') as file :
                data = file.read().replace("~", "•")
    except Exception as e:
        data = 'No information available.'

    return data

def open_link(event, link=None):
    webbrowser.open(link)

def auto_hyperlink(text_widget:tk.Text):
    content = text_widget.get('1.0', tk.END)
    
    # Regular expression to identify URLs
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)

    for url in urls:
        start_idx = content.find(url)
        end_idx = start_idx + len(url)
        
        # Convert indices to tk.Text widget format
        start_line = content.count('\n', 0, start_idx) + 1
        start_char = start_idx - content.rfind('\n', 0, start_idx) - 1
        end_line = content.count('\n', 0, end_idx) + 1
        end_char = end_idx - content.rfind('\n', 0, end_idx) - 1

        start_tag = f"{start_line}.{start_char}"
        end_tag = f"{end_line}.{end_char}"

        # Tag the hyperlink text and configure it
        text_widget.tag_add(url, start_tag, end_tag)
        text_widget.tag_configure(url, foreground=FG_COLOR, underline=True)
        text_widget.tag_bind(url, "<Button-1>", lambda e, link=url: open_link(e, link))
        text_widget.tag_bind(url, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
        text_widget.tag_bind(url, "<Leave>", lambda e: text_widget.config(cursor="arrow"))

def vip_downloads(password, link_type=VIP_REPO):
    """Attempts to decrypt VIP model link with given input code"""
    
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=link_type[0],
            iterations=390000,)

        key = base64.urlsafe_b64encode(kdf.derive(bytes(password, 'utf-8')))
        f = Fernet(key)

        return str(f.decrypt(link_type[1]), 'UTF-8')
    except Exception:
        return NO_CODE

def extract_stems(audio_file_base, export_path):
    
    filenames = [file for file in os.listdir(export_path) if file.startswith(audio_file_base)]

    pattern = r'\(([^()]+)\)(?=[^()]*\.wav)'
    stem_list = []

    for filename in filenames:
        match = re.search(pattern, filename)
        if match:
            stem_list.append(match.group(1))
            
    counter = Counter(stem_list)
    filtered_lst = [item for item in stem_list if counter[item] > 1]

    return list(set(filtered_lst))


system_helpers.configure_runtime(sys.modules[__name__])
tk_helpers_module.configure_runtime(sys.modules[__name__])
model_data_module.configure_runtime(sys.modules[__name__])
processing_service_module.configure_runtime(sys.modules[__name__])
ui_actions_module.configure_runtime(sys.modules[__name__])
ui_file_inputs_module.configure_runtime(sys.modules[__name__])
advanced_menus_module.configure_runtime(sys.modules[__name__])
common_menus_module.configure_runtime(sys.modules[__name__])
download_menus_module.configure_runtime(sys.modules[__name__])
input_menus_module.configure_runtime(sys.modules[__name__])
ensemble_module.configure_runtime(sys.modules[__name__])
audio_tools_module.configure_runtime(sys.modules[__name__])
widgets_module.configure_runtime(sys.modules[__name__])

save_data = persistence_helpers.save_data
load_data = persistence_helpers.load_data
get_execution_time = system_helpers.get_execution_time
right_click_release_linux = system_helpers.right_click_release_linux
close_process = system_helpers.close_process
extract_stems = system_helpers.extract_stems
drop = tk_helpers_module.drop
read_bulliten_text_mac = tk_helpers_module.read_bulliten_text_mac
open_link = tk_helpers_module.open_link
auto_hyperlink = tk_helpers_module.auto_hyperlink
vip_downloads = tk_helpers_module.vip_downloads
Ensembler = ensemble_module.Ensembler
AudioTools = audio_tools_module.AudioTools
ToolTip = widgets_module.ToolTip
ListboxBatchFrame = widgets_module.ListboxBatchFrame
ComboBoxEditableMenu = widgets_module.ComboBoxEditableMenu
ComboBoxMenu = widgets_module.ComboBoxMenu
ThreadSafeConsole = widgets_module.ThreadSafeConsole

if __name__ == "__main__":

    try:
        windll.user32.SetThreadDpiAwarenessContext(wintypes.HANDLE(-1))
    except Exception as e:
        if OPERATING_SYSTEM == 'Windows':
            print(e)
    
    root = MainWindow()
    root.update_checkbox_text()
    root.is_root_defined_var.set(True)
    root.is_check_splash = True

    root.update() if is_windows else root.update_idletasks()
    root.deiconify()
    root.configure(bg=BG_COLOR)
    root.mainloop()
