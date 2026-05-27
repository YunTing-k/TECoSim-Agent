# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.27\n
Description: File filter support

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.27      Yu Huang     1.0               First implementation\n

Details:
Support of file filter with grep and glob
------------------------------------------------------------------------------------------------------------------------
"""
import os
import glob
import logging
import subprocess

from typing import Any

sys_log = logging.getLogger('logger')


def glob_impl(arguments: dict[str, Any]) -> tuple[str, bool, str]:
    """glob implementation with glob lib"""
    pattern = arguments.get("pattern")
    if not pattern:
        return "", False, "Required parameter `pattern` is missing or empty"

    # full glob pattern
    root = str(arguments.get("path", os.getcwd()))
    try:
        full_pattern = os.path.join(root, str(pattern))
    except Exception as e:
        return "", False, f"Assemble full glob pattern with `pattern`: {pattern} failed with error: {e}"

    # recursive match
    try:
        matched_paths = glob.glob(full_pattern, recursive=True)
        file_paths = [p for p in matched_paths if os.path.isfile(p)]
        if len(file_paths) != 0:
            file_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return "\n".join(file_paths), True, "SUCCESS"
        else:
            return "(No matches found)", True, "SUCCESS"
    except Exception as e:
        return "", False, f"Recursive match with `pattern`: {pattern} failed with error: {e}"


def grep_impl(arguments: dict[str, Any], timeout: int) -> tuple[str, bool, str]:
    """grep implementation with ripgrep (rg)"""
    pattern = arguments.get("pattern")
    if not pattern:
        return "", False, "Required parameter `pattern` is missing or empty"

    """get prams"""
    path = arguments.get("path", os.getcwd())
    glob_filter = arguments.get("glob")
    file_type = arguments.get("type")
    output_mode = arguments.get("output_mode", "files_with_matches")
    ignore_case = arguments.get("ignore_case", False)
    context_val = arguments.get("context")
    head_limit = arguments.get("head_limit", 250)
    multiline = arguments.get("multiline", False)

    """build rg cmd"""
    cmd = ["rg", "--color", "never"]

    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    elif output_mode == "content":
        cmd.append("--line-number")
        if context_val is not None:
            cmd.extend(["-C", str(context_val)])
    else:
        return "", False, f"Unsupported `output_mode`: {output_mode}"

    if ignore_case:
        cmd.append("-i")
    if multiline:
        cmd.extend(["--multiline", "--multiline-dotall"])
    if glob_filter is not None:
        cmd.extend(["--glob", str(glob_filter)])
    if file_type:
        cmd.extend(["--type", str(file_type)])

    cmd.append(str(pattern))
    cmd.append(path)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    """rg operation"""
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except FileNotFoundError:
        return "", False, "ripgrep (rg) is not installed"
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        return "", False, "ripgrep is cancelled by user. Command interrupted"
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        return "", False, (f"ripgrep is timeout > {timeout} s.\n"
                           f"return code: {proc.returncode}\n"
                           f"stdout: {stdout}\n"
                           f"stderr: {stderr}\n")
    except Exception as e:
        proc.terminate()
        try:
            proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        return "", False, f"ripgrep failed with error: {e}"

    # rg return code: 0=match found，1=no match，>1=error
    if proc.returncode == 1:
        return "(No matches found)", True, "SUCCESS"
    if proc.returncode >= 2:
        proc.terminate()
        try:
            proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        return "", False, f"ripgrep failed with return code {proc.returncode}\nstderr: {stderr}\nstdout: {stdout}"

    """post-process"""
    output = stdout
    if head_limit == 0:  # 0 unlimited
        return output, True, "SUCCESS"

    lines = output.splitlines()
    if len(lines) > head_limit:
        truncated = lines[:head_limit]
        return "\n".join(truncated) + f"\n(... truncated {len(lines) - head_limit} lines)", True, "SUCCESS"
    else:
        return output, True, "SUCCESS"
