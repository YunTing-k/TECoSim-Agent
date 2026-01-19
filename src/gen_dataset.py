# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.16\n
Description: Script of generating raw data of IR Drop diffusion model

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.16-17   Yu Huang     1.0               First implementation\n

Details:
Generate PDN cases and run the simulator with the generated configs, then move/copy the data to the target folder
------------------------------------------------------------------------------------------------------------------------

"""
import os
import sys
import shutil
import subprocess
import sys_logger
import numpy as np

sys_log = sys_logger.Logger('gen_dataset').logger  # logger

if __name__ == '__main__':
    sys_log.debug('Program start')

    # config params
    random_seed = 42
    np.random.seed(random_seed)
    p_width = 1920
    p_height = 1080
    pdn_voltage = 5.0
    frame_num = 100  # frame of simulation
    min_seg_num = 1  # min segments of single edge
    max_seg_num = 5  # max segments of single edge
    max_gen_time = 8  # max generate times of each case
    pdn_num = max_gen_time * 15  # total amount of PDN cases
    column = 8  # max columns of json objects
    precision = 1  # digits precision of json dump
    simulator_path = 'C:/Users/12416/Desktop/C++File/Project/TECoSim'  # path of TECoSim simulator
    rawdata_path = '../raw_data'  # path of raw raw_data set
    skip_pdn_gen = True
    pdn_start = 1  # the start index of PDN case simulation (1 as the first one)
    pdn_end = 10  # the end index of PDN case simulation (1 as the first one)

    # print params
    sys_log.param('random_seed: %d', random_seed)
    sys_log.param('panel width: %d', p_width)
    sys_log.param('panel height: %d', p_height)
    sys_log.param('PDN voltage: %f', pdn_voltage)
    sys_log.param('Frame of simulation: %d', frame_num)
    sys_log.param('minimum~maximum segments of single edge: %d~%d', min_seg_num, max_seg_num)
    sys_log.param('maximum generate times of each PDN case: %d', max_gen_time)
    sys_log.param('total amount of PDN cases: %d', pdn_num)
    sys_log.param('max columns of json objects: %d', column)
    sys_log.param('digits precision of json dump: %d', precision)
    sys_log.param('path of TECoSim simulator: %s', simulator_path)
    sys_log.param('path of raw dataset: %s', rawdata_path)
    sys_log.param('skip the generation of PDN: %s', str(skip_pdn_gen))
    sys_log.param('start index of PDN case simulation: %d', pdn_start)
    sys_log.param('end index of PDN case simulation: %d', pdn_end)
    if pdn_start > pdn_num:
        sys_log.error('Start case index is larger than all cases amount')
        sys.exit(0)
    if pdn_end > pdn_num:
        sys_log.error('End case index is larger than all cases amount')
        sys.exit(0)
    if pdn_start > pdn_end:
        sys_log.error('Start case index is larger than end case index')
        sys.exit(0)

    # generation of PDN
    pdn_idx = 1
    seg_num_arr = [0, 0, 0, 0]  # segment amount of edge [Left, Right, Top, Down]
    seg_len_arr = [0, 0, 0, 0]  # segment length of edge [Left, Right, Top, Down]
    if not skip_pdn_gen:
        for i in range(16):  # 15 case of all edges combination
            if i == 0: continue
            edge_sel = f'{i:0{4}b}'  # select code of edge [0]->[Left, Right, Top, Down]<-[3]
            # generate `max_gen_time` times
            for j in range(max_gen_time):
                # left edge is selected
                if edge_sel[0] == '1':
                    seg_num = np.random.randint(min_seg_num, max_seg_num + 1, 1)
                    seg_edge = np.random.choice(p_height, size=2 * seg_num, replace=False)
                    seg_edge.sort()
                    row_left = None
                    for k in range(seg_num[0]):
                        if k == 0:
                            row_left = np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                   num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                   endpoint=True, dtype=np.int32)
                        else:
                            row_left = np.hstack((row_left, np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                                        num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                                        endpoint=True, dtype=np.int32)))
                    col_left = np.zeros((1, row_left.size), dtype=np.int32)
                    col_left = col_left[0]
                    seg_num_arr[0] = seg_num[0]
                    seg_len_arr[0] = row_left.size
                else:
                    row_left = None
                    col_left = None
                    seg_num_arr[0] = 0
                    seg_len_arr[0] = 0

                # right edge is selected
                if edge_sel[1] == '1':
                    seg_num = np.random.randint(min_seg_num, max_seg_num + 1, 1)
                    seg_edge = np.random.choice(p_height, size=2 * seg_num, replace=False)
                    seg_edge.sort()
                    row_right = None
                    for k in range(seg_num[0]):
                        if k == 0:
                            row_right = np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                    num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                    endpoint=True, dtype=np.int32)
                        else:
                            row_right = np.hstack(
                                (row_right, np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                        num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                        endpoint=True, dtype=np.int32)))
                    col_right = np.zeros((1, row_right.size), dtype=np.int32) + p_width - 1
                    col_right = col_right[0]
                    seg_num_arr[1] = seg_num[0]
                    seg_len_arr[1] = row_right.size
                else:
                    row_right = None
                    col_right = None
                    seg_num_arr[1] = 0
                    seg_len_arr[1] = 0

                # Top edge is selected
                if edge_sel[2] == '1':
                    seg_num = np.random.randint(min_seg_num, max_seg_num + 1, 1)
                    seg_edge = np.random.choice(p_width, size=2 * seg_num, replace=False)
                    seg_edge.sort()
                    col_top = None
                    for k in range(seg_num[0]):
                        if k == 0:
                            col_top = np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                  num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                  endpoint=True, dtype=np.int32)
                        else:
                            col_top = np.hstack((col_top, np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                                      num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                                      endpoint=True, dtype=np.int32)))
                    row_top = np.zeros((1, col_top.size), dtype=np.int32)
                    row_top = row_top[0]
                    seg_num_arr[2] = seg_num[0]
                    seg_len_arr[2] = col_top.size
                else:
                    row_top = None
                    col_top = None
                    seg_num_arr[2] = 0
                    seg_len_arr[2] = 0

                # Down edge is selected
                if edge_sel[3] == '1':
                    seg_num = np.random.randint(min_seg_num, max_seg_num + 1, 1)
                    seg_edge = np.random.choice(p_width, size=2 * seg_num, replace=False)
                    seg_edge.sort()
                    col_down = None
                    for k in range(seg_num[0]):
                        if k == 0:
                            col_down = np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                   num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                   endpoint=True, dtype=np.int32)
                        else:
                            col_down = np.hstack((col_down, np.linspace(start=seg_edge[2 * k], stop=seg_edge[2 * k + 1],
                                                                        num=seg_edge[2 * k + 1] - seg_edge[2 * k] + 1,
                                                                        endpoint=True, dtype=np.int32)))
                    row_down = np.zeros((1, col_down.size), dtype=np.int32) + p_height - 1
                    row_down = row_down[0]
                    seg_num_arr[3] = seg_num[0]
                    seg_len_arr[3] = col_down.size
                else:
                    row_down = None
                    col_down = None
                    seg_num_arr[3] = 0
                    seg_len_arr[3] = 0

                # merge arrays
                pdn_row = np.hstack([x for x in [row_left, row_right, row_top, row_down] if x is not None])
                pdn_col = np.hstack([y for y in [col_left, col_right, col_top, col_down] if y is not None])
                pdn_vol = np.zeros((1, pdn_row.size), dtype=np.float32) + pdn_voltage
                pdn_vol = pdn_vol[0]
                amount = pdn_row.size
                if pdn_row.size != pdn_col.size:
                    sys_log.error("Unmatched row with %d elements and col with %d elements", pdn_row.size, pdn_col.size)
                    sys.exit(0)
                if sum(seg_len_arr) != pdn_row.size:
                    sys_log.error("Unmatched sum of segments with %d elements and row with %d elements",
                                  sum(seg_len_arr), pdn_row.size)
                    sys.exit(0)

                # Export to json (without using json library)
                file_path = '../pdn/pdn_injection' + str(pdn_idx) + '.json'
                with open(file_path, "w") as fid:
                    fid.write('{\n    "amount": %d,\n' % amount)
                    # Export row
                    cur_col = 1
                    fid.write('    "row": [')
                    for ii in range(amount):
                        if cur_col > column:
                            cur_col = 1
                            fid.write("\n    ")
                        if ii != amount - 1:
                            fid.write('%d, ' % int(pdn_row[ii]))
                        else:
                            fid.write('%d],\n' % int(pdn_row[ii]))
                        cur_col += 1

                    # Export col
                    cur_col = 1
                    fid.write('    "col": [')
                    for ii in range(amount):
                        if cur_col > column:
                            cur_col = 1
                            fid.write("\n    ")
                        if ii != amount - 1:
                            fid.write('%d, ' % int(pdn_col[ii]))
                        else:
                            fid.write('%d],\n' % int(pdn_col[ii]))
                        cur_col += 1

                    # Export voltage
                    cur_col = 1
                    fid.write('    "voltage": [')
                    for ii in range(amount):
                        if cur_col > column:
                            cur_col = 1
                            fid.write("\n    ")
                        if ii != amount - 1:
                            fid.write('%.{}e, '.format(precision) % pdn_vol[ii])
                        else:
                            fid.write('%.{}e]\n'.format(precision) % pdn_vol[ii])
                        cur_col += 1
                    fid.write('}\n')

                sys_log.info("PDN case-%d --> "
                             "left: %d-seg %d-len | right: %d-seg %d-len | "
                             "up: %d-seg %d-len | down: %d-seg %d-len | "
                             "total: %d-seg %d-len",
                             pdn_idx, seg_num_arr[0], seg_len_arr[0],
                             seg_num_arr[1], seg_len_arr[1],
                             seg_num_arr[2], seg_len_arr[2],
                             seg_num_arr[3], seg_len_arr[3],
                             sum(seg_num_arr), sum(seg_len_arr))
                pdn_idx = pdn_idx + 1
        sys_log.debug("PDN generation done")
    else:
        sys_log.debug("PDN generation skipped")

    # TECoSim simulation and raw_data gathering
    target_config_path = simulator_path + '/config/pdn_injection.json'
    for i in range(pdn_num):
        # skip cases
        if (i + 1) < pdn_start:
            sys_log.debug("PDN case-%d skipped", i + 1)
            continue
        # remove json file
        try:
            os.remove(target_config_path)
            sys_log.debug("PDN case-%d --> json file %s removed", i + 1, target_config_path)
        except Exception as err:
            sys_log.error("Remove file %s failed with error %s", target_config_path, str(err))
            sys.exit(0)
        # copy json to config
        source_config_path = '../pdn/pdn_injection' + str(i + 1) + '.json'
        try:
            shutil.copy(source_config_path, target_config_path)
            sys_log.debug("PDN case-%d --> copy json file from %s to %s", i + 1, source_config_path, target_config_path)
        except Exception as err:
            sys_log.error("Copy json file from %s to %s failed with error %s",
                          source_config_path, target_config_path, str(err))
            sys.exit(0)
        # simulation
        sys_log.debug("PDN case-%d --> simulation start", i + 1)
        result = subprocess.run([simulator_path + '/TECoSim.exe', simulator_path + '/config/'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0:
            sys_log.error("Simulator terminated with error")
            sys.exit(0)
        else:
            sys_log.debug("PDN case-%d --> simulation done", i + 1)
        # create sub raw_data folder
        sub_rawdata_path = rawdata_path + '/pdn' + str(i + 1) + '/'
        try:
            os.makedirs(os.path.dirname(sub_rawdata_path), exist_ok=True)
        except Exception as err:
            sys_log.error("Create sub rawdata folder %s failed with error %s",
                          sub_rawdata_path, str(err))
            sys.exit(0)
        # copy log file
        log_files = [f for f in os.listdir('./logs/') if f.endswith('.txt')]
        log_files_sorted = sorted(log_files, key=lambda x: os.path.getmtime(os.path.join('./logs/', x)), reverse=True)
        log_file = './logs/' + log_files_sorted[0]
        try:
            shutil.copy(log_file, sub_rawdata_path + log_files_sorted[0])
            sys_log.debug("PDN case-%d --> copy log file from %s to %s",
                          i + 1, log_file, sub_rawdata_path + log_files_sorted[0])
        except Exception as err:
            sys_log.error("Copy log file from %s to %s failed with error %s",
                          log_file, sub_rawdata_path + log_files_sorted[0], str(err))
            sys.exit(0)
        # copy config files
        try:
            shutil.copytree(src=simulator_path + '/config', dst=sub_rawdata_path + 'config')
            sys_log.debug("PDN case-%d --> copy config files from %s to %s",
                          i + 1, simulator_path + '/config', sub_rawdata_path + 'config')
        except Exception as err:
            sys_log.error("Copy config files from %s to %s failed with error %s",
                          simulator_path + '/config', sub_rawdata_path + 'config', str(err))
            sys.exit(0)
        # move output frame
        file_amount = len([f for f in os.listdir(simulator_path + '/data/frame_output')
                           if os.path.isfile(os.path.join(simulator_path + '/data/frame_output', f))])
        if file_amount != frame_num:
            sys_log.error("Unmatched file amount %d to target of %d", file_amount, frame_num)
            sys.exit(0)
        try:
            shutil.move(src=simulator_path + '/data/frame_output', dst=sub_rawdata_path + 'frame_output')
            sys_log.debug("PDN case-%d --> move output frames from %s to %s",
                          i + 1, simulator_path + '/data/frame_output', sub_rawdata_path + 'frame_output')
        except Exception as err:
            sys_log.error("Move output frames from %s to %s failed with error %s",
                          simulator_path + '/data/frame_output', sub_rawdata_path + 'frame_output', str(err))
            sys.exit(0)
        # move voltage
        file_amount = len([f for f in os.listdir(simulator_path + '/data/voltage')
                           if os.path.isfile(os.path.join(simulator_path + '/data/voltage', f))])
        if file_amount != (frame_num + 1):
            sys_log.error("Unmatched file amount %d to target of %d", file_amount, frame_num)
            sys.exit(0)
        try:
            shutil.move(src=simulator_path + '/data/voltage', dst=sub_rawdata_path + 'voltage')
            sys_log.debug("PDN case-%d --> move PDN voltage files from %s to %s",
                          i + 1, simulator_path + '/data/voltage', sub_rawdata_path + 'voltage')
        except Exception as err:
            sys_log.error("Move PDN voltage files from %s to %s failed with error %s",
                          simulator_path + '/data/voltage', sub_rawdata_path + 'voltage', str(err))
            sys.exit(0)
        # move quality metric
        try:
            shutil.move(src=simulator_path + '/data/quality_metric', dst=sub_rawdata_path + 'quality_metric')
            sys_log.debug("PDN case-%d --> move quality metric file from %s to %s",
                          i + 1, simulator_path + '/data/quality_metric', sub_rawdata_path + 'quality_metric')
        except Exception as err:
            sys_log.error("Move quality metric file from %s to %s failed with error %s",
                          simulator_path + '/data/quality_metric', sub_rawdata_path + 'quality_metric', str(err))
            sys.exit(0)
        # move timing
        try:
            shutil.move(src=simulator_path + '/data/timing', dst=sub_rawdata_path + 'timing')
            sys_log.debug("PDN case-%d --> move simulator timing file from %s to %s",
                          i + 1, simulator_path + '/data/timing', sub_rawdata_path + 'timing')
        except Exception as err:
            sys_log.error("Move simulator timing file from %s to %s failed with error %s",
                          simulator_path + '/data/timing', sub_rawdata_path + 'timing', str(err))
            sys.exit(0)
        sys_log.info("PDN case-%d --> concluded", i + 1)
        if (i + 1) >= pdn_end:
            break

    sys_log.debug('Program end')
