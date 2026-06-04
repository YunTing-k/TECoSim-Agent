# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.27
Description: TECoSim Simulator support

Revision:
---------
2026.5.27      Yu Huang      1.0      First implementation

Details:
---------
TypedDict definitions for all simulator configuration files: RunConfig (paths, CUDA device), ModelParamConfig (4 pixel circuit
models with hysteresis/LUT params), PanelParamConfig (physical/electrical/thermal/PDN params), HeatFluxConfig, HeatContactConfig,
PdnInjectionConfig, SimulationParamConfig (solver, display, encoding, probing). Also provides stdout/stderr log cleaning
utilities for TOOL_NAME_READ_LOG tool.
"""
import re
import logging

from typing import TypedDict

sys_log = logging.getLogger('logger')


class RunConfig(TypedDict):
    """Configuration for simulation run (run.json)."""
    video_in_path: str
    video_out_path: str
    data_path: str
    cuda_device: int


class ModelParamConfig(TypedDict):
    """Pixel circuit model parameters (model_param.json)."""
    model: int
    nominal_temp: float

    # Model 1
    m1_imax: float
    m1_elvdd: float
    m1_elvss: float
    m1_coeff_b: float
    m1_coeff_c: float
    m1_T0: float
    m1_r_eff: float
    m1_g_eff: float
    m1_b_eff: float
    m1_cap: float

    # Model 2
    m2_imax: float
    m2_elvdd: float
    m2_elvss: float
    m2_coeff_b: float
    m2_coeff_c: float
    m2_T0: float
    m2_r_eff: float
    m2_g_eff: float
    m2_b_eff: float
    m2_cap: float

    # Model 3
    m3_elvdd: float
    m3_elvss: float
    m3_a: float
    m3_b: float
    m3_c: float
    m3_d: float
    m3_T0: float
    m3_Vss: float
    m3_k: float
    m3_m: float
    m3_W: float
    m3_L: float
    m3_cap: float
    m3h1_tao_c0: float
    m3h1_tao_e0: float
    m3h1_coeff1: float
    m3h1_coeff2: float
    m3h1_stable_t: float
    m3h1_cap: float

    # Model 4
    m4_elvdd: float
    m4_elvss: float
    m4_beta0: float
    m4_beta1: float
    m4_beta2: float
    m4_beta3: float
    m4_beta4: float
    m4_beta5: float
    m4_beta6: float
    m4_n: float
    m4_Vth0: float
    m4_betaVth: float
    m4_Ea: float
    m4_kBq: float
    m4_T0: float
    m4_miu0: float
    m4_miumean: float
    m4_gamma: float
    m4_Vmean: float
    m4_Vstd: float
    m4_alphasat: float
    m4_lambda: float
    m4_cap: float
    m4h1_tao_c0: float
    m4h1_tao_e0: float
    m4h1_c0: float
    m4h1_e0: float
    m4h1_a: float
    m4h1_b: float
    m4h1_Nt: float
    m4h1_NtA0: float
    m4h1_cNtA: float
    m4h1_stable_t: float
    m4h1_cap: float

    # LUTs
    r_lut: list[float]
    g_lut: list[float]
    b_lut: list[float]


class PanelParamConfig(TypedDict):
    """Panel physical and electrical parameters (panel_param.json)."""
    p_width: int
    p_height: int
    p_fresh_rate: int
    rf_type: int
    p_size_w: float
    p_size_h: float
    p_size_t: float
    th_kx: float
    th_ky: float
    th_kz: float
    th_c: float
    th_rho: float
    th_h: float
    th_medium_t: float
    extra_hflux: bool
    extra_hcontact: bool
    pdn_type: int
    rx: float
    ry: float
    cx: float
    cy: float
    ring_rx: float
    ring_ry: float
    ring_cx: float
    ring_cy: float


class HeatFluxConfig(TypedDict):
    """External heat flux boundary condition (heat_flux.json)."""
    amount: int
    row: list[int]
    col: list[int]
    source: list[float]


class HeatContactConfig(TypedDict):
    """External heat contact boundary condition (heat_contact.json)."""
    amount: int
    row: list[int]
    col: list[int]
    temp: list[float]
    th_conduct: list[float]


class PdnInjectionConfig(TypedDict):
    """PDN current injection sources (pdn_injection.json)."""
    amount: int
    row: list[int]
    col: list[int]
    voltage: list[float]
    glb_r: list[float]


class SimulationParamConfig(TypedDict):
    """Simulation control and numerical parameters (simulation_param.json)."""
    print_timing_info: bool
    max_frame_num: int
    max_threads: int
    use_cuda: bool
    couple_type: int
    tran_method: int
    tran_itr_steps: int
    ini_temp: float
    te_eval_loss: bool
    te_solver_type: int
    te_order_type: int
    te_solver_tol: float
    te_solver_max_itr_steps: int
    ini_vol: float
    ird_fix_i_omp: bool
    ird_eval_loss: bool
    ird_solver_type: int
    ird_order_type: int
    ird_solver_tol: float
    ird_solver_max_itr_steps: int
    ird_max_itr_steps: int
    ird_itr_tol: float
    ird_guess_stg: int
    ird_v_guess: float
    ird_coeff_stg: int
    ird_coeff_start: float
    ird_coeff_end: float
    ird_exp: float
    display_gamma: float
    visual_gamma: float
    inseq_format: int
    inframe_sp_gap: int
    outseq_format: int
    outframe_sp_gap: int
    probe_temp: bool
    probe_v: bool
    temp_sp_gap: int
    save_te_error: bool
    v_sp_gap: int
    save_ird_error: bool
    current_sp_gap: int
    dvth_sp_gap: int
    qm_type: int
    qm_sp_gap: int
    bit_rate: int
    rc_max_rate: int
    rc_min_rate: int
    rc_buffer_size: int
    gop_size: int
    max_b_frames: int
    thread_count: int


def clean_stdout_log(content: str) -> list[str]:
    """remove the redundancy in the input stdout log str"""
    pattern = re.compile(r'\[(debug|info|warning|error)]', re.IGNORECASE)
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        if not line.strip():
            continue
        if "print_start_banner" in line:
            continue
        if "print_end_banner" in line:
            continue
        if "print_error_banner" in line:
            continue
        if "print_abort_banner" in line:
            continue
        match = pattern.search(line)
        if match:
            start = match.start()
            line = line[start:]
        cleaned_lines.append(line)
    # return "\n".join(cleaned_lines)
    return cleaned_lines


def clean_stderr_log(content: str) -> list[str]:
    """remove the redundancy in the input stderr log str"""
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        if not line.strip():
            continue
        if "libx264 @" in line:
            continue
        if "psnr @" in line:
            continue
        if "ssim @" in line:
            continue
        if "vmaf @" in line:
            continue
        if "std::cerr abort_banner" in line:
            continue
        cleaned_lines.append(line)
    # return "\n".join(cleaned_lines)
    return cleaned_lines
