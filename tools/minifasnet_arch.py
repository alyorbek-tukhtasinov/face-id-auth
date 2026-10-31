"""MiniFASNet arxitekturasi (PyTorch) — faqat ONNX ga o'girish uchun.

Asl dizayn: Minivision, Silent-Face-Anti-Spoofing (Apache License 2.0).
Bu qayta yozilgan versiya; parametr nomlari asl checkpoint bilan mos.
"""

from __future__ import annotations

import torch
from torch import nn

KEEP = {
    "V1": [32, 32, 103, 103, 64, 13, 13, 64, 26, 26, 64, 13, 13, 64, 52, 52, 64, 231, 231, 128,
           154, 154, 128, 52, 52, 128, 26, 26, 128, 52, 52, 128, 26, 26, 128, 26, 26, 128, 308, 308,
           128, 26, 26, 128, 26, 26, 128, 512, 512],
    "V2": [32, 32, 103, 103, 64, 13, 13, 64, 13, 13, 64, 13, 13, 64, 13, 13, 64, 231, 231, 128,
           231, 231, 128, 52, 52, 128, 26, 26, 128, 77, 77, 128, 26, 26, 128, 26, 26, 128, 308, 308,
           128, 26, 26, 128, 26, 26, 128, 512, 512],
}


class ConvBlock(nn.Module):
    def __init__(self, cin, cout, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1, act=True):
        super().__init__()
        self.conv = nn.Conv2d(cin, cout, kernel, stride, padding, groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(cout)
        if act:
            self.prelu = nn.PReLU(cout)
        self.act = act

    def forward(self, x):
        x = self.bn(self.conv(x))
        return self.prelu(x) if self.act else x


class SEModule(nn.Module):
    def __init__(self, ch, red):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(ch, ch // red, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(ch // red)
        self.relu = nn.ReLU()
        self.fc2 = nn.Conv2d(ch // red, ch, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(ch)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        s = self.sigmoid(self.bn2(self.fc2(self.relu(self.bn1(self.fc1(self.avg_pool(x)))))))
        return x * s


class DepthWise(nn.Module):
    def __init__(self, c1, c2, c3, residual=False, stride=(2, 2), se=False):
        super().__init__()
        self.conv = ConvBlock(c1[0], c1[1])
        self.conv_dw = ConvBlock(c2[0], c2[1], (3, 3), stride, (1, 1), groups=c2[0])
        self.project = ConvBlock(c3[0], c3[1], act=False)
        self.residual = residual
        if se:
            self.se_module = SEModule(c3[1], 4)
        self.se = se

    def forward(self, x):
        y = self.project(self.conv_dw(self.conv(x)))
        if self.residual:
            if self.se:
                y = self.se_module(y)
            return x + y
        return y


class Residual(nn.Module):
    def __init__(self, keep, idx, n, se):
        super().__init__()
        blocks = []
        for i in range(n):
            j = idx + 3 * i
            blocks.append(DepthWise((keep[j], keep[j + 1]), (keep[j + 1], keep[j + 2]), (keep[j + 2], keep[j + 3]),
                                    residual=True, stride=(1, 1), se=se and i == n - 1))
        self.model = nn.Sequential(*blocks)

    def forward(self, x):
        return self.model(x)


class MiniFASNet(nn.Module):
    def __init__(self, version="V2", se=False, conv6_kernel=(5, 5), embedding=128, classes=3):
        super().__init__()
        k = KEEP[version]
        self.conv1 = ConvBlock(3, k[0], (3, 3), (2, 2), (1, 1))
        self.conv2_dw = ConvBlock(k[0], k[1], (3, 3), (1, 1), (1, 1), groups=k[1])
        self.conv_23 = DepthWise((k[1], k[2]), (k[2], k[3]), (k[3], k[4]))
        self.conv_3 = Residual(k, 4, 4, se)
        self.conv_34 = DepthWise((k[16], k[17]), (k[17], k[18]), (k[18], k[19]))
        self.conv_4 = Residual(k, 19, 6, se)
        self.conv_45 = DepthWise((k[37], k[38]), (k[38], k[39]), (k[39], k[40]))
        self.conv_5 = Residual(k, 40, 2, se)
        self.conv_6_sep = ConvBlock(k[46], k[47])
        self.conv_6_dw = ConvBlock(k[47], k[48], conv6_kernel, groups=k[48], act=False)
        self.linear = nn.Linear(512, embedding, bias=False)
        self.bn = nn.BatchNorm1d(embedding)
        self.prob = nn.Linear(embedding, classes, bias=False)

    def forward(self, x):
        for m in (self.conv1, self.conv2_dw, self.conv_23, self.conv_3, self.conv_34, self.conv_4,
                  self.conv_45, self.conv_5, self.conv_6_sep, self.conv_6_dw):
            x = m(x)
        x = torch.flatten(x, 1)
        return self.prob(self.bn(self.linear(x)))
