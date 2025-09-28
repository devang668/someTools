import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np


class ReplayBuffer:
    def __init__(self, capacity):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, state, action, reward, next_state):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        states, actions, rewards, next_states = zip(*[self.buffer[i] for i in indices])
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states)
        )

    def __len__(self):
        return len(self.buffer)


class Actor(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(Actor, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),  # 关键修改层：与训练时一致
            nn.ReLU(),
            nn.Linear(128, 64),  # 新增层：解决size mismatch问题
            nn.ReLU(),
            nn.Linear(64, action_dim),
            nn.Sigmoid()
        )

    def forward(self, state):
        return self.net(state)


class Critic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(Critic, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, 256),
            nn.LeakyReLU(0.01),
            nn.Linear(256, 128),  # 保持与训练时相同的层级结构
            nn.LeakyReLU(0.01),
            nn.Linear(128, 1)
        )

    def forward(self, state, action):
        return self.net(torch.cat([state, action], dim=1))  # 修正dim参数


class DDPGAgent:
    def __init__(self, state_dim, action_dim, gamma=0.99, tau=0.005):
        # 设备配置（修正拼写错误）
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 初始化网络
        self.actor = Actor(state_dim, action_dim).to(self.device)
        self.critic = Critic(state_dim, action_dim).to(self.device)
        self.target_actor = Actor(state_dim, action_dim).to(self.device)
        self.target_critic = Critic(state_dim, action_dim).to(self.device)

        # 同步目标网络参数
        self.target_actor.load_state_dict(self.actor.state_dict())
        self.target_critic.load_state_dict(self.critic.state_dict())

        # 优化器配置
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=1e-4)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=1e-3)

        # 经验回放
        self.replay_buffer = ReplayBuffer(capacity=1000000)
        self.batch_size = 128
        self.gamma = gamma
        self.tau = tau

    def select_action(self, state, noise_scale=0.1):
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action = self.actor(state).cpu().numpy()[0]
        noise = noise_scale * np.random.randn(*action.shape)
        return np.clip(action + noise, 0, 1)

    def save_experience(self, state, action, reward, next_state):
        self.replay_buffer.push(state, action, reward, next_state)

    def update(self):
        if len(self.replay_buffer) < self.batch_size:
            return

        # 从回放缓冲区采样
        states, actions, rewards, next_states = self.replay_buffer.sample(self.batch_size)
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)

        # 更新Critic网络
        with torch.no_grad():
            target_actions = self.target_actor(next_states)
            target_q = self.target_critic(next_states, target_actions)
            target_q = rewards + self.gamma * target_q

        current_q = self.critic(states, actions)
        critic_loss = F.mse_loss(current_q, target_q)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # 更新Actor网络
        actor_actions = self.actor(states)
        actor_loss = -self.critic(states, actor_actions).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        # 软更新目标网络
        for target_param, param in zip(self.target_actor.parameters(), self.actor.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

        for target_param, param in zip(self.target_critic.parameters(), self.critic.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)