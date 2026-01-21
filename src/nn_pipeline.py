# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.19\n
Description: Neural network pipeline realization

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.21      Yu Huang     1.0               First implementation\n

Details:
Training and inference pipeline of the Unet and DDIM model.
------------------------------------------------------------------------------------------------------------------------

"""
import logging
import torch
from torch import nn
import nn_utils
import numpy as np
from tqdm import tqdm
from torch.profiler import profile, record_function, ProfilerActivity

sys_log = logging.getLogger('logger')


def unet_train(unet: nn.Module, path: str, hdf5_config: dict[str, any], train_batch: int,
               epoch=60, device='cuda:0', accumulation_steps=1, epoch_save=True, update_count=20):
    """Train the Unet"""
    """get the dataset and data loader"""
    train_set = nn_utils.get_dataset(path=path, hdf5_config=hdf5_config)
    train_loader = nn_utils.get_dataloader(dataset=train_set, batch_size=train_batch, shuffle=False, num_workers=0)
    if train_set.len % train_batch != 0:
        sys_log.warning("Mismatched train batch %d with train dataset length %d",
                        train_batch, train_set.len)
    """loss array"""
    train_loss_array = np.zeros((epoch, int(train_set.len / train_batch)))  # train loss array
    """loss function and optimizer"""
    criterion = nn_utils.get_loss_function('MSELoss')  # loss function
    optimizer = nn_utils.get_optimizer(unet.parameters(), lr=1e-4, weight_decay=0.01)  # optimizer
    unet.initialize()  # initialize nn
    unet.train()  # toggle train mode

    sys_log.info('Unet training start')
    if len(train_loader) % accumulation_steps != 0:
        sys_log.warning("Mismatched accumulation steps %d with train loader length %d",
                        accumulation_steps, len(train_loader))
    for epoch in range(epoch):  # train
        unet.train()
        optimizer.zero_grad()
        process_bar = tqdm(enumerate(train_loader), total=len(train_loader),
                           desc='Unet Training', leave=True, unit='batch')
        for i, (samples) in process_bar:
            samples_ = samples.to(device)
            outputs = unet(samples_)
            targets = samples[:, 0, :, :].unsqueeze(1).to(device)
            loss = criterion(outputs, targets)  # get loss
            loss = loss / accumulation_steps  # scale to mean
            loss.backward()  # backward propagation
            if ((i + 1) % accumulation_steps == 0) or (i + 1 == len(train_loader)):
                optimizer.step()  # update weight
                optimizer.zero_grad()
            train_loss_array[epoch, i] = loss.item() * accumulation_steps
            if i % update_count == update_count - 1:  # update loss with gap of update_count
                process_bar.set_postfix(loss=loss.item() * accumulation_steps, epoch=epoch + 1, iteration=i + 1)
        process_bar.close()
        if epoch_save:
            torch.save(unet.state_dict(), '../model/unet' + str(epoch) + '.pth')
    """save results"""
    nn_utils.numpy_to_mat(train_loss_array, '../model/unet_train_loss.mat')
    sys_log.info('Unet training done')
