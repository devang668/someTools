#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: traditional.py
@time: 27/5/2025 上午 9:06
@functions：please note ..
"""
import numpy as np


class TraditionalScheduler:
    """传统无线资源调度算法集合"""

    def __init__(self, max_users, mode='round_robin'):
        """
        参数：
            max_users : 最大用户数（需与环境一致）
            mode : 调度模式
                'round_robin' - 轮询调度
                'equal_power' - 均等功率分配
                'channel_aware' - 基于信道状态的调度
        """
        self.max_users = max_users
        self.mode = mode

    def allocate(self, state):
        """
        生成调度动作

        参数：
            state : 环境状态向量（用于信道感知模式）
        返回：
            action : 动作向量（形状：2*max_users）
        """
        current_users = int(len(state) // 4)  # 从状态推断当前用户数
        action = np.zeros(2 * self.max_users)

        # ----------------------------
        # 资源块分配逻辑
        # ----------------------------
        if self.mode == 'round_robin':
            rb_alloc = np.ones(current_users) / current_users
        elif self.mode == 'fixed_rb':
            rb_alloc = np.ones(current_users) * 0.3  # 固定分配30%资源块
        elif self.mode == 'channel_aware':
            # 从状态中提取信道质量信息（假设前current_users个元素是CSI）
            csi = state[:current_users]
            rb_alloc = csi / np.sum(csi)
        else:
            raise ValueError(f"未知的调度模式: {self.mode}")

        # ----------------------------
        # 功率分配逻辑
        # ----------------------------
        if self.mode == 'equal_power':
            power_alloc = np.ones(current_users) * 0.5  # 固定50%最大功率
        elif self.mode == 'channel_aware':
            # 信道质量越好分配越多功率
            csi = state[:current_users]
            power_alloc = 0.2 + 0.6 * (csi / np.max(csi))  # 归一化后分配
        else:
            # 默认固定功率
            power_alloc = np.ones(current_users) * 0.4

        # ----------------------------
        # 组合动作向量
        # ----------------------------
        action[:current_users] = rb_alloc
        action[self.max_users:self.max_users + current_users] = power_alloc

        return action