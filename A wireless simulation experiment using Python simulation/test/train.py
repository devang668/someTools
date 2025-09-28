import numpy as np
import torch
import matplotlib.pyplot as plt
from ddpg_agent import DDPGAgent
from wireless_env import WirelessCommEnv

# ----------------------
# 超参数配置
# ----------------------
EPISODES = 1000
MAX_STEPS = 200
MAX_USERS = 50
MIN_USERS = 10

# ----------------------
# 初始化环境与智能体
# ----------------------
env = WirelessCommEnv(max_users=MAX_USERS)
agent = DDPGAgent(
    state_dim=4 * MAX_USERS,
    action_dim=2 * MAX_USERS
)

# ----------------------
# 训练指标记录
# ----------------------
rewards_history = []
user_counts = []

# ----------------------
# 主训练循环
# ----------------------
for episode in range(EPISODES):
    # 动态调整用户数量
    if episode % 10 == 0:
        new_users = np.random.randint(MIN_USERS, MAX_USERS + 1)
        env.current_num_users = new_users

    state = env.reset()
    episode_reward = 0

    for _ in range(MAX_STEPS):
        # 选择动作（使用完整状态）
        action = agent.select_action(state)

        # 与环境交互
        next_state, reward, done, _ = env.step(action)

        # 存储经验
        agent.save_experience(state, action, reward, next_state)
        agent.update()

        # 状态转移
        state = next_state
        episode_reward += reward

    # 记录训练指标
    rewards_history.append(episode_reward)
    user_counts.append(env.current_num_users)

    # 打印训练进度
    if episode % 50 == 0:
        avg_reward = episode_reward / MAX_STEPS
        print(f"Episode {episode} | Users: {env.current_num_users} | "
              f"Total Reward: {episode_reward:.1f} | Avg: {avg_reward:.2f}")

# ----------------------
# 保存与可视化
# ----------------------
torch.save(agent.actor.state_dict(), "actor.pth")
torch.save(agent.critic.state_dict(), "critic.pth")

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(rewards_history)
plt.title("Training Rewards")
plt.subplot(1, 2, 2)
plt.scatter(range(EPISODES), user_counts, s=3, alpha=0.5)
plt.title("Dynamic User Count")
plt.tight_layout()
plt.savefig("training_analysis.png")
plt.show()