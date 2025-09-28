#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: ddpg_agent.py.py
@time: 27/5/2025 上午 12:11
@functions：please note ..
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque


# Actor网络定义
class Actor(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=256):
        super(Actor, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
            nn.Sigmoid()  # 输出归一化到[0,1]
        )

    def forward(self, state):
        return self.net(state)


# Critic网络定义
class Critic(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=256):
        super(Critic, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.LeakyReLU(),
            nn.Linear(hidden_dim, 128),
            nn.LeakyReLU(),
            nn.Linear(128, 64),
            nn.LeakyReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, state, action):
        return self.net(torch.cat([state, action], 1))


# DDPG Agent类
class DDPGAgent:
    def __init__(self, state_dim, action_dim):
        self.actor = Actor(state_dim, action_dim)
        self.actor_target = Actor(state_dim, action_dim)
        self.actor_target.load_state_dict(self.actor.state_dict())
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=1e-4)

        self.critic = Critic(state_dim, action_dim)
        self.critic_target = Critic(state_dim, action_dim)
        self.critic_target.load_state_dict(self.critic.state_dict())
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=1e-3)

        self.replay_buffer = deque(maxlen=1000000)
        self.batch_size = 64
        self.tau = 0.005
        self.gamma = 0.99

    def select_action(self, state, noise_scale=0.1):
        state = torch.FloatTensor(state).unsqueeze(0)
        action = self.actor(state).detach().numpy()[0]
        # 添加OU噪声促进探索
        noise = noise_scale * np.random.randn(*action.shape)
        return np.clip(action + noise, 0, 1)

    def update(self):
        if len(self.replay_buffer) < self.batch_size:
            return

        # 从回放缓冲区采样
        batch = random.sample(self.replay_buffer, self.batch_size)
        states = torch.FloatTensor([t[0] for t in batch])
        actions = torch.FloatTensor([t[1] for t in batch])
        rewards = torch.FloatTensor([t[2] for t in batch]).unsqueeze(1)
        next_states = torch.FloatTensor([t[3] for t in batch])

        # Critic更新
        with torch.no_grad():
            target_actions = self.actor_target(next_states)
            target_q = self.critic_target(next_states, target_actions)
            target_q = rewards + self.gamma * target_q

        current_q = self.critic(states, actions)
        critic_loss = nn.MSELoss()(current_q, target_q)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # Actor更新
        actor_loss = -self.critic(states, self.actor(states)).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        # 软更新目标网络
        for param, target_param in zip(self.actor.parameters(), self.actor_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)
        for param, target_param in zip(self.critic.parameters(), self.critic_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

    def save_experience(self, state, action, reward, next_state):
        self.replay_buffer.append((state, action, reward, next_state))