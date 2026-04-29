# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.19\n
Description: Simple test script of the packed HDF5 dataset of IR Drop deep learning simulation agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.19      Yu Huang     1.0               First implementation\n
2026.1.19      Yu Huang     1.1               Add HDF5 cache config\n

Details:
Test the packed HDF5 dataset, read the images, voltage, distance map and shuffle index.
------------------------------------------------------------------------------------------------------------------------

"""
import os
import sys
import time
import sys_logger
import h5py
import matplotlib.pyplot as plt
import numpy as np

sys_log = sys_logger.Logger(os.path.basename(__file__)[0:-3]).logger  # logger

if __name__ == '__main__':
    sys_log.debug('Program start')

    # config params
    random_seed = 42
    np.random.seed(random_seed)
    p_width = 1920
    p_height = 1080
    frame_num = 100  # frame of simulation
    pdn_num = 120  # total amount of PDN cases
    total_num = pdn_num * frame_num  # total amount of samples
    data_path = '../data/dataset32.h5'  # path of raw raw_data set
    check_index = 43  # the index of the shuffled sample among total_num samples (start from zero)
    read_size = 256  # size of chunk read test

    # print params
    sys_log.param('random_seed: %d', random_seed)
    sys_log.param('panel width: %d', p_width)
    sys_log.param('panel height: %d', p_height)
    sys_log.param('Frame of simulation: %d', frame_num)
    sys_log.param('total amount of PDN cases: %d', pdn_num)
    sys_log.param('total amount of samples: %d', total_num)
    sys_log.param('path of dataset: %s', data_path)
    sys_log.param('index of the checked sample: %d', check_index)
    if check_index >= total_num:
        sys_log.error('Index of the checked sample is larger than all cases amount')
        sys.exit(0)
    sys_log.param('size of chunk read test: %d', read_size)
    if read_size >= total_num:
        sys_log.error('Size of chunk read test is larger than all cases amount')
        sys.exit(0)

    # get index
    shuffle_idx = np.random.choice(total_num, size=total_num, replace=False)
    case_idx = shuffle_idx[check_index]  # actual index before shuffle start from zero
    pdn_idx1 = shuffle_idx[check_index] // frame_num  # index of PDN start from zero
    frame_idx1 = shuffle_idx[check_index] - pdn_idx1 * frame_num  # index of frame start from zero
    sys_log.debug("Index-%d, Case-%d (shuffled), PDN Case-%d, Frame Idx-%d check test start",
                  check_index + 1, case_idx + 1, pdn_idx1 + 1, frame_idx1 + 1)

    # config HDF5
    cache_config = {
        'rdcc_nslots': 1601,
        'rdcc_nbytes': 4 * 1024 * 1024 * 1024,
        'rdcc_w0': 1.0,
        'libver': 'latest',
        'locking': False,
        'swmr': False
    }
    h5_file = h5py.File(data_path, 'r', **cache_config)

    # read PDN index
    t = time.perf_counter_ns()
    pdn_idx = np.array(h5_file['pdn_idx'])
    t = time.perf_counter_ns() - t
    pdn_idx2 = pdn_idx[check_index]
    sys_log.debug("Read PDN index to memory, time=%.4f ms" % (t * 1e-6))
    sys_log.debug("shape=%s, dtype=%s", str(pdn_idx.shape), str(pdn_idx.dtype))
    if pdn_idx1 != pdn_idx2:
        sys_log.error("Unmatched PDN index of target %d and source %d", pdn_idx1 + 1, pdn_idx2 + 1)
    else:
        sys_log.info("Matched PDN index of target %d and source %d", pdn_idx1 + 1, pdn_idx2 + 1)

    # read frame index
    t = time.perf_counter_ns()
    frame_idx = np.array(h5_file['frame_idx'])
    frame_idx2 = frame_idx[check_index]
    t = time.perf_counter_ns() - t
    sys_log.debug("Read frame index to memory, time=%.4f ms" % (t * 1e-6))
    sys_log.debug("shape=%s, dtype=%s", str(frame_idx.shape), str(frame_idx.dtype))
    if frame_idx1 != frame_idx2:
        sys_log.error("Unmatched frame index of target %d and source %d", frame_idx1 + 1, frame_idx2 + 1)
    else:
        sys_log.info("Matched frame index of target %d and source %d", frame_idx1 + 1, frame_idx2 + 1)

    # read all image
    t = time.perf_counter_ns()
    img = np.array(h5_file['img'])
    t = time.perf_counter_ns() - t
    sys_log.debug("Read all images to memory, time=%.4f ms" % (t * 1e-6))
    sys_log.debug("All images shape=%s, dtype=%s", str(img.shape), str(img.dtype))

    # display frame (display delayed)
    img_slice = img[frame_idx1, :, :, :]
    img_slice = img_slice.transpose(1, 2, 0)
    plt.figure(1)
    plt.imshow(img_slice)
    plt.title(f'Frame {frame_idx1+1} (RGB)')
    plt.axis('off')

    # read voltage
    t = time.perf_counter_ns()
    vdata = h5_file['vdata']
    t = time.perf_counter_ns() - t
    sys_log.debug("Vdata handel assignment, time=%.4f ms" % (t * 1e-6))

    t = time.perf_counter_ns()
    vdata_slice = vdata[check_index]  # get the shuffled vdata with check_index
    t = time.perf_counter_ns() - t
    sys_log.debug("First Vdata slice-%d read (HDF5 file), time=%.4f ms" % (check_index + 1, t * 1e-6))

    # read from bin
    vdata_slice.tofile('test.bin')
    t = time.perf_counter_ns()
    vdata_slice = np.fromfile('test.bin', dtype=np.float32)
    vdata_slice = vdata_slice.reshape((p_height, p_width))
    t = time.perf_counter_ns() - t
    sys_log.debug("First Vdata slice-%d read (raw file), time=%.4f ms" % (check_index + 1, t * 1e-6))
    os.remove('test.bin')

    # display voltage (display delayed)
    edge_sel = f'{(int(pdn_idx1) // 8 + 1):0{4}b}'
    plt.figure(2)
    plt.imshow(vdata_slice, cmap='viridis', aspect='auto')
    plt.title(f'Vdata {check_index + 1} L:{edge_sel[0]} R:{edge_sel[1]} U:{edge_sel[2]} D:{edge_sel[3]}')
    plt.axis('off')

    # voltage chunk test
    t_total = 0
    read_total = 0
    for i in range(read_size):
        if check_index + i + 1 < total_num:
            t = time.perf_counter_ns()
            vdata_slice_ = vdata[check_index + i + 1]
            t = time.perf_counter_ns() - t
            t_total = t_total + t
            read_total = read_total + 1
            sys_log.debug("Vdata slice-%d read, time=%.4f ms" % (check_index + i + 2, t * 1e-6))
    if read_total != 0:
        sys_log.info("Chunk test with avg. time of %.4f ms", t_total * 1e-6 / read_total)

    t = time.perf_counter_ns()
    vdata_slice_ = vdata[-1]
    t = time.perf_counter_ns() - t
    sys_log.debug("Last Vdata slice-%d read, time=%.4f ms" % (total_num, t * 1e-6))

    # read all distance map
    t = time.perf_counter_ns()
    dmap = np.array(h5_file['dmap'])
    t = time.perf_counter_ns() - t
    sys_log.debug("Read all distance map to memory, time=%.4f ms" % (t * 1e-6))
    sys_log.debug("All distance map shape=%s, dtype=%s", str(dmap.shape), str(dmap.dtype))

    # display distance map (display delayed)
    dmap_slice = dmap[pdn_idx1]
    plt.figure(3)
    plt.imshow(dmap_slice, cmap='hot', aspect='auto')
    plt.title(f'PDN {pdn_idx1 + 1} L:{edge_sel[0]} R:{edge_sel[1]} U:{edge_sel[2]} D:{edge_sel[3]}')
    plt.axis('off')

    # display all figs
    plt.show(block=True)

    sys_log.debug('Program end')
