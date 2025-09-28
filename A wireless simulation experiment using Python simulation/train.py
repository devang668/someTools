#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: train.py.py
@time: 27/5/2025 上午 12:21
@functions：训练主程序
"""
from ddpg_agent import DDPGAgent
from wireless_env import WirelessCommEnv
import matplotlib.pyplot as plt
import numpy as np
import torch
# 超参数设置
EPISODES = 1000
MAX_STEPS = 200
NUM_USERS = 10  # 动态变化范围在env中处理

# 初始化环境和智能体
env = WirelessCommEnv(num_users=NUM_USERS)
state_dim = env.observation_space.shape[0]
action_dim = env.action_space.shape[0]
agent = DDPGAgent(state_dim, action_dim)

# 训练循环
episode_rewards = []
for episode in range(EPISODES):
    state = env.reset()
    total_reward = 0

    # 动态改变用户数量 (每10个episode变化一次)
    if episode % 10 == 0:
        env.num_users = np.random.randint(10, 50)
        env.reset()

    for step in range(MAX_STEPS):
        # 选择动作并执行
        action = agent.select_action(state)
        next_state, reward, done, _ = env.step(action)

        # 存储经验
        agent.save_experience(state, action, reward, next_state)

        # 更新网络参数
        agent.update()

        state = next_state
        total_reward += reward

        if done:
            break

    episode_rewards.append(total_reward)

    # 打印训练进度
    if episode % 50 == 0:
        print(f"Episode {episode}, Reward: {total_reward:.2f}")

# 保存模型
torch.save(agent.actor.state_dict(), "ddpg_actor.pth")
torch.save(agent.critic.state_dict(), "ddpg_critic.pth")

# 绘制训练曲线
plt.plot(episode_rewards)
plt.xlabel("Episode")
plt.ylabel("Total Reward")
plt.title("DDPG Training Progress")
plt.savefig("training_curve.png")