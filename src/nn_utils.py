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

Details:
NN dataset, dataloader, optimizer, loss function definitions.
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


def numpy_to_mat(data_in: np.array, path: str, name='data'):
    """save numpy vars to mat"""
    data = {name: data_in}
    sio.savemat(path, data)
