## 0.技术栈及负责人(暂定)
>前端: `React + Typescript + Vite`，负责人`yanamidaisuki`
>后端: `Supabase`，负责人`RatherHard`
>UniDic: `Python (MeCab)`，负责人`whatisthatzhexue`
---
## 1.分支说明
-  `main`: **正式版本所在分支。该分支在开发阶段仅用于维护docs文件夹等协作文档。请勿push未测试稳定的功能。**
- `dev`: **开发版本分支。前期由仓库所有者汇总frontend, backend, unidict上的内容。**
- `frontend`: **前端内容分支。**
- `backend`: **后端内容分支。**
- `unidic`: **UniDic声调提取分支。此分支下不放置完整的UniDic词典文件，仓库使用者自行配置。**
- (`worker`): *未来可能加入的分支。用于LLM声调识别和情感分析。*
---
## 2.Commit信息说明
本项目commit消息应遵循*Conventional Commits(约定式提交规范)*
- 使用`<类型>[可选的作用域]: <描述>`的格式。
- 清晰交代本次commit的**新内容与旧内容的修复/更新**
*例如：`refactor(unidic): 重制了语音语调的结果输出格式`*
---
## 3.git项目启动 + 贡献指南
*项目从零启动示例：*
```bash
#先下载main分支内容，再本地切换到对应分支。
git clone https://github.com/whatisthatzhexue/Utaer.git
cd Utaer
git branch <分支名称>
git checkout <分支名称>
```
项目启动（无本地仓库，从远程仓库单分支继续开发）示例：
```bash
#方法一：在个人电脑的项目开发文件夹下，直接拉取特定分支（包括该分支所有历史信息）
git clone -b <分支名称> https://github.com/whatisthatzhexue/Utaer.git
cd Utaer
#方法二：若远程仓库历史过长，可针对该分支仅做浅克隆（忽略历史版本）。当前文件夹直接成为仓库。
git init
git remote add origin https://github.com/whatisthatzhexue/Utaer.git
git fetch origin <分支名称或分支ID> --depth 1
git checkout <分支名称或分支ID>
```
*开发进度中继（有本地仓库，从远程仓库单分支继续开发）示例：*
```bash
#方法一：立即将远程仓库上的分支内容更新到本地
git pull origin <分支名称>
#方法二：将远程仓库上特定分支的内容merge到本地仓库
git fetch origin <分支名称>
git merge origin/<分支名称>
```
*本地commit示例：*
```bash
#在Utaer文件夹下
git add <更改文件的路径>
git commit -m "feat: 在此处清晰地说明本次commit的变动"
```
*注意！！请提前写好.gitignore：只上传源代码，不要上传编译结果！！*
*提交到远程仓库示例：*
```bash
#若干次commit操作完成后
git push origin <分支名称>
```
---
## 4. 文档同步 + 分支同步规则 + 注意事项
本项目的各类文档（API接口文档、项目计划书等）均会在`main`分支`docs`文件夹下更新。
- **主干保护**：`main` 和 `dev` 分支设置为 **“禁止直接推送 (Protected)”**，必须通过 PR 并经过owner审查才能合入。
- **合并方式**：统一采用 `Merge Commit`

Supabase部分**严禁**将 `.env` 文件上传：
- 根目录必须包含 **`.env.example`**（模板），列出所有必需的环境变量名（如 `VITE_SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`）。