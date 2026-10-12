# tdmelodic 配置教程

> 本教程带你从零开始，在 WSL2（Ubuntu-22.04）上完成 tdmelodic 的全部配置：基础 Docker 镜像 → 大音调词典推断 → 与 UniDic 结合安装为组合词典。

## 1. 文档简介

本教程解决「如何把 tdmelodic 装好」的问题，是其余所有文档的前置。配置完成后：

- 可直接跳至 `tdmelodic 使用教程.md`（想了解 tdmelodic 是如何被调用的）；
- 或直接跳至 `本项目 unidic_and_f0 部分启动教程.md`（想在配置完成后立即启动项目）。

**流程概览**：

- **第一阶段**：先跑通 tdmelodic（只需 tdmelodic 仓库即可做到基础词典调用 + 单词声调预测功能）。
- **第二阶段**：利用 mecab-unidic-neologd，结合 UniDic 和 neologd + 大模型推断生成大音调词典，最后再把这个大音调词典结合到 tdmelodic 中。

第二阶段的意义：仅用第一阶段的词典解析「人工知能」，会得到「人工」「知能」两个分词结果，不便于复合词的声调分析；第二阶段完成后，调用词典解析可以直接得到「人工知能」作为一个统一的分词结果及其整体的声调。

## 2. 前置条件

### 2.1 环境与软件要求

- Windows 10/11（WSL2 未安装时由 3.2 安装）
- WSL2 Ubuntu-22.04（安装后自带 python3 和 git）
- docker（3.4 安装）

### 2.2 文件与路径约定

- 本教程统一用 `${WORKDIR}` 表示「项目根目录/functions/unidic」。
- **克隆前先 `cd ${WORKDIR}`**，以下两处第三方仓库均放置于此：
  - `${WORKDIR}/mecab-unidic-neologd/` —— UniDic 音调词典扩充器（第三方，自行克隆）
  - `${WORKDIR}/tdmelodic/` —— tdmelodic 词典本体（第三方，自行克隆）
- 第三方仓库与 UniDic 基础辞书均不随文档提供，须按本教程自行下载安装。

### 2.3 前置文档依赖

- 无硬性前置；了解背景可先读项目根目录 `AGENTS.md` §9（音频处理规范）。

## 3. 核心步骤

### 3.1 备份系统软件源

在修改系统软件源（比如换成国内清华、阿里、科大镜像源）前，先备份原始文件是 Linux 系统运维的标准安全操作。

```bash
# 备份
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
# 还原（需要时）
sudo cp /etc/apt/sources.list.bak /etc/apt/sources.list
```

### 3.2 安装 WSL2（Ubuntu-22.04）

在 Windows PowerShell 中执行：

```powershell
wsl --install
```

建议的版本：Ubuntu-22.04

```powershell
wsl --install -d Ubuntu-22.04
```

> **说明**：安装后自带 python3 和 git。已安装 WSL2 可跳过本步。

WSL 的常用操作：

- WSL 内：`exit` 退出 WSL。
- WSL 外：`wsl --shutdown` 关闭 WSL。
- 将 Ubuntu-22.04 迁移到其他盘、释放 C 盘空间（注：默认安装在 C 盘）：

```powershell
wsl --export Ubuntu-22.04 盘符:\文件夹1\ubuntu2204.tar
wsl --unregister Ubuntu-22.04
wsl --import Ubuntu-22.04 盘符:\文件夹2 盘符:\文件夹1\ubuntu2204.tar --version 2
del 盘符:\文件夹1\ubuntu2204.tar
```

> **说明**：文件夹1 为临时文件夹，最终 WSL 将调用文件夹2 中的版本。文件夹1、文件夹2 有多层文件夹也可。

### 3.3 Linux 基础操作速查

```bash
cd /mnt/c/Users/用户名
# WSL 中访问 Windows 文件的方式（跨系统访问文件性能低，不建议使用）
cd ~
# 回到家目录
mkdir abc
# 新建文件夹
mv nameA nameB
# 重命名 / 移动
cp fileA fileB
# 复制
chmod +x filename
# 添加文件可执行权限
```

