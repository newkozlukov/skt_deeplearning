import torch
import numpy as np
import math


def make_conv(
        in_features, out_features, kernel_size,
        stride=1,
        drop_rate=0.,
        padding=1):
    layers = [
            torch.nn.BatchNorm2d(in_features),
            torch.nn.ReLU(),
    ]
    if drop_rate > 0:
        layers.append(torch.nn.Dropout(drop_rate))
    layers.append(
            torch.nn.Conv2d(
                in_features,
                out_features,
                kernel_size=kernel_size,
                stride=stride,
                padding=padding,
                ),
    )
    return torch.nn.Sequential(*layers)


class Immersion(torch.nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride, padding):
        super(Immersion, self).__init__()
        if isinstance(kernel_size, int):
            kernel_size = (kernel_size,)*2
        self.register_buffer('weight', torch.ones(out_channels, in_channels, *kernel_size))
        self.weight.div_(in_channels*kernel_size[0]*kernel_size[1])
        self.weight.requires_grad_(False)
        self.stride = stride
        self.padding = padding
    def forward(self, input):
        assert not hasattr(self.weight, 'grad') or self.weight.grad is None
        return torch.conv2d(input, self.weight, stride=self.stride, padding=self.padding)

class ResBlock(torch.nn.Module):
    def __init__(self, in_features, out_features, stride, drop_rate):
        """`B(?, ?)` from `https://arxiv.org/pdf/1605.07146.pdf`"""
        super(ResBlock, self).__init__()
        self.residual = torch.nn.Sequential(
            make_conv(in_features, out_features, 3, stride=stride, drop_rate=0.),
            make_conv(
                out_features, out_features, 1,
                padding=0,
                drop_rate=drop_rate),
        )
        self.shortcut = Immersion(
                in_features, out_features,
                kernel_size=1,
                stride=stride,
                padding=0)
    def forward(self, input):
        return self.shortcut.forward(input) + self.residual.forward(input)

class Flatten(torch.nn.Module):
    def forward(self, input):
        return torch.flatten(input, start_dim=1)

def make_wideresnet(
        n_classes, layers_per_stage,
        apooling_cls,
        apooling_output_size,
        widen_factor=3, drop_rate=.2):
    layers = [ torch.nn.Conv2d(3, 16*widen_factor, 1) ]
    for stride in [1, 2, 3]:
        in_channels, out_channels = 2**(3 + stride)*widen_factor, 2**(4 + stride)*widen_factor
        layers += [ ResBlock(in_channels, out_channels, stride, drop_rate) ]
        for i in range(1, layers_per_stage):
            layers += [ ResBlock(out_channels, out_channels, 1, drop_rate) ]
    layers += [
            torch.nn.BatchNorm2d(out_channels),
            torch.nn.ReLU(),
            torch.nn.Conv2d(out_channels, 1, 1),
            apooling_cls(apooling_output_size),
            Flatten(),
            torch.nn.Linear(
                np.product(apooling_output_size),
                n_classes),
            torch.nn.LogSoftmax(-1)
            ]
    return torch.nn.Sequential(*layers)
