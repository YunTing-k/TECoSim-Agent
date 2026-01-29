# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.27\n
Description: UnetLand pipeline realization

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.27      Yu Huang     1.0               First implementation\n
2026.1.28      Yu Huang     1.1               Debug output process\n
2026.1.29      Yu Huang     1.2               Batch test update\n

Details:
Training and inference pipeline instance of the Unet Landscape model.
------------------------------------------------------------------------------------------------------------------------

"""
import json
import os
import shutil
import subprocess
import sys
import time
import torch
import numpy as np
import sys_logger
import nn_model
import nn_utils
import nn_pipeline
import skimage.io as img_sio
import scipy.io as mat_io
from scipy.ndimage import distance_transform_edt as d_tran

sys_log = sys_logger.Logger(os.path.basename(__file__)[0:-3]).logger  # logger

if __name__ == '__main__':
    sys_log.debug('Program start')

    # config params (train NN)
    device = 'cuda:0'
    skip_train = False
    skip_test = False
    test_train = False
    skip_simulation = True
    dataset_path = '../data/dataset32B.h5'
    hdf5_config = {
        'rdcc_nslots': 1601,
        'rdcc_nbytes': 4 * 1024 * 1024 * 1024,
        'rdcc_w0': 1.0,
        'libver': 'latest',
        'locking': False,
        'swmr': False
    }

    # create NN
    try:
        unetland = nn_model.UnetLand().to(device)
        sys_log.info("UnetLand created and send to device %s", device)
    except Exception as err:
        sys_log.error("UnetLand create failed with error %s", str(err))
        sys.exit(0)

    # train NN
    if not skip_train:
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
        torch.set_float32_matmul_precision('high')
        unetland = torch.compile(unetland)
        nn_pipeline.unetland_train(unetland=unetland, path=dataset_path, hdf5_config=hdf5_config,
                                   train_batch=5, epoch=5, device=device, accumulation_steps=1, epoch_save=True,
                                   update_count=1)
        torch.save(unetland.state_dict(), '../model/unetland.pth')
    else:
        torch.set_float32_matmul_precision('high')
        unetland = torch.compile(unetland)
        unetland.load_state_dict(torch.load('../model/unetland.pth'))
        sys_log.info('Read UnetLand weights from file')

    # test NN
    if not skip_test:
        # config params (test NN)
        random_seed = 24
        np.random.seed(random_seed)
        p_width = 1920
        p_height = 1080
        pdn_voltage = 5.0
        min_seg_num = 1  # min segments of single edge
        max_seg_num = 5  # max segments of single edge
        column = 8  # max columns of json objects
        precision = 1  # digits precision of json dump
        simulator_path = 'D:/TECoSimDev'  # path of TECoSim simulator
        frame_idx = [19]  # index of test frame (start from one, for OOD test)
        case_idx = [20]  # index of case (start from zero, for dataset test)
        if not test_train:
            test_len = len(frame_idx)
        else:
            test_len = len(case_idx)

        target_config_path = simulator_path + '/config/pdn_injection.json'
        for i in range(test_len):
            if not test_train:
                sys_log.info("Test with OOD")
                if not skip_simulation:
                    edge_sel = int(np.random.randint(low=1, high=16, size=1)[0])
                    seg_num_arr, seg_len_arr, amount, pdn_row, pdn_col, pdn_vol = (
                        nn_utils.gen_pdn(sel=edge_sel, p_height=p_height, p_width=p_width,
                                         min_seg_num=min_seg_num, max_seg_num=max_seg_num, pdn_voltage=pdn_voltage))
                    sys_log.info("PDN test case --> "
                                 "left: %d-seg %d-len | right: %d-seg %d-len | "
                                 "up: %d-seg %d-len | down: %d-seg %d-len | "
                                 "total: %d-seg %d-len",
                                 seg_num_arr[0], seg_len_arr[0],
                                 seg_num_arr[1], seg_len_arr[1],
                                 seg_num_arr[2], seg_len_arr[2],
                                 seg_num_arr[3], seg_len_arr[3],
                                 sum(seg_num_arr), sum(seg_len_arr))
                    # Export to json (without using json library)
                    file_path = '../pdn/pdn_injection_test.json'
                    nn_utils.dump_pdn(file_path=file_path, column=column, precision=precision, amount=amount,
                                      pdn_row=pdn_row, pdn_col=pdn_col, pdn_vol=pdn_vol)

                    # remove json file
                    try:
                        os.remove(target_config_path)
                        sys_log.debug("PDN test case --> json file %s removed", target_config_path)
                    except Exception as err:
                        sys_log.error("Remove file %s failed with error %s", target_config_path, str(err))
                        sys.exit(0)
                    # copy json to config
                    source_config_path = '../pdn/pdn_injection_test.json'
                    try:
                        shutil.copy(source_config_path, target_config_path)
                        sys_log.debug("PDN test case --> copy json file from %s to %s", source_config_path,
                                      target_config_path)
                    except Exception as err:
                        sys_log.error("Copy json file from %s to %s failed with error %s",
                                      source_config_path, target_config_path, str(err))
                        sys.exit(0)
                    # simulation
                    sys_log.debug("PDN test case --> simulation start")
                    result = subprocess.run([simulator_path + '/TECoSim.exe', simulator_path + '/config/'],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if result.returncode != 0:
                        sys_log.error("Simulator terminated with error")
                        sys.exit(0)
                    else:
                        sys_log.debug("PDN test case --> simulation done")
                else:
                    sys_log.info("Simulation skipped")

                # read the json
                with open(target_config_path, 'r', encoding='utf-8') as jf:
                    jdata = json.load(jf)
                    amount = jdata['amount']
                    inj_row = np.array(jdata['row'])
                    inj_col = np.array(jdata['col'])
                    if inj_row.size != amount or inj_col.size != amount:
                        raise Exception("Unmatched row and col of injection point")
                # get the dmap
                max_dist = np.sqrt((p_height - 1) ** 2 + (p_width - 1) ** 2)
                bin_map = np.zeros((p_height, p_width), dtype=np.int32)
                bin_map[inj_row, inj_col] = 1
                dmap_slice = np.array(d_tran(1 - bin_map)) / max_dist
                dmap_slice = dmap_slice.astype(np.float32)  # [H W]
                # get the img
                img_path = simulator_path + '/data/frame_input/frame_' + str(frame_idx[i]) + '.png'
                img_raw = np.array(img_sio.imread(img_path))
                img_slice = img_raw.astype(np.float32) / 255.0
                img_slice = img_slice.transpose(2, 0, 1)  # [C H W]
                # get the vdata
                vdata_path = simulator_path + '/data/voltage/V_' + str(frame_idx[i]) + '.bin'
                raw_vdata = np.fromfile(vdata_path, dtype=np.float64)
                raw_vdata = raw_vdata.reshape((p_height, p_width))
                vdata_slice = raw_vdata.astype(np.float32) / pdn_voltage  # [H W]
            else:
                sys_log.info("Test with dataset")
                train_set = nn_utils.get_dataset(path=dataset_path, hdf5_config=hdf5_config)
                sample, voltage = train_set.__getitem__(case_idx[i])
                img_slice = sample[0:3, :, :].squeeze().numpy()
                dmap_slice = sample[3, :, :].squeeze().numpy()
                vdata_slice = voltage.squeeze().numpy()
                inj_row, inj_col = np.where(dmap_slice == 0)

            # get the prediction by NN
            unetland.eval()  # toggle inference mode
            with torch.no_grad():
                img_slice_ = torch.from_numpy(img_slice).unsqueeze(0)
                dmap_slice_ = torch.from_numpy(dmap_slice).unsqueeze(0).unsqueeze(0)
                vdata_slice_ = torch.from_numpy(vdata_slice).unsqueeze(0).unsqueeze(0)
                nn_input = torch.cat([img_slice_, dmap_slice_], dim=1).to(device)
                t = time.perf_counter_ns()
                nn_v = unetland(nn_input)
                t = time.perf_counter_ns() - t
            v_real_min = vdata_slice_.amin(dim=[2, 3], keepdim=True)  # get the input voltage's min value
            v_real_rel = (vdata_slice_ - v_real_min) / (1.0 - v_real_min)  # [N C H W]
            v_real_rel = v_real_rel.numpy()
            v_real_rel = np.squeeze(v_real_rel)  # [H W]
            v_pred_rel = nn_v.cpu()
            v_pred_rel = v_pred_rel.numpy()
            v_pred_rel = np.squeeze(v_pred_rel)  # [H W]
            verr = v_real_rel - v_pred_rel
            max_err = np.max(np.abs(verr))
            avg_err = np.mean(np.abs(verr))
            sys_log.info("Max error: %.4e, average error: %.4e, time: %.4f ms", max_err, avg_err, 1e-6 * t)
            data = {'inj_row': inj_row,
                    'inj_col': inj_col,
                    'dmap_slice': dmap_slice,
                    'img_slice': img_slice,
                    'v_real_relative': v_real_rel,
                    'v_predict_relative': v_pred_rel,
                    'v_err': verr}
            if not test_train:
                mat_io.savemat('../test/unetland_test_OOD' + str(frame_idx[i]) + '.mat', data)
                sys_log.info("OOD test with frame %d done", frame_idx[i])
            else:
                mat_io.savemat('../test/unetland_test_IOD' + str(case_idx[i]) + '.mat', data)
                sys_log.info("IOD test with case %d done", case_idx[i])
    else:
        sys_log.info('UnetLand test skipped')

    sys_log.debug('Program end')