### 3.4 安装 Docker 并配置用户组

```bash
# 在 apt 下安装 docker
sudo apt update && sudo apt install -y docker.io

hash -r
# 刷新路径缓存
# (下面这个 snap 版本不支持，apt 直接安装的可以）
sudo usermod -aG docker $USER
newgrp docker
```

Docker 调试操作：

```bash
# 查看容器
docker ps -a
# 销毁容器
docker rm <container-id>
```

### 3.5 克隆 tdmelodic 仓库

> **注意**：克隆前先 `cd ${WORKDIR}`（项目根目录/functions/unidic/）。

```bash
cd ${WORKDIR}
git clone --depth 1 https://github.com/PKSHATechnology-Research/tdmelodic
```

克隆后生成 `${WORKDIR}/tdmelodic/`（tdmelodic 词典本体）。

### 3.6 下载 UniDic 基础辞书并放入 tdmelodic 文件夹

> **说明**：模块总文档把本步放在镜像构建之后；但本项目的 `Dockerfile` 通过 `COPY ${UNIDIC}.zip /tmp` 在**构建阶段**读取该 zip，因此必须先完成本步再构建镜像（3.8）。该 zip 后续还会在 3.13（推断）与 3.15（结合）中复用。

方法一（网页下载）：打开 https://clrd.ninjal.ac.jp/unidic/back_number.html ，下载 `unidic-mecab_kana-accent-2.1.2_src.zip`，然后把下载下来的压缩包放入 tdmelodic 仓库文件夹。

方法二（命令行下载）：

```bash
wget https://ccd.ninjal.ac.jp/unidic_archive/cwj/2.1.2/unidic-mecab_kana-accent-2.1.2_src.zip
cp unidic-mecab_kana-accent-2.1.2_src.zip ${WORKDIR}/tdmelodic
```

验证：确认 `${WORKDIR}/tdmelodic/unidic-mecab_kana-accent-2.1.2_src.zip` 存在。

### 3.7 修复 Dockerfile

背景：由于 python module setuptools 的版本问题，我们需要把克隆下来的 tdmelodic 文件夹内最外层的 Dockerfile 修改一下。

曾尝试构建后在容器内降级（下面的指令没用：对运行中容器的修改不会写回镜像，必须直接改 Dockerfile 后重新构建）：

```bash
docker run --rm -v $(pwd):/root/workspace tdmelodic:latest \
    pip install "setuptools<60.0"
```

正确做法：用项目提供的 `functions/unidic/Dockerfile` 替换 tdmelodic 文件夹内最外层的 Dockerfile（懒人可直接复制粘贴）。关键修改点：

```dockerfile
ARG UNIDIC='unidic-mecab_kana-accent-2.1.2_src'
COPY ${UNIDIC}.zip /tmp
```

```dockerfile
RUN $pip install --upgrade pip && \
    $pip install "setuptools<60.0" && \
    $pip install wheel
```

> **说明**：项目提供的 Dockerfile 同时将 apt 源替换为清华镜像，并内置 UniDic 安装。

### 3.8 构建镜像

```bash
# 先进入 tdmelodic 仓库文件夹
cd tdmelodic
# 然后执行 docker 的构建指令
docker build -t tdmelodic:latest .
# 若构建时 WSL 存在网络问题需要执行以下指令
docker build --network=host -t tdmelodic:latest .
```

> **说明**：`--network=host` 共享主机网络设置（这个无论在 snap 版本还是 apt 版本都是必要的）。
> 附：`&` 表示异步运行；`&&` 表示先后运行；`|` 是管道符号，前一个命令的输出成为后一个命令的输入。

### 3.9 镜像安装验证（可选）

方式一（样例验证）：

```bash
docker run --rm tdmelodic:latest /bin/bash -c "echo 深層学習 | mecab -d \`mecab-config --dicdir\`/unidic"
```

预期结果：

