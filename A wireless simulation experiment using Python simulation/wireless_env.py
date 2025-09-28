#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: wireless_env.py.py
@time: 27/5/2025 上午 12:21
@functions：自定义通信环境
"""
import gym
from gym import spaces
import numpy as np


class WirelessCommEnv(gym.Env):
    def __init__(self, num_users=10, num_rb=100):
        super(WirelessCommEnv, self).__init__()
        self.num_users = num_users  # 动态用户数
        self.num_rb = num_rb  # 资源块数量

        # 状态空间定义: [CSI, QoS需求, 基站负载, 干扰水平]
        self.observation_space = spaces.Box(low=0, high=1, shape=(4 * num_users,))

        # 动作空间定义: 每个用户的资源分配比例 (power + RB)
        self.action_space = spaces.Box(low=0, high=1, shape=(2 * num_users,))

        # 基站参数
        self.max_power = 20  # 瓦
        self.bandwidth = 180e3  # Hz per RB

        # 信道模型参数 (3GPP UMi)
        self.path_loss_coeff = 34.5  # dB
        self.shadowing_std = 8  # dB

    def reset(self):
        # 随机生成用户位置和初始状态
        self.user_positions = np.random.uniform(50, 500, self.num_users)  # 距离基站50-500米
        self.qos_demand = np.random.randint(1, 5, self.num_users)  # 1-5 Mbps需求

        # 初始状态生成
        state = self._get_state()
        return state

    def _get_state(self):
        # 获取当前信道状态
        csi = self._calculate_channel_state()
        # 基站负载 (已使用RB比例)
        load = np.sum(self.last_action[:self.num_users]) if hasattr(self, 'last_action') else 0.0
        # 干扰水平 (简化为其他用户总功率的10%)
        interference = 0.1 * np.sum(self.last_action[self.num_users:]) if hasattr(self, 'last_action') else 0.0

        state = np.concatenate([
            csi,
            self.qos_demand / 5.0,  # 归一化到[0,1]
            np.array([load] * self.num_users),
            np.array([interference] * self.num_users)
        ])
        return state

    def _calculate_channel_state(self):
        # 3GPP UMi路径损耗模型
        distance = self.user_positions
        pl = self.path_loss_coeff + 20 * np.log10(distance) + np.random.normal(0, self.shadowing_std)
        # 转换为信道增益 (简化模型)
        channel_gain = 10 ** (-pl / 20)
        return channel_gain

    def step(self, action):
        # 解析动作: 前num_users为RB分配，后num_users为功率分配
        rb_alloc = action[:self.num_users]
        power_alloc = action[self.num_users:] * self.max_power  # 转换为实际功率

        # 计算每个用户的吞吐量
        sinr = self._calculate_sinr(power_alloc, rb_alloc)
        throughput = self.bandwidth * np.log2(1 + sinr) / 1e6  # Mbps

        # 奖励函数
        reward = self._calculate_reward(throughput, power_alloc)

        # 生成新状态
        next_state = self._get_state()

        # 判断是否结束 (持续仿真，无终止条件)
        done = False

        return next_state, reward, done, {}

    def _calculate_sinr(self, power_alloc, rb_alloc):
        # 简化干扰模型: 其他用户的总功率
        interference = np.sum(power_alloc) - power_alloc
        noise_power = 1e-9  # -90 dBm
        sinr = (power_alloc * self._calculate_channel_state()) / (interference + noise_power)
        return sinr

    def _calculate_reward(self, throughput, power_alloc):
        # 吞吐量奖励
        alpha = 0.7
        # 公平性奖励 (Jain指数)
        beta = 0.2
        jain_index = np.sum(throughput) ** 2 / (self.num_users * np.sum(throughput ** 2))
        # 能耗惩罚
        gamma = 0.1
        total_power = np.sum(power_alloc)

        reward = alpha * np.sum(throughput) + beta * jain_index - gamma * total_power
        return reward