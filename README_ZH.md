# agy-cli-statusline

[English](README.md) | 简体中文

适用于 Google Antigravity CLI (`agy`) 的自定义状态栏（Statusline）一键安装与配置工具。

能够自动将 `statusline.py` 脚本放置到用户的 `~/.gemini/antigravity-cli/scripts/` 目录，并自动初始化/更新 `~/.gemini/antigravity-cli/settings.json` 配置。

---

## ✨ 特性

- **执行模式两端对齐**：左侧高亮标识当前会话执行模式（如 `[Accept-Edits]`、`[Planning]`、`[Fast]` 等），未匹配或默认模式自动隐藏，保持界面清爽。
- **智能阈值色彩警示**：
  - **Context 占用**：常规粗体亮白高亮；达到 **20%** 亮黄警示；达到 **50%** 亮红告警。
  - **Quota 剩余**：常规粗体亮白高亮；剩余不足 **50%** 亮黄警示；剩余不足 **20%** 亮红告警。
- **精准宽度自适应**：自动剥离 ANSI 转义颜色代码计算可见列宽，并兼容东亚宽字符，左右两端对齐分毫不差。
- **免手动配置**：直接通过 `uvx` 运行，自动将脚本放入正确的目录并同步更新 `settings.json`。
- **纯标准库实现**：脚本与安装工具均零外部依赖，极速执行。

---

## 🚀 使用方法

无需手动打包或构建 wheel，直接使用 `uvx` 运行即可：

### 1. 一键安装并配置

**通过 Git 仓库直接运行（推荐）：**
```bash
uvx --from git+https://github.com/entr0pia/agy-cli-statusline agy-cli-statusline
```

**本地开发或已克隆仓库内运行：**
```bash
uvx --from . agy-cli-statusline
```

> 运行后会自动完成：
> 1. 拷贝 `statusline.py` 到 `~/.gemini/antigravity-cli/scripts/statusline.py`
> 2. 更新 `~/.gemini/antigravity-cli/settings.json` 中的 `statusLine` 配置项

### 2. 检查当前安装状态

```bash
uvx --from . agy-cli-statusline --status
```

### 3. 卸载状态栏配置

```bash
uvx --from . agy-cli-statusline --uninstall
```

---

## ⚙️ 生成的配置示例

安装完成后，您的 `~/.gemini/antigravity-cli/settings.json` 会自动增加或更新以下配置项：

```json
{
  "statusLine": {
    "type": "command",
    "command": "python C:/Users/<Username>/.gemini/antigravity-cli/scripts/statusline.py",
    "enabled": true,
    "debug": false
  }
}
```

> **调试模式**：将 `"debug": true`（或在安装时指定 `--debug` 参数，或配置环境变量 `AGY_STATUSLINE_DEBUG=1`）会把最近一次接收到的原始 payload 写入 `~/.gemini/antigravity-cli/last_statusline_payload.json` 便于排查。默认禁用调试文件写入以确保极致的终端刷新性能。

重新启动 `agy` 即可看到新状态栏生效。

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 协议开源。

