# 井场物资调度管理系统（纯客户端）

基于 **Python + SQLite + PySide6** 的桌面物资调度应用，**仅连接主机共享的 wellsite.db**，不在 exe 旁生成本机库。支持：

- 仓库管理、物料管理、调度记录管理
- Excel 导出、拓扑可视化
- 登录与角色（管理员 / 普通用户）

## 环境要求

- **操作系统**：主要在 **Windows** 开发与使用（任务栏图标等逻辑针对 Windows）；其他平台未专门验证。
- **Python**：建议 **3.10 及以上**（需与 PySide6 当前 wheel 兼容）。

## 启动步骤

1. **安装依赖**（建议在项目根目录使用虚拟环境）：

```bash
pip install -r requirements.txt
```

2. **运行应用**：

```bash
python main.py
```

启动后会弹出登录窗口；通过验证后进入主界面。

## 默认账号（仅当数据库中尚无用户时自动创建）

首次运行若不存在用户表数据，会写入演示账号：

| 用户名   | 密码     | 角色   |
|----------|----------|--------|
| `admin`  | `132123` | 管理员 |
| `wgd123` | `112233`   | 普通用户 |

若已有历史数据库，默认账号可能已存在或被改过，请以实际库为准。

## 数据与文件位置

- **SQLite 数据库**：必须使用主机共享路径上的 `wellsite.db`（通过 `network_settings.json` 或首次运行向导配置）。  
- **源码运行**：与打包版相同，须配置可访问的共享 `wellsite.db`；`database.Database` 不接受默认本机路径，也不会在项目根自动建库。  
- **打包 exe**：与 exe 同目录有 `network_settings.json` 等配置，**不会**在 exe 旁自动生成本机 `wellsite.db`。  
- **记住登录**：勾选「记住」后会在同目录生成 `remembered_login.json`（含 Base64 密码，非高强度加密），勿在公用电脑使用；取消勾选并成功登录后会删除该文件。  
- **共享（与 `wellsite.db` 同目录，UNC）**：`wellsite.db` 与调度附图目录 **`Picture record`**。多台客户端应对该共享文件夹有读写权限（与打开数据库相同）。
- **本机（exe 旁或开发时项目根）**：`network_settings.json`、`remembered_login.json`、**`warehouse_layout.json`**、**`backup_ui_settings.json`**、拓扑与备份页背景目录 **`Background images`**。每台电脑各自一份，不随共享库同步。
- **备份与恢复**：  
  - 界面「数据备份」页中 **「立即备份」** 导出的是 `backup.json`，内容为仓库 / 物料 / 调度等摘要，**不能**完整还原库存与调度明细。  
  - **完整恢复**请使用当时复制的 **`wellsite.db` 整文件**，并在**完全退出程序**后，使用脚本覆盖（见下节）。

## 数据库恢复脚本

用备份的 `wellsite.db` 覆盖当前库前，请先关闭本程序（含打包后的 exe）。

```text
python scripts\restore_wellsite_db.py "D:\备份\wellsite.db"
```

可选参数 `-t` 指定目标路径，例如指向发布目录下的 `wellsite.db`。详见 `scripts\restore_wellsite_db.py` 文件头注释。

## 打包 Windows 可执行文件

1. **进入项目根目录**（例如 `c:\wellsite_system`）。  
2. **激活虚拟环境**（第一步；之后在同一窗口里用 `pip` 才不会装到全局）：  
   - **CMD**：`cd /d c:\wellsite_system` → `.venv\Scripts\activate.bat`  
   - **PowerShell**：`cd c:\wellsite_system` → `.venv\Scripts\Activate.ps1`（若禁止脚本，可先执行：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`）  
3. **首次**在该环境中安装依赖与打包工具：`pip install -r requirements.txt`，再 `pip install pyinstaller`。  
4. 执行 **`build_exe.bat`**（会调用 `scripts\generate_app_icon.py` 与 `warehouse_dispatch.spec`；脚本内部使用 `.venv\Scripts\python.exe`，未激活时双击 bat 也可打包，但**手动敲 pip 命令前请先完成第 2 步**）。  
5. 输出目录为 **`dist\仓库物资调度-客户端\`**（目录模式；`wellsite.db` 与 `Picture record` 在配置的 UNC 上，布局与背景图在 exe 旁）。  
6. 打包完成后会尝试更新桌面快捷方式（与 exe 同名）；若图标未刷新，可按脚本提示处理图标缓存。

图标源图与生成：`assets\app_icon_source.png`，由 `scripts\generate_app_icon.py` 生成（需已安装 `pillow`，见 `requirements.txt`）。

## 功能说明（界面）

- **左侧**：创建仓库、添加与管理物料等操作。  
- **右侧**：拓扑图展示仓库节点及仓库之间的调度连线。  
- **下方**：调度历史表格，可按时间过滤。  
- **导出**：将调度记录导出为 Excel。  
- **备份页**：导出 JSON 摘要；完整灾难恢复依赖复制 `wellsite.db`。

## 依赖一览

见项目根目录 **`requirements.txt`**（含 PySide6、pandas、openpyxl、pillow 等）。
