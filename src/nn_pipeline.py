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
2026.1.22      Yu Huang     1.1               Unet debug\n
2026.1.23-26   Yu Huang     1.2               Unet arch optimization\n

Details:
Training and inference pipeline of the Unet and DDIM model.
------------------------------------------------------------------------------------------------------------------------

"""
import logging
import torch
from torch import nn
import torch.nn.functional as nnf
import nn_utils
import numpy as np
from tqdm import tqdm
from torch.optim.lr_scheduler import CosineAnnealingLR, CosineAnnealingWarmRestarts

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
    optimizer = nn_utils.get_optimizer(unet.parameters(), lr=5e-4, weight_decay=1e-3)  # optimizer
    total_steps = (len(train_loader) // accumulation_steps) * epoch
    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=total_steps,
        eta_min=1e-5
    )
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
        for i, (samples, v_real) in process_bar:
            v_real_min = v_real.amin(dim=[2, 3], keepdim=True)  # get the input voltage's min value
            v_real_rel = (v_real - v_real_min) / (1.0 - v_real_min)  # get the case-wise normalization
            v_real_rel = v_real_rel.to(device)
            v_real_min = v_real_min.to(device)
            samples = samples.to(device)
            v_pred_rel, v_pred_min = unet(samples)

            loss1 = criterion(v_pred_rel, v_real_rel)  # get relative results' loss
            loss2 = criterion(v_real_min, v_pred_min)  # get V min's loss
            pred_grad_x, pred_grad_y = nn_utils.get_gradient(v_pred_rel)
            real_grad_x, real_grad_y = nn_utils.get_gradient(v_real_rel)
            grad_loss_x = nnf.smooth_l1_loss(pred_grad_x, real_grad_x, reduction='mean')
            grad_loss_y = nnf.smooth_l1_loss(pred_grad_y, real_grad_y, reduction='mean')
            loss3 = grad_loss_x + grad_loss_y  # get gradient's loss
            loss = 0.7 * loss1 + 0.3 * loss2 + 30.0 * loss3
            sys_log.info("loss1: %.4e, loss2: %.4e, loss3: %.4e",
                         loss1.detach(), loss2.detach(), loss3.detach())
            loss = loss / accumulation_steps  # scale to mean
            loss.backward()  # backward propagation
            if ((i + 1) % accumulation_steps == 0) or (i + 1 == len(train_loader)):
                optimizer.step()  # update weight
                scheduler.step()  # lr schedule
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
