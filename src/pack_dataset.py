# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.19\n
Description: Script of pack the raw data of IR Drop deep learning

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.19      Yu Huang     1.0               First implementation\n

Details:
Pack the raw data of IR Drop diffusion model, including images, voltage and distance map. They will be normalized and
pre-shuffled into float32 data. Images will preload into the memory, another frame index and PDN index will indicate the
current sample's frame and PDN.
------------------------------------------------------------------------------------------------------------------------

"""
import json
import os
import sys
import sys_logger
import h5py
import skimage.io as sio
from scipy.ndimage import distance_transform_edt as d_tran
import numpy as np
from tqdm import tqdm

sys_log = sys_logger.Logger(os.path.basename(__file__)[0:-3]).logger  # logger

if __name__ == '__main__':
    sys_log.debug('Program start')

    # config params
    random_seed = 42
    np.random.seed(random_seed)
    p_width = 1920
    p_height = 1080
    pdn_voltage = 5.0
    frame_num = 100  # frame of simulation
    pdn_num = 120  # total amount of PDN cases
    total_num = pdn_num * frame_num  # total amount of samples
    rawdata_path = '../raw_data'  # path of raw raw_data set
    data_path = '../data'  # path of raw raw_data set
    chunk_size = 32  # chunk size of dataset

    # print params
    sys_log.param('random_seed: %d', random_seed)
    sys_log.param('panel width: %d', p_width)
    sys_log.param('panel height: %d', p_height)
    sys_log.param('PDN voltage: %f', pdn_voltage)
    sys_log.param('Frame of simulation: %d', frame_num)
    sys_log.param('total amount of PDN cases: %d', pdn_num)
    sys_log.param('total amount of samples: %d', total_num)
    sys_log.param('path of raw dataset: %s', rawdata_path)
    sys_log.param('path of dataset: %s', data_path)
    sys_log.param('chunk size of dataset: %d', chunk_size)

    # generate the pre-shuffle sequence (start from 0)
    shuffle_idx = np.random.choice(total_num, size=total_num, replace=False)
    pdn_idx = np.zeros((1, total_num), dtype=np.int32)[0]
    frame_idx = np.zeros((1, total_num), dtype=np.int32)[0]

    # create HDF5 dataset
    sys_log.info("Dataset packing start")
    with h5py.File(data_path + '/dataset.h5', 'w') as f:
        # pack the images
        sys_log.debug("Frame packing start")
        img_dset = f.create_dataset(
            name='img',
            shape=(frame_num, 3, p_height, p_width),
            dtype=np.float32,
            compression='lzf',
            shuffle=True
        )
        process_bar = tqdm(range(frame_num), total=frame_num, desc='Frame Packing', leave=True, unit='frame', ncols=100)
        for i in process_bar:
            try:
                img_path = rawdata_path + '/frame_input/frame_' + str(i+1) + '.png'
                img_raw = np.array(sio.imread(img_path))
                img_slice = img_raw.astype(np.float32) / 255.0
                img_slice = img_slice.transpose(2, 0, 1)
                f['img'][i] = img_slice
            except Exception as err:
                sys_log.error("Read and write img %s failed with error %s", img_path, str(err))
                sys.exit(0)
        sys_log.debug("Frame packing done")

        # pack the voltage with pre-shuffle
        sys_log.debug("Voltage packing start")
        vdata_dset = f.create_dataset(
            name='vdata',
            shape=(total_num, p_height, p_width),
            dtype=np.float32,
            chunks=(chunk_size, p_height, p_width),
        )
        process_bar = tqdm(range(total_num), total=total_num, desc='Vdata Packing', leave=True, unit='Vdata', ncols=100)
        for i in process_bar:
            try:
                pdn_idx_ = shuffle_idx[i] // frame_num  # index of PDN start from zero
                frame_idx_ = shuffle_idx[i] - pdn_idx_ * frame_num  # index of frame start from zero
                pdn_idx[i] = pdn_idx_
                frame_idx[i] = frame_idx_
                vdata_path = rawdata_path + '/pdn' + str(pdn_idx_+1) + '/voltage/V_' + str(frame_idx_+1) + '.bin'
                raw_vdata = np.fromfile(vdata_path, dtype=np.float64)
                raw_vdata = raw_vdata.reshape((p_height, p_width))
                vdata_slice = raw_vdata.astype(np.float32) / pdn_voltage
                f['vdata'][i] = vdata_slice
            except Exception as err:
                sys_log.error("Read and write voltage %s failed with error %s", vdata_path, str(err))
                sys.exit(0)
        sys_log.debug("Voltage packing done")

        # get the distance map and pack it
        sys_log.debug("Distance map packing start")
        max_dist = np.sqrt((p_height - 1) ** 2 + (p_width - 1) ** 2)
        dmap_dset = f.create_dataset(
            name='dmap',
            shape=(pdn_num, p_height, p_width),
            dtype=np.float32,
            compression='lzf',
            shuffle=True
        )
        process_bar = tqdm(range(pdn_num), total=pdn_num, desc='Distance Map Packing', leave=True, unit='Dmap', ncols=100)
        for i in process_bar:
            try:
                pdn_path = rawdata_path + '/pdn' + str(i+1) + '/config/pdn_injection.json'
                with open(pdn_path, 'r', encoding='utf-8') as jf:
                    jdata = json.load(jf)
                    amount = jdata['amount']
                    inj_row = np.array(jdata['row'])
                    inj_col = np.array(jdata['col'])
                    if inj_row.size != amount or inj_col.size != amount:
                        raise Exception("Unmatched row and col of injection point")
                bin_map = np.zeros((p_height, p_width), dtype=np.int32)
                bin_map[inj_row, inj_col] = 1
                dmap_slice = np.array(d_tran(1 - bin_map)) / max_dist
                dmap_slice = dmap_slice.astype(np.float32)
                f['dmap'][i] = dmap_slice
            except Exception as err:
                sys_log.error("Read and write PDN injection distance map %s failed with error %s", pdn_path, str(err))
                sys.exit(0)
        sys_log.debug("Distance map packing done")

        # shuffle index export
        sys_log.debug("Shuffle index exporting start")
        pdn_idx_dset = f.create_dataset(
            name='pdn_idx',
            data=pdn_idx,
            shape=(total_num,),
            dtype=np.int32,
        )
        frame_idx_dset = f.create_dataset(
            name='frame_idx',
            data=frame_idx,
            shape=(total_num,),
            dtype=np.int32,
        )
        sys_log.debug("Shuffle index exporting done")
        sys_log.info("Dataset packing done")
    sys_log.debug('Program end')
