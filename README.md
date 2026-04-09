# 🔥 API Problem Generator

> 工业级 AI 信奥出题引擎 —— 大模型 × 云端沙箱 × 自动化流水线

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-go--judge-orange.svg)](https://github.com/criyle/go-judge)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📖 项目简介

`api-problem-generator` 是一款**工业级信息学奥林匹克（NOIP/CSP）AI 出题引擎**。它将大模型的推理能力与高强度沙箱编译/数据生成能力深度融合，实现从"原题描述"到"完整数据包"的**全自动化流水线**。

### 核心特性

- 🤖 **大模型驱动** —— AI 依据精心设计的 `SKILL.md` 自动生成题目源码、题面与元数据
- 🏗️ **三层架构解耦** —— 脑（LLM）/ 手（本地组装）/ 肌肉（云端沙箱）分离，互不干扰
- 🐳 **go-judge 沙箱** —— Docker 化部署，毫秒级编译、生成、校验，全程资源隔离
- 📦 **一键部署** —— `./deploy.sh` 即可拉起完整生产级环境与 Systemd 守护进程

---

## 🧠 核心架构解析

```
┌─────────────────────────────────────────────────────────────────┐
│                        🧠 大模型层 (Brain)                        │
│                                                                 │
│   用户触发 @api-problem-generator                                │
│   ↓                                                              │
│   AI 读取 SKILL.md → 生成 gen.cpp / valid.cpp / std.cpp          │
│              + problem.md / meta.json / test_payload.json        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP POST
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ✋ 本地组装层 (Hand)                          │
│                                                                 │
│   call_api.py 读取 test_payload.json → 提交到云端 API             │
│   ↓                                                              │
│   等待云端返回 .zip → 解压 → 注入 meta.json → 重新打包             │
│   ↓                                                              │
│   输出最终数据包: problem_package_<timestamp>.zip                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ 编译 + 运行生成器
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     💪 云端沙箱层 (Muscle)                         │
│                                                                 │
│   FastAPI Backend (守护进程)                                     │
│   ↓                                                              │
│   go-judge Docker 容器                                           │
│     ├─ 编译 gen.cpp → 生成测试数据 (Subtask × Cases)             │
│     ├─ 编译 valid.cpp → 严格校验每个 input                       │
│     └─ 编译 std.cpp → 生成标准输出                               │
│   ↓                                                              │
│   打包 testdata/*.in + *.out + problem.md + std.cpp → .zip      │
└─────────────────────────────────────────────────────────────────┘
```

### 各层职责详解

| 层级 | 组件 | 职责 |
|------|------|------|
| 🧠 **大模型层** | `SKILL.md` | 定义 AI 出题专家的 SOP（标准作业流程），包含铁律约束、数据分配规则、标签规范 |
| ✋ **本地组装层** | `call_api.py` | 读取 AI 生成的 payload → 调用云端 API → 组装最终数据包 |
| 💪 **云端沙箱层** | `backend/main.py` + `go-judge` | 高强度沙箱编译 C++ 源码 → 生成海量测试数据 → 校验 → 打包 |

---

## 🚀 快速部署

### 前置要求

- Ubuntu 20.04+ / macOS（已安装 Docker）
- Root 权限或 sudo 权限

### 一键部署

```bash
# 克隆项目后，进入项目根目录执行：
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` 会自动完成以下操作：

1. 安装系统依赖（curl, wget, git, python3, pip）
2. 配置 Python 虚拟环境并安装 FastAPI 依赖
3. 构建并启动 go-judge Docker 沙箱
4. 配置 FastAPI Systemd 守护进程

部署完成后，服务地址：

```
🌐 API 端点: http://<服务器IP>:8000/api/forge_problem
```

### 日常运维

```bash
# 查看服务状态
sudo systemctl status cloud-judge-api

# 查看实时日志
sudo journalctl -u cloud-judge-api -f

# 重启服务
sudo systemctl restart cloud-judge-api
```

---

## 🔄 核心工作流

### AI 出题流程（用户视角）

1. **触发 AI**：在支持 MCP 协议的工具中输入 `@api-problem-generator`，并提供原题描述

2. **AI 生成阶段**：
   - 读取 `SKILL.md` 获取出题规范
   - 检索 `references/templates/` 获取图论/树等结构的标准骨架
   - 依据 `Algorithm_Tags.md` 生成合规标签
   - 生成 `gen.cpp` / `valid.cpp` / `std.cpp` / `problem.md`
   - 生成 `meta.json` 和 `test_payload.json`

3. **本地调度**：
   ```bash
   python3 call_api.py
   ```

4. **云端执行**：
   - 编译三件套（生成器、校验器、标程）
   - 按 Subtask 分配生成 4-3-3 共 10 个测试点
   - 每个数据点经过生成 → 校验 → 标程运行三关
   - 打包输出 `problem_package_<timestamp>.zip`

### SKILL.md 关键铁律

| 铁律 | 说明 |
|------|------|
| **背景盲盒铁律** | 未指定背景时，随机抽取 `references/backgrounds.md` 中的世界观 |
| **数据分配铁律** | 默认 3 个 Subtask，10 个测试点，按 4-3-3 分配 |
| **API 查阅铁律** | 必须使用 testlib 官方 API（`println`、`opt`、`rnd`），禁用 `print()` |
| **标签强制规范** | 必须从 `Algorithm_Tags.md` 中挑选 1~3 个标准标签 |
| **严禁覆写铁律** | 禁止修改 `call_api.py`，它是固化的流水线程序 |

---

## 📂 项目结构

```
api-problem-generator/
├── SKILL.md              # AI 出题专家的 SOP（供大模型使用）
├── call_api.py           # 本地调度脚本（提交任务到云端）
├── deploy.sh             # 一键部署脚本
├── docker-compose.yml    # go-judge 沙箱编排
├── Dockerfile.judge     # go-judge 沙箱镜像
├── README.md             # 项目文档
├── .gitignore            # Git 忽略配置
│
├── backend/              # FastAPI 后端
│   ├── main.py          # 核心 API 逻辑（编译、生成、校验、打包）
│   ├── requirements.txt  # Python 依赖
│   └── testlib.h        # testlib 标准库
│
├── references/           # 参考资料库（供 AI 检索）
│   ├── Algorithm_Tags.md    # 合规算法标签列表
│   ├── backgrounds.md       # 背景世界观素材库
│   ├── testlib-manual.md    # testlib API 手册
│   └── templates/            # 官方标准骨架
│       ├── generators/     # 生成器模板（图、树、网格等）
│       └── validators/      # 校验器模板
│
└── scripts/              # 辅助脚本
    ├── generate.py       # 备用生成脚本
    └── testlib.h         # 备用 testlib
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **AI 推理** | 大模型 (Claude/GPT-4) | 生成源码与题面 |
| **本地调度** | Python 3.10+ / requests | 读取 payload，调用云端 API |
| **API 框架** | FastAPI + uvicorn | 高性能 HTTP 接口 |
| **沙箱引擎** | go-judge (Docker) | 资源隔离的 C++ 编译与执行 |
| **系统守护** | Systemd | 生产级进程管理 |

---

## 📋 数据包输出格式

最终生成的 `problem_package_<timestamp>.zip` 包含：

```
problem_package_xxx/
├── testdata/
│   ├── 1.in          # 测试点 1 输入
│   ├── 1.out         # 测试点 1 输出
│   ├── 2.in
│   ├── 2.out
│   ├── ...
│   └── 10.in
│   └── 10.out
├── problem.md        # 题面（含样例与标签）
└── std.cpp          # 标程源码
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 License

MIT License
