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
2026.1.22      Yu Huang     1.1               Unet debug\n
2026.1.23-26   Yu Huang     1.2               Unet arch optimization\n
2026.1.27      Yu Huang     1.3               Unet Land implementation\n
2026.1.28      Yu Huang     1.4               Unet Land arch optimization\n

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
        self.conv1 = nn.Conv2d(in_channels=4, out_channels=32, kernel_size=3, stride=3, padding=0, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL2Encoder(nn.Module):
    """Unet Level-2 encoder"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=32, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL3Encoder(nn.Module):
    """Unet Level-3 encoder"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=128, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.conv2 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL4Bottleneck(nn.Module):
    """Unet Level-4 bottleneck"""
    def __init__(self):
        super().__init__()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.conv1 = nn.Conv2d(in_channels=512, out_channels=1024, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=32, num_channels=1024)
        self.conv2 = nn.Conv2d(in_channels=1024, out_channels=1024, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=32, num_channels=1024)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool1(x)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class VminExtractor(nn.Module):
    """Unet V min extractor"""
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels=1024, out_channels=256, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=16, num_channels=256)
        self.pool1 = nn.AdaptiveAvgPool2d((4, 4))
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(in_features=4096, out_features=64, bias=True)
        self.ln1 = nn.LayerNorm(64)
        self.fc2 = nn.Linear(in_features=64, out_features=1, bias=True)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.pool1(x)
        x = self.flatten(x)
        x = self.relu(self.ln1(self.fc1(x)))
        x = self.fc2(x)
        return x


class UnetL3Decoder(nn.Module):
    """Unet Level-3 decoder"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=1024, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.conv1 = nn.Conv2d(in_channels=1024, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.conv2 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL3DecoderNS(nn.Module):
    """Unet Level-3 decoder (No skip connection)"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=1024, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.conv1 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.conv2 = nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=32, num_channels=512)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL2Decoder(nn.Module):
    """Unet Level-2 decoder"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=512, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.conv1 = nn.Conv2d(in_channels=256, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL2DecoderNS(nn.Module):
    """Unet Level-2 decoder (No skip connection)"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=512, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.conv1 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.conv2 = nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=8, num_channels=128)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL1Decoder(nn.Module):
    """Unet Level-1 decoder"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=128, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.conv1 = nn.Conv2d(in_channels=64, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.relu = nn.ReLU()

    def forward(self, x_skip, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = torch.cat([x_skip, x], dim=1)
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL1DecoderNS(nn.Module):
    """Unet Level-1 decoder (No skip connection)"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=128, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn0 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.conv1 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn1 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1, dilation=1)
        self.gn2 = nn.GroupNorm(num_groups=4, num_channels=32)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.upsample(x)
        x = self.relu(self.gn0(self.conv0(x)))
        x = self.relu(self.gn1(self.conv1(x)))
        x = self.relu(self.gn2(self.conv2(x)))
        return x


class UnetL0Decoder(nn.Module):
    """Unet Level-0 decoder"""
    def __init__(self):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=3, mode='bilinear', align_corners=False)
        self.conv0 = nn.Conv2d(in_channels=32, out_channels=16, kernel_size=3, stride=1, padding=1, dilation=1)
        self.in0 = nn.InstanceNorm2d(num_features=16, momentum=0.1, affine=True)
        self.conv1 = nn.Conv2d(in_channels=16, out_channels=4, kernel_size=3, stride=1, padding=1, dilation=1)
        self.in1 = nn.InstanceNorm2d(num_features=4, momentum=0.1, affine=True)
        self.conv2 = nn.Conv2d(in_channels=4, out_channels=1, kernel_size=3, stride=1, padding=1, dilation=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.upsample(x)
        x = self.relu(self.in0(self.conv0(x)))
        x = self.relu(self.in1(self.conv1(x)))
        x = self.conv2(x)
        return x


class Unet(nn.Module):
    """Unet for IR drop end-to-end prediction"""

    def __init__(self):
        super().__init__()
        self.l1_encoder = UnetL1Encoder()
        self.l2_encoder = UnetL2Encoder()
        self.l3_encoder = UnetL3Encoder()
        self.l4_bottleneck = UnetL4Bottleneck()
        self.vmin_extractor = VminExtractor()
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
        y_min = self.vmin_extractor(x_bottleneck)
        y_min = y_min.unsqueeze(2).unsqueeze(3)
        # decoder
        y_dec3 = self.l3_decoder(x_enc3, x_bottleneck)
        y_dec2 = self.l2_decoder(x_enc2, y_dec3)
        y_dec1 = self.l1_decoder(x_enc1, y_dec2)
        y = self.l0_decoder(y_dec1)
        return y, y_min

    def initialize(self):
        """Initialize the prams of NN"""
        for name, m in self.named_modules():
            if isinstance(m, nn.Conv2d):
                if name == 'l0_decoder.conv2':
                    nn.init.xavier_uniform_(m.weight, gain=1.0)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.5)
                else:
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.ConvTranspose2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                if m is self.vmin_extractor.fc1:
                    nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.01)
                elif m is self.vmin_extractor.fc2:
                    nn.init.xavier_uniform_(m.weight, gain=1.0)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.5)
                else:
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
        sys_log.info("Unet params initialized")


class UnetLand(nn.Module):
    """Unet for IR drop landscape prediction"""

    def __init__(self):
        super().__init__()
        self.l1_encoder = UnetL1Encoder()
        self.l2_encoder = UnetL2Encoder()
        self.l3_encoder = UnetL3Encoder()
        self.l4_bottleneck = UnetL4Bottleneck()
        self.l3_decoder = UnetL3Decoder()
        self.l2_decoder = UnetL2DecoderNS()
        self.l1_decoder = UnetL1DecoderNS()
        self.l0_decoder = UnetL0Decoder()
        sys_log.info("UnetLand constructed")

    def forward(self, x):
        # encoder
        x_enc1 = self.l1_encoder(x)
        x_enc2 = self.l2_encoder(x_enc1)
        x_enc3 = self.l3_encoder(x_enc2)
        x_bottleneck = self.l4_bottleneck(x_enc3)
        # decoder
        y_dec3 = self.l3_decoder(x_enc3, x_bottleneck)
        y_dec2 = self.l2_decoder(y_dec3)
        y_dec1 = self.l1_decoder(y_dec2)
        y = self.l0_decoder(y_dec1)
        return y

    def initialize(self):
        """Initialize the prams of NN"""
        for name, m in self.named_modules():
            if isinstance(m, nn.Conv2d):
                if name == 'l0_decoder.conv2':
                    nn.init.xavier_uniform_(m.weight, gain=1.0)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.5)
                else:
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.ConvTranspose2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                if m is self.vmin_extractor.fc1:
                    nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.01)
                elif m is self.vmin_extractor.fc2:
                    nn.init.xavier_uniform_(m.weight, gain=1.0)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0.5)
                else:
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
        sys_log.info("UnetLand params initialized")
