# 自动化测试问题记录

> 由游戏测试 AGENT 自动维护。每次执行 `run_tasks.py` 后更新。
> 问题分析由独立 AGENT 负责，本文件仅记录观察到的现象。

---

## 执行记录

<!-- 最新记录在最上方 -->

---

### 第 1 次执行

| 字段 | 内容 |
|---|---|
| 执行时间 | 2026-06-06 17:03:20 ~ 17:10:08 |
| 退出码 | 0 |
| 日志文件 | `src/img/debug_captures/run_20260606_170320.log` |
| 游戏窗口 | 找到（rect=144,79,1764,1035），标题乱码 |

#### ISSUE-001 · 师门任务：按钮未找到，完成 0 次

- **严重程度**: 高（任务未执行）
- **触发时间**: 2026-06-06 17:03:21
- **现象**:
  - 脚本启动后立即检测师门任务按钮
  - 日志报告 `button not found   all daily tasks completed`，0.16 秒内结束，完成 0 次迭代
- **相关日志**:
  ```
  17:03:21,440 - __main__ - INFO - === Starting 师门任务 ===
  17:03:21,440 - bot.tasks - INFO - 师门任务 iteration 1
  17:03:21,603 - bot.tasks - INFO - 师门任务 button not found   all daily tasks completed
  17:03:21,603 - bot.tasks - INFO - 师门任务 finished   completed 0 iteration(s)
  ```
- **相关截图**: 本次未产生师门任务专属截图
- **备注**: 日志中中文字符显示为乱码（见 ISSUE-003），原始日志为唯一参考

---

#### ISSUE-002 · 秘境降妖：无完成检测模板，使用固定 300s 等待

- **严重程度**: 中（功能可运行，但无法感知任务真实结束时间）
- **触发时间**: 2026-06-06 17:05:08
- **现象**:
  - 脚本成功导航并打开活动面板（多次检测到 `ClosePanel_X2.png`）
  - 任务开始后立即报告"无完成模板"，进入 300 秒硬等待
  - 300 秒后假定完成并继续
- **相关日志**:
  ```
  17:05:08,138 - bot.tasks - INFO - 秘境降妖 started
  17:05:08,138 - bot.tasks - INFO - 秘境降妖: no completion template available; waiting fixed 300.0s
  17:10:08,138 - bot.tasks - INFO - 秘境降妖: fixed wait done, assuming completed
  17:10:08,138 - bot.tasks - INFO - 秘境降妖 task flow finished
  ```
- **相关截图**:
  - `src/img/debug_captures/dbg_grid_window_1780736705.png`
  - `src/img/debug_captures/dbg_grid_desktop_1780736705.png`
  - `src/img/debug_captures/dbg_mouse_stop_1780736706.png`

---

#### ISSUE-003 · 日志中文字符乱码（编码问题）

- **严重程度**: 中（任务名称不可读，影响日志可读性）
- **触发时间**: 全程
- **现象**:
  - 游戏窗口标题显示为 `'???h{^??8n??ezz'`（GBK 被错误解释为其他编码）
  - 任务名称 师门任务、秘境降妖、宝图任务 均显示为乱码字节序列
  - 日志文件为 UTF-16 LE（PowerShell Tee-Object 默认输出），Python 程序以 GBK/UTF-8 写入 stderr，编码不一致
- **相关日志**（原始乱码示例）:
  ```
  python.exe : ... Using game window: '?h{^?8n??ezz'  ...
              FullyQualifiedErrorId : NativeCommandError
  __main__ - INFO - === Starting^??N?R ===
  ```
- **相关截图**: 无（日志编码问题）

---

#### ISSUE-004 · 宝图任务：执行状态在日志中不可见

- **严重程度**: 中（无法确认宝图任务是否正常执行）
- **触发时间**: 2026-06-06 17:10:08
- **现象**:
  - 日志在秘境降妖完成后 (`17:10:08`) 直接显示 `All tasks done.`
  - 未观察到明确的"Starting 宝图任务"或"宝图任务 finished"日志条目
  - 可能原因：宝图任务瞬间完成（检测为已完成状态）；或该任务名称乱码与秘境降妖条目混淆
- **相关日志**:
  ```
  17:10:08,138 - __main__ - INFO - === 秘境降妖 finished: OK ===
  17:10:08,138 - __main__ - INFO - All tasks done.
  ```
- **相关截图**: 无（任务执行期间无新截图产生）

---

#### ISSUE-005 · PowerShell 捕获 stderr 产生 NativeCommandError 噪音

- **严重程度**: 低（不影响运行，干扰日志阅读）
- **触发时间**: 2026-06-06 17:03:21
- **现象**:
  - Python 脚本向 stderr 输出日志时，PowerShell 通过 `2>&1` 合并流，将非空 stderr 内容误判为错误
  - 每行 Python 日志在日志文件中多出 `NativeCommandError` / `RemoteException` 包装
- **相关日志**:
  ```
  python.exe : 2026-06-06 17:03:21,438 - __main__ - INFO - ...
  At run_capture.ps1:23 char:5
      + CategoryInfo : NotSpecified: ... NativeCommandError
      + FullyQualifiedErrorId : NativeCommandError
  ```
- **相关截图**: 无

