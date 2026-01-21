# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.1.19\n
Description: Neural network definition

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.1.21      Yu Huang     1.0               First implementation\n

Details:
UNet and DDIM model definition script.
------------------------------------------------------------------------------------------------------------------------

"""
import logging
import torch
from torch import nn

sys_log = logging.getLogger('logger')


class UnetL1Encoder(nn.Module):
    """Unet Level-1 encoder"""
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels=5, out_channels=32, kernel_size=3, stride=3, padding=0, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL2Encoder(nn.Module):
    """Unet Level-2 encoder"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=32, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL3Encoder(nn.Module):
    """Unet Level-3 encoder"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=128, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL4Bottleneck(nn.Module):
    """Unet Level-4 bottleneck"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=512, out_channels=1024, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=1024, out_channels=1024, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL3Decoder(nn.Module):
    """Unet Level-3 decoder"""
    def __init__(self):
        super().__init__()
        self.up_conv1 = nn.ConvTranspose2d(in_channels=1024, out_channels=512, kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=1024, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.up_conv1(x)
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL2Decoder(nn.Module):
    """Unet Level-2 decoder"""
    def __init__(self):
        super().__init__()
        self.up_conv1 = nn.ConvTranspose2d(in_channels=512, out_channels=128, kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=256, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.up_conv1(x)
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL1Decoder(nn.Module):
    """Unet Level-1 decoder"""
    def __init__(self):
        super().__init__()
        self.up_conv1 = nn.ConvTranspose2d(in_channels=128, out_channels=32, kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=64, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.up_conv1(x)
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x


class UnetL0Decoder(nn.Module):
    """Unet Level-0 decoder"""
    def __init__(self):
        super().__init__()
        self.up_conv1 = nn.ConvTranspose2d(in_channels=32, out_channels=16, kernel_size=3, stride=3, padding=0)
        self.conv1 = nn.Conv2d(in_channels=16, out_channels=4, kernel_size=3, stride=1, padding=1, dilation=1)
        self.conv2 = nn.Conv2d(in_channels=4, out_channels=1, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.up_conv1(x)
        x = self.relu(self.conv1(x))
        x = self.sigmoid(self.conv2(x))
        return x


class Unet(nn.Module):
    """Unet structure"""

    def __init__(self):
        super().__init__()
        self.l1_encoder = UnetL1Encoder()
        self.l2_encoder = UnetL2Encoder()
        self.l3_encoder = UnetL3Encoder()
        self.l4_bottleneck = UnetL4Bottleneck()
        self.l3_decoder = UnetL3Decoder()
        self.l2_decoder = UnetL2Decoder()
        self.l1_decoder = UnetL1Decoder()
        self.l0_decoder = UnetL0Decoder()
        sys_log.info("Unet constructed")

    def forward(self, x):
        # encoder
        x_enc1 = self.l1_encoder(x)
        x_enc2 = self.l2_encoder(x_enc1)
        x_enc3 = self.l3_encoder(x_enc2)
        x_bottleneck = self.l4_bottleneck(x_enc3)
        # decoder
        y_dec3 = self.l3_decoder(x_enc3, x_bottleneck)
        y_dec2 = self.l2_decoder(x_enc2, y_dec3)
        y_dec1 = self.l1_decoder(x_enc1, y_dec2)
        y = self.l0_decoder(y_dec1)
        return y

    def initialize(self):
        """Initialize the prams of NN"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d) or isinstance(m, nn.ConvTranspose2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
        sys_log.info("Unet params initialized")
