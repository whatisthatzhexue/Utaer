# 本项目 unidic_and_f0 部分启动教程

> 本教程给出 Utaer 项目 unidic_and_f0 部分从环境激活到服务启动、结果验证的完整线性步骤：启动 tdmelodic_service 容器（HTTP 声调预测服务）→ 运行 `init.py` 启动脚本 → 解读并验证两段输出。

## 1. 文档简介

本教程是配置流程的收尾篇。完成本教程后，你将在本地跑通模块的**双通道**：

- **通道 A（HTTP 预测）**：`td_service.py` 被挂载进 `tdmelodic:latest` 容器，作为声调预测服务监听 8000 端口；
- **通道 B（本地词典）**：宿主 `init.py` 通过 mecab-python3 + 组合词典完成词典解析。

建议阅读顺序：`tdmelodic 配置教程.md` → `tdmelodic 使用教程.md`（可选）→ `本项目配置教程.md` → 本教程。

## 2. 前置条件

### 2.1 环境与软件要求

- 已完成 `tdmelodic 配置教程.md`：镜像 `tdmelodic:latest` 已构建（3.8），宿主组合词典已安装（3.16）。
- 已完成 `本项目配置教程.md`：宿主 mecab-python3 与词典路径可用。

### 2.2 文件与路径约定

- 项目根目录为 `Utaer/`，模块目录为 `Utaer/functions/unidic/`。
- `init.py`、`td_service.py`、`Dockerfile` 由项目提供；`tdmelodic/`、`mecab-unidic-neologd/` 须已按 `tdmelodic 配置教程.md` 自行克隆安装。

### 2.3 前置文档依赖

- `tdmelodic 配置教程.md`、`本项目配置教程.md`（必读前置）。
- `tdmelodic 使用教程.md` 3.4/3.5（了解本次启动所调用接口的实现，可选）。

## 3. 核心步骤

### 3.1 进入模块目录

```bash
cd Utaer/functions/unidic/
```

> **注意**：后续步骤依赖 `$PWD`（当前目录），必须在 `functions/unidic/` 下执行。

### 3.2 清理旧容器

```bash
docker rm -f tdmelodic_service
```

> **说明**：若容器不存在会报错，忽略即可。

### 3.3 启动 HTTP 服务容器

```bash
docker run -d -p 8000:8000 \
  -v $PWD/td_service.py:/app/server.py \
  -w /app \
  --name tdmelodic_service \
  tdmelodic:latest python3 server.py
```

参数说明：

| 参数 | 说明 |
|---|---|
| `-d` | 后台运行容器 |
| `-p 8000:8000` | 端口映射（宿主 8000 → 容器 8000） |
| `-v $PWD/td_service.py:/app/server.py` | 把当前目录的 `td_service.py` 挂载为容器内 `/app/server.py` |
| `-w /app` | 容器工作目录设为 `/app` |
| `--name tdmelodic_service` | 容器命名 |
| `tdmelodic:latest python3 server.py` | 使用的镜像及容器启动命令 |

### 3.4 运行启动脚本

```bash
python3 init.py
```

### 3.5 输出解读

`init.py` 会打印两段输出：

- **`SpeakToYomiAkusento` 段**：`predict_batch` 经 HTTP 请求容器服务（通道 A）得到，内容是两条示例文本（`私は歌を歌うのが好きです。`、`なんでこんな目で見てるの`）的 tdmelodic-s2ya 预测结果列表。**只依赖容器服务**。
- **`MeCabDictionaryResult` 段**：宿主 mecab-python3 + 组合词典（通道 B）解析示例句的完整输出，格式与 `tdmelodic 使用教程.md` 3.1 的预期输出一致。**只依赖宿主组合词典**。

两段相互独立：容器未启动时第一段报连接错误；宿主组合词典未安装时第二段报词典不存在。

## 4. 验证方式

### 4.1 容器运行确认

```bash
docker ps
```

预期：列表中出现 `tdmelodic_service`。

### 4.2 服务接口自测

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"texts": ["機械学習"]}'
```

预期：返回 `{"results": [...]}`，`results` 条数 = `texts` 条数。

### 4.3 词典通道验证

`init.py` 第二段输出与 `tdmelodic 使用教程.md` 3.1 的预期输出格式一致（Tab 分隔的 表層形/発音/読み… 列，「人工知能」作为整词返回）。

### 4.4 结束与清理（可选）

```bash
docker rm -f tdmelodic_service
```

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| curl 连接被拒 | 容器未启动或已退出 | `docker ps` 检查；`docker logs tdmelodic_service` 查看日志 |
| 端口 8000 被占用 | 其他进程占用该端口 | 停掉占用进程；或修改 `-p` 映射，并同步修改 `init.py` 中 `predict_batch` 的 `url` 参数 |
| `docker run` 报镜像不存在 | `tdmelodic:latest` 未构建 | 完成 `tdmelodic 配置教程.md` 3.8 |
| `docker run` 报挂载路径错误 | 未在 `functions/unidic/` 下执行（`$PWD` 错误） | 回到 3.1 |
| init.py 第一段成功、第二段报错 | 宿主组合词典未安装 | 完成 `tdmelodic 配置教程.md` 3.16 与 `本项目配置教程.md` 3.7 |
| init.py 第一段报错、第二段成功 | 容器未启动 | 回到 3.3 |
| 修改 `td_service.py` 后行为未变 | 容器内进程不会热重载挂载的文件 | `docker rm -f tdmelodic_service` 后重新执行 3.3 |
| 输出乱码 | 终端编码问题 | 使用 UTF-8 终端（容器内已设 ja_JP.UTF-8） |

## 附录：参考链接

- 项目总规范：`AGENTS.md`（项目根目录）
- 本系列：`tdmelodic 配置教程.md`、`tdmelodic 使用教程.md`、`本项目配置教程.md`、`AGENT.md`
