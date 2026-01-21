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
import os
import sys
import torch
import sys_logger
import nn_model
import nn_pipeline

sys_log = sys_logger.Logger(os.path.basename(__file__)[0:-3]).logger  # logger

if __name__ == '__main__':
    sys_log.debug('Program start')

    # config params
    device = 'cuda:0'
    skip_train = False
    dataset_path = '../data/dataset32.h5'
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
        unet = nn_model.Unet().to(device)
        sys_log.info("Unet created and send to device %s", device)
    except Exception as err:
        sys_log.error("Unet create failed with error %s", str(err))
        sys.exit(0)

    # train NN
    if not skip_train:
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
        unet = torch.compile(unet)
        nn_pipeline.unet_train(unet=unet, path=dataset_path, hdf5_config=hdf5_config,
                               train_batch=6, epoch=5, device=device, accumulation_steps=5, epoch_save=True, update_count=1)
        torch.save(unet.state_dict(), '../model/unet.pth')
    else:
        unet.load_state_dict(torch.load('../model/unet.pth'))
        sys_log.info('Read FPN weights from file')

    sys_log.debug('Program end')