```text
深層	シンソー	シンソウ	深層	名詞-普通名詞-一般			0
学習	ガクシュー	ガクシュウ	学習	名詞-普通名詞-サ変可能			0
EOS
```

方式二（先进入 docker 再验证）：

```bash
docker run -it --rm tdmelodic:latest
echo 深層学習 | mecab -d `mecab-config --dicdir`/unidic
# 要退出 docker，输入 exit，或直接按 Ctrl+D
```

预期结果同上。

> **说明**：容器内 UniDic 的安装名为 `unidic`；宿主侧的组合词典（3.16 安装）才使用 `tdmelodic`。

### 3.10 克隆 mecab-unidic-neologd

> **注意**：克隆前先 `cd ${WORKDIR}`。

```bash
cd ${WORKDIR}
git clone --depth 1 https://github.com/neologd/mecab-unidic-neologd/
```

### 3.11 解压 seed 词表 CSV

```bash
# WSL 有 unxz 指令
unxz -k `ls mecab-unidic-neologd/seed/*.xz | tail -n 1`
```

```bash
# 如果没有 unxz 指令，用容器代替执行
docker run --rm -v $(pwd):/root/workspace tdmelodic:latest \
    unxz -k `ls mecab-unidic-neologd/seed/*.xz | tail -n 1`
```

> **说明**：解压后将会生成 `mecab-unidic-user-dict-seed.yyyymmdd.csv` 这个文件（yyyymmdd 为具体日期）。

### 3.12 推断前过滤

```bash
docker run --rm -v $(pwd):/root/workspace tdmelodic:latest \
    tdmelodic-neologd-preprocess \
    --input `ls mecab-unidic-neologd/seed/mecab-unidic-user-dict-seed*.csv | tail -n 1` \
    --output neologd_modified.csv \
    --no-rmdups --no-rm_wrong_yomi
```

> **说明**：这一步过滤 `mecab-unidic-user-dict-seed.yyyymmdd.csv` 的文件内容；其中 `--no-rmdups` 表示不删除重复词条，`--no-rm_wrong_yomi` 表示不删除读音错误的词条。

### 3.13 大音调词典推断

```bash
docker run --rm -v $(pwd):/root/workspace tdmelodic:latest \
    tdmelodic-convert \
    -m unidic \
    --input neologd_modified.csv \
    --output ${WORKDIR}/tdmelodic_original.csv
cp ${WORKDIR}/tdmelodic_original.csv ${WORKDIR}/tdmelodic.csv # backup
```

> **注意**：这一步可能需要花数小时！！
> **说明**：以上命令在 `${WORKDIR}` 下执行；`-v $(pwd):/root/workspace` 把当前目录挂载为容器内的 `/root/workspace`。若容器内输出路径报错，可把输出路径写为 `/root/workspace/tdmelodic_original.csv`（与挂载目录同一位置）。

### 3.14 推断后过滤/修正

```bash
cp ${WORKDIR}/tdmelodic.csv ${WORKDIR}/tdmelodic.csv.bak
docker run --rm -v $(pwd):/root/workspace tdmelodic:latest \
    tdmelodic-modify-unigram-cost \
    -i tdmelodic.csv.bak \
    -o tdmelodic.csv
```

> **说明**：这一步结束，推断步骤已全部完成，接下来只需要对前面下载的 UniDic 词典进行结合和安装。

### 3.15 与 UniDic 词典结合

找一个临时文件夹，把 `unidic-mecab_kana-accent-2.1.2_src.zip` 解压到这个文件夹中，然后把上一步获得的 `tdmelodic.csv` 与 `lex.csv` 进行拼接：

```bash
# 打开到解压出的文件夹内
cat ${TDMELODIC_CSV} >> lex.csv
# ${TDMELODIC_CSV} 是 tdmelodic.csv 所在位置
```

### 3.16 安装组合词典

```bash
# 添加文件权限
chmod +x configure
# 对于 WSL，最后安装复合词典 UniDic-tdmelodic 需要先做 3 件事
sudo apt install make
sudo apt install mecab
sudo apt install libmecab-dev
# 配置、编译并安装
./configure
make
sudo make install
```

> **说明**：模块总文档 5.2 只写了 `make` 与 `sudo make install`，此处补上 `./configure` 一步，与 `Dockerfile` 内 UniDic 的安装序列（`./configure && make && make install`）保持一致。
> 安装完成后，组合词典位于 `$(mecab-config --dicdir)/tdmelodic`。

到这里，恭喜你已经完成了所有的 tdmelodic 配置步骤。

## 4. 验证方式

### 4.1 镜像验证

与 3.9 相同：`深層学習` 的预期输出逐字对照。

### 4.2 组合词典验证

```bash
echo 一昔前は人工知能のプログラミング言語といえばCommon LispやPrologだった。 | \
    mecab -d `mecab-config --dicdir`/tdmelodic/
```

预期输出（重点：`人工知能`、`プログラミング言語` 等复合词作为整词返回）：

```text
一昔	ヒトムカシ	ヒトムカシ	一昔	名詞-普通名詞-一般			2,3
前	マエ	マエ	前	名詞-普通名詞-副詞可能			1
は	ワ	ハ	は	助詞-係助詞
人工知能	ジ[ンコーチ]ノー	ジンコウチノウ	人工知能	名詞-固有名詞-一般			@
の	ノ	ノ	の	助詞-格助詞
プログラミング言語	プ[ログラミングゲ]ンゴ	プログラミングゲンゴ	プログラミング言語	名詞-固有名詞-一般			@
と	ト	ト	と	助詞-格助詞
いえ	イエ	イウ	言う	動詞-一般	五段-ワア行	仮定形-一般	0
ば	バ	バ	ば	助詞-接続助詞
Common Lisp	コ[モンリ]スプ	コモンリスプ	Common Lisp	名詞-固有名詞-一般			@
や	ヤ	ヤ	や	助詞-副助詞
Prolog	プ[ロログ	プロログ	Prolog	名詞-固有名詞-一般			@
だっ	ダッ	ダ	だ	助動詞	助動詞-ダ	連用形-促音便
た	タ	タ	た	助動詞	助動詞-タ	終止形-一般
。			。	補助記号-句点
EOS
```

输出字段含义见 `tdmelodic 使用教程.md` 3.2。

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| `docker build` 网络超时/失败 | WSL 网络问题 | 改用 `docker build --network=host -t tdmelodic:latest .`；项目 Dockerfile 已将 apt 源替换为清华镜像 |
| build 报 `unidic-mecab_kana-accent-2.1.2_src.zip not found` | zip 未放入 tdmelodic 构建上下文 | 回到 3.6 下载并放入 `${WORKDIR}/tdmelodic/`，再重新构建 |
| setuptools 版本报错 | 镜像内 setuptools 过新 | 直接修改 Dockerfile 加入 `pip install "setuptools<60.0"`；注意构建后在容器内 pip 降级无效（修改不写回镜像） |
| `unxz: command not found` | WSL 未安装 unxz | 用 3.11 的容器兜底命令代替 |
| `make` 或 mecab 相关报错 | 缺少编译依赖 | 按 3.16 先执行 `sudo apt install make`、`mecab`、`libmecab-dev` |
| 3.13 运行数小时无输出 | 推断耗时长属正常现象 | 耐心等待，勿中断 |
| 组合词典验证报「词典不存在」 | 3.16 未完成 | 检查 `ls $(mecab-config --dicdir)` 是否包含 `tdmelodic` |

## 附录：参考链接

- tdmelodic 官方教程（日文）：https://tdmelodic.readthedocs.io/ja/latest/pages/introduction.html
- tdmelodic：https://github.com/PKSHATechnology-Research/tdmelodic
- mecab-unidic-neologd：https://github.com/neologd/mecab-unidic-neologd/
- UniDic（基础辞书下载）：https://clrd.ninjal.ac.jp/unidic/back_number.html
