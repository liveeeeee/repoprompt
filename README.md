# ⚡ RepoPrompt

> **Pure Python, Zero-Dependency Codebase Packager for LLMs.**  
> Pack entire code repositories into clean, AI-optimized prompts in milliseconds.  
> 纯 Python 3 原生标准库实现，零第三方依赖、免装 Node.js、毫秒级将工程代码库打包为大模型上下文的极简神器！

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/liveeeeee1203)
[![GitHub Sponsor](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?style=for-the-badge&logo=github)](https://github.com/sponsors/liveeeeee)

---

## 💡 Why RepoPrompt? (为什么选择 RepoPrompt？)

When feeding an entire codebase to LLMs (ChatGPT, Claude, DeepSeek, Cursor), popular tools like [Repomix](https://github.com/yamadashy/repomix) (15k+ Stars) are great, but have significant friction:
- ❌ **Forces Node.js & npm runtime**: Millions of Python, DevOps, Go, C++, and backend developers don't have Node.js installed on their machines or production servers.
- ❌ **Bloated dependencies**: Requires downloading hundreds of npm packages.
- ❌ **Slow startup**: Node.js runtime initialization overhead.

**RepoPrompt solves this once and for all:**
- ✅ **0 Third-Party Dependencies (零依赖)**: Built 100% on the Python Standard Library.
- ✅ **Single File, Drop & Run (单文件即用)**: Copy `repoprompt.py` anywhere and run immediately.
- ✅ **Lightning Fast (毫秒级启动)**: Executes in ~0.02s without runtime boot overhead.
- ✅ **AI & LLM Optimized (大模型专属优化)**: Adaptive backticks, XML & Markdown dual output, and native `--copy` clipboard support.

---

### 🥊 Comparison Table (代差级优势对比)

| Feature (特性) | **RepoPrompt** (本项目) | **Repomix** (Node.js) | **Gitingest** (Python Web) |
| :--- | :---: | :---: | :---: |
| **Dependencies (依赖)** | **0 (Pure Standard Library)** | Node.js + npm packages | FastAPI + Uvicorn + Web |
| **Installation (安装门槛)** | **1 file or `pip install`** | `npm install -g repomix` | `pip install gitingest` |
| **Startup Speed (启动速度)** | **~0.02s (Instant)** | ~1.5s | ~0.8s |
| **.gitignore Support** | ✅ Full recursive + negation (`!`) | ✅ Yes | ⚠️ Partial |
| **Markdown Collision Safety** | ✅ Adaptive dynamic backticks | ⚠️ Basic | ⚠️ Basic |
| **Clipboard One-Click** | ✅ Cross-platform (`--copy`) | ✅ Yes | ❌ Browser only |
| **XML Output for Claude** | ✅ Native (`--xml`) | ✅ Yes | ❌ No |

---

## 🚀 Quick Usage (快速使用)

### Method 1: Drop & Run (免安装直接运行)

Just download or copy `repoprompt.py`:

```bash
# Pack current directory into repoprompt-output.md
python repoprompt.py

# Pack a specific directory and copy directly to clipboard
python repoprompt.py path/to/project --copy

# Generate Claude-optimized XML format
python repoprompt.py --xml --output codebase.xml
```

### Method 2: Global CLI via pip

```bash
pip install .
# or once on PyPI:
# pip install repoprompt

# Now run anywhere:
repoprompt --copy
```

---

## 🛡️ Battle-Tested Defenses (经受红蓝对抗检验的硬核鲁棒性)

RepoPrompt has undergone adversarial code auditing and edge-case stress testing:

1. **Adaptive Backtick Fence (自适应反引号)**:
   Dynamically scans the codebase for the maximum contiguous backticks count $N$ and wraps file contents in $N+1$ backticks (e.g. ```` or `````). This completely prevents nested Markdown blocks from breaking ChatGPT or Claude syntax rendering.
2. **Standard-Compliant `.gitignore` Engine**:
   Correctly parses negation rules (`!keep_me.log`), root-anchored rules (`/secret.key`), and nested subdirectory `.gitignore` files.
3. **Self-Ingestion Shield (防自吞噬机制)**:
   Automatically ignores previous output files (`repoprompt-output.*`, `repomix-output.*`) so repeated runs never exponentially bloat your prompt.
4. **Resilient Character Encoding**:
   Gracefully falls back from UTF-8 to GB18030 / GBK and Latin-1. Legacy or Asian character sets never crash the packer.
5. **Minified Code Chunking**:
   Detects minified single-line code bombs (>1,500 chars/line) and splits them into safe chunks, protecting the LLM's single-line attention window.

---

## 🛠️ CLI Options (常用参数)

```text
Usage: python repoprompt.py [PATH] [OPTIONS]

Options:
  --xml                  Output in Claude-optimized XML format (default is Markdown)
  --output <FILE>        Custom output destination filename
  --copy                 Automatically copy the packed output to system clipboard
  --include-minified     Include minified JS/CSS files (excluded by default)
  --max-depth=<INT>      Maximum folder recursion depth (default: 8)
  --self-test            Run built-in offline security and adversarial test suite
```

---

## 🧪 Run Tests (离线自检)

```bash
python repoprompt.py --self-test
```

---

## ☕ Sponsor & Support (赞助与打赏)

RepoPrompt is 100% free and open-source under the MIT license.  
If this tool saved you from installing Node.js or streamlined your AI engineering workflow, consider supporting its development:

👉 **[Donate via PayPal (通过 PayPal 赞助作者)](https://paypal.me/liveeeeee1203)**  
👉 **[Sponsor on GitHub](https://github.com/sponsors/liveeeeee)**  

*Your support helps keep this project lean, fast, and maintained!*

---

## 📄 License

MIT License © 2026 [liveeeeee](https://github.com/liveeeeee)
