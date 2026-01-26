# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.19\n
Description: Neural network utilities definition

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.21      Yu Huang     1.0               First implementation\n
2026.1.22      Yu Huang     1.1               Unet debug\n
2026.1.22      Yu Huang     1.2               PDN generator & dumper realization\n
2026.1.23-26   Yu Huang     1.3               Unet arch optimization\n

Details:
NN dataset, dataloader, optimizer, loss function definitions and other utilities such as PDN generator and dumper.
------------------------------------------------------------------------------------------------------------------------

"""
import logging
import sys
import h5py
import numpy as np
import torch
import torch.optim as optim
from torch import nn
from torch.utils.data import Dataset
import scipy.io as sio
from torch.optim.optimizer import ParamsT

sys_log = logging.getLogger('logger')


class IRDropDataset(Dataset):
    """IR Drop dataset"""
    def __init__(self, path: str, hdf5_config: dict[str, any], transform=None, target_transform=None):
        self.h5_file = h5py.File(path, 'r', **hdf5_config)
        self.pdn_idx = torch.from_numpy(np.array(self.h5_file['pdn_idx']))
        self.frame_idx = torch.from_numpy(np.array(self.h5_file['frame_idx']))
        self.img = torch.from_numpy(np.array(self.h5_file['img']))
        self.dmap = torch.from_numpy(np.array(self.h5_file['dmap']))
        self.vdata = self.h5_file['vdata']
        self.transform = transform
        self.target_transform = target_transform
        self.len = self.vdata.shape[0]

    def __getitem__(self, index):
        voltage = torch.from_numpy(self.vdata[index]).unsqueeze(dim=0)
        img = self.img[self.frame_idx[index]]
        dmap = self.dmap[self.pdn_idx[index]].unsqueeze(dim=0)
        sample = torch.cat([img, dmap], dim=0)
        # sample = torch.zeros((4, 1080, 1920), dtype=torch.float32)  # test for dataloader bottleneck
        return sample, voltage

    def __len__(self):
        return self.len


def get_gradient(tensor: torch.Tensor):
    """Get the gradient of input tensor"""
    sobel_x = torch.tensor([[-1, 0, 1],
                            [-2, 0, 2],
                            [-1, 0, 1]], dtype=tensor.dtype).view(1, 1, 3, 3)
    sobel_y = torch.tensor([[-1, -2, -1],
                            [0, 0, 0],
                            [1, 2, 1]], dtype=tensor.dtype).view(1, 1, 3, 3)

    grad_x = torch.nn.functional.conv2d(tensor, sobel_x.to(tensor.device), padding=1)
    grad_y = torch.nn.functional.conv2d(tensor, sobel_y.to(tensor.device), padding=1)
    return grad_x, grad_y


def get_dataset(path: str, hdf5_config: dict[str, any], transform=None, target_transform=None):
    """Get dataset from path and hdf5 configs"""
    try:
        dataset = IRDropDataset(path=path, hdf5_config=hdf5_config,
                                transform=transform, target_transform=target_transform)
        sys_log.info("Get dataset from path: %s and hdf5 configs: %s", path, str(hdf5_config))
    except Exception as err:
        sys_log.error("Get dataset with path of %s failed with error %s", path, str(err))
        sys.exit(0)
    return dataset


def get_dataloader(dataset: Dataset, batch_size: int, shuffle: bool, num_workers: int):
    """Get dataloader and config"""
    data_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers,
                                              pin_memory=True)
    sys_log.info('Get dataloader with batch size: %d, shuffle: %s, worker num: %d',
                 batch_size, str(shuffle), num_workers)
    return data_loader


def get_optimizer(net_params: ParamsT, lr=0.001, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0, amsgrad=False):
    """Get adam optimizer"""
    optimizer = optim.AdamW(net_params, lr=lr, betas=betas, eps=eps, weight_decay=weight_decay, amsgrad=amsgrad)
    sys_log.info('Optimizer prepared with lr: %.3e, betas: (%.3e, %.3e), eps: %.3e, weight_decay: %.3e, amsgrad: %s',
                 lr, betas[0], betas[1], eps, weight_decay, str(amsgrad))
    return optimizer


def get_loss_function(loss_type='MSELoss'):
    """Get loss function"""
    if loss_type == 'CrossEntropyLoss':
        criterion = nn.CrossEntropyLoss()
    elif loss_type == 'L1Loss':
        criterion = nn.L1Loss()
    elif loss_type == 'MSELoss':
        criterion = nn.MSELoss()
    elif loss_type == 'NLLLoss':
        criterion = nn.NLLLoss()
    elif loss_type == 'SmoothL1Loss':
        criterion = nn.SmoothL1Loss()
    else:
        criterion = nn.MSELoss()
        sys_log.warning('Unknown target loss function,loss function is allocated as MSELoss')
    sys_log.info('Get loss function: %s', loss_type)
    return criterion


def numpy_to_mat(data_in: np.ndarray, path: str, name='data'):
    """save numpy vars to mat"""
    data = {name: data_in}
    sio.savemat(path, data)


def gen_pdn(sel: int, p_height: int, p_width: int, min_seg_num: int, max_seg_num: int, pdn_voltage: float):
    """Gen PDN with given params, specific to edge-only"""
    edge_sel = f'{sel:0{4}b}'  # select code of edge [0]->[Left, Right, Top, Down]<-[3]
    seg_num_arr = [0, 0, 0, 0]  # segment amount of edge [Left, Right, Top, Down]
    seg_len_arr = [0, 0, 0, 0]  # segment length of edge [Left, Right, Top, Down]
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
    return seg_num_arr, seg_len_arr, amount, pdn_row, pdn_col, pdn_vol


def dump_pdn(file_path: str, column: int, precision: int, amount: int,
             pdn_row: np.ndarray, pdn_col: np.ndarray, pdn_vol: np.ndarray):
    """Dump the PDN into json file without json lib"""
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
