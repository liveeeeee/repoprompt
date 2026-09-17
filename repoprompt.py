"""
RepoPrompt: Pure Python, Zero-Dependency Codebase Packager for LLMs.
A lightweight, battle-tested, lightning-fast alternative to Repomix (no Node.js required!).
Author: liveeeeee (https://github.com/liveeeeee)
Sponsorship: https://paypal.me/liveeeeee1203
License: MIT
"""

import fnmatch
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Set, Tuple, Optional, Dict, Any


from xml.sax.saxutils import escape, quoteattr

PAYPAL_URL = "https://paypal.me/liveeeeee1203"
VERSION = "1.2.0"

# 构建产物目录（可通过 --keep-build-dirs 豁免）
BUILD_DIRS = ["dist", "build", "out", "target", "bin", "obj"]

# 基础默认全局忽略的目录与文件（内置防自吞噬规则）
BASE_IGNORE_PATTERNS = [
    ".git", ".svn", ".hg",
    "node_modules", "bower_components",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", ".env", ".env.*",
    ".idea", ".vscode", ".DS_Store", "Thumbs.db",
    "repomix-output.*", "pyrepomix-output.*", "repoprompt-output.*",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.svg", "*.webp",
    "*.mp4", "*.mp3", "*.wav", "*.avi", "*.mov",
    "*.zip", "*.tar", "*.gz", "*.7z", "*.rar",
    "*.pdf", "*.docx", "*.xlsx", "*.pptx",
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock"
]
DEFAULT_IGNORE_PATTERNS = BASE_IGNORE_PATTERNS + BUILD_DIRS

# 常见纯文本与代码文件扩展名
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".sass",
    ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx", ".cs", ".go", ".rs", ".java",
    ".kt", ".kts", ".swift", ".m", ".mm", ".rb", ".php", ".sh", ".bash", ".zsh",
    ".ps1", ".bat", ".cmd", ".lua", ".r", ".dart", ".scala", ".clj", ".ex", ".exs",
    ".sql", ".graphql", ".proto",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf",
    ".md", ".markdown", ".rst", ".txt", ".csv",
    ".dockerignore", "Dockerfile", "Makefile"
}


def _pattern_to_regex(pat: str, is_rooted: bool) -> Any:
    """
    将 .gitignore 通配符模式转换为高效且符合 Git 规范的正则表达式。
    支持:
    - ** 零层与多层目录通配 (如 a/**/b 匹配 a/b 与 a/x/y/b)
    - * 匹配单层文件名或目录名中的非斜杠字符
    - ? 匹配单个非斜杠字符
    - [abc] 字符组
    - 根锚定与带斜杠相对路径精确匹配
    """
    i = 0
    n = len(pat)
    res = []
    while i < n:
        if pat[i:i+4] == "/**/":
            res.append(r"(?:/.+/|/)")
            i += 4
        elif pat[i:i+3] == "**/":
            res.append(r"(?:^|.*/)")
            i += 3
        elif pat[i:i+3] == "/**":
            res.append(r"(?:/.*)?")
            i += 3
        elif pat[i:i+2] == "**":
            res.append(r".*")
            i += 2
        elif pat[i] == "*":
            res.append(r"[^/]*")
            i += 1
        elif pat[i] == "?":
            res.append(r"[^/]")
            i += 1
        elif pat[i] == "[":
            j = i + 1
            if j < n and pat[j] in ("!", "^"):
                j += 1
            if j < n and pat[j] == "]":
                j += 1
            while j < n and pat[j] != "]":
                j += 1
            if j < n:
                bracket_content = pat[i+1:j]
                if bracket_content.startswith("!"):
                    bracket_content = "^" + bracket_content[1:]
                res.append(f"[{bracket_content}]")
                i = j + 1
            else:
                res.append(re.escape(pat[i]))
                i += 1
        else:
            res.append(re.escape(pat[i]))
            i += 1

    pattern_regex = "".join(res)
    # Git 规范: 若 pattern 包含 / (无论是开头还是中间)，均严格相对于其 scope 目录匹配；
    # 若不包含 /，则可在任意子目录层级的文件名/目录名上递归匹配。
    if is_rooted or ("/" in pat):
        regex_str = f"^{pattern_regex}$"
    else:
        regex_str = f"(?:^|.*/){pattern_regex}$"
    return re.compile(regex_str)


class GitIgnoreEngine:
    """
    轻量且贴合 Git 规范的 GitIgnore 引擎。
    支持：
    1. 根目录与子目录 .gitignore 嵌套继承
    2. /pattern 根路径锚定匹配（仅匹配本 .gitignore 所在目录对应层级）
    3. !pattern 否定反选规则
    4. pattern/ 目录限定匹配（普通同名文件不受影响）
    5. ** 零层与多层目录通配符
    6. 规则来源跟踪与构建目录提示智能防误报
    """

    def __init__(self, root_dir: Path, extra_ignores: Optional[List[str]] = None, keep_build_dirs: bool = False):
        self.root_dir = root_dir.resolve()
        # rule: (scope_dir, is_neg, clean_pat, is_dir_only, is_rooted, source, regex)
        self.rules: List[Tuple[Path, bool, str, bool, bool, str, Any]] = []
        self._init_default_rules(extra_ignores or [], keep_build_dirs=keep_build_dirs)
        self._collect_all_gitignores()

    def _add_rule(self, scope_dir: Path, is_neg: bool, pat: str, is_dir_only: bool, is_rooted: bool, source: str):
        rx = _pattern_to_regex(pat, is_rooted=is_rooted)
        self.rules.append((scope_dir, is_neg, pat, is_dir_only, is_rooted, source, rx))

    def _init_default_rules(self, extra_ignores: List[str], keep_build_dirs: bool = False):
        for pat in BASE_IGNORE_PATTERNS:
            self._add_rule(self.root_dir, False, pat, is_dir_only=False, is_rooted=False, source="default_base")
        if not keep_build_dirs:
            # 构建目录限定为目录专属规则 (is_dir_only=True)，普通构建脚本文件 build 正常保留
            for pat in BUILD_DIRS:
                self._add_rule(self.root_dir, False, pat, is_dir_only=True, is_rooted=False, source="default_build")
        for pat in extra_ignores:
            self._add_rule(self.root_dir, False, pat, is_dir_only=False, is_rooted=False, source="extra")

    def _collect_all_gitignores(self):
        for curr_root, dirs, files in os.walk(self.root_dir, followlinks=False):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__"]]
            if ".gitignore" in files:
                git_path = Path(curr_root) / ".gitignore"
                self._parse_file(git_path, Path(curr_root))

    def _parse_file(self, filepath: Path, scope_dir: Path):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(r"\#"):
                        line = line[1:]
                    elif line.startswith("#"):
                        continue

                    is_neg = False
                    if line.startswith(r"\!"):
                        line = line[1:]
                    elif line.startswith("!"):
                        is_neg = True
                        line = line[1:].strip()

                    is_dir_only = line.endswith("/")
                    clean_pat = line.rstrip("/")

                    # 处理 / 开头的根锚定规则
                    is_rooted = clean_pat.startswith("/")
                    if is_rooted:
                        clean_pat = clean_pat.lstrip("/")

                    if clean_pat:
                        self._add_rule(scope_dir, is_neg, clean_pat, is_dir_only, is_rooted, source="user")
        except Exception:
            pass

    def _check_path(self, path: Path, is_dir: bool = False, ignore_source: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        resolved_path = path.resolve()
        try:
            rel_to_root = resolved_path.relative_to(self.root_dir).as_posix()
        except ValueError:
            return False, None

        ignored = False
        last_matched_source = None

        for scope_dir, is_neg, pat, is_dir_only, is_rooted, source, rx in self.rules:
            if ignore_source and source == ignore_source:
                continue
            if is_dir_only and not is_dir:
                continue

            try:
                rel_to_scope = resolved_path.relative_to(scope_dir).as_posix()
            except ValueError:
                continue

            if rx.match(rel_to_scope):
                if is_neg:
                    ignored = False
                    last_matched_source = None
                else:
                    ignored = True
                    last_matched_source = source

        return ignored, last_matched_source

    def is_ignored(self, path: Path, is_dir: bool = False) -> bool:
        return self._check_path(path, is_dir=is_dir)[0]

    def is_ignored_by_default_build_only(self, path: Path, is_dir: bool = True) -> bool:
        """检查路径是否仅由默认构建目录规则忽略（若用户规则自身已忽略则返回 False）"""
        ignored, _ = self._check_path(path, is_dir=is_dir)
        if not ignored:
            return False
        ignored_without_build, _ = self._check_path(path, is_dir=is_dir, ignore_source="default_build")
        return not ignored_without_build


def is_binary_file(file_path: Path) -> bool:
    """通过读取首部 1024 字节嗅探是否包含 null 字节来判定是否二进制文件"""
    ext = file_path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return False
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except Exception:
        return True
    return False


MINIFIED_EXTENSIONS = {".js", ".mjs", ".cjs", ".css", ".map"}


def is_minified_file(file_path: Path, sample_lines: int = 5) -> bool:
    """智能嗅探是否为前端 minified 压缩文件（如 bundle.min.js）"""
    name = file_path.name.lower()
    if ".min." in name or "-min." in name or ".bundle.js" in name:
        return True

    ext = file_path.suffix.lower()
    # 仅针对前端打包压缩常见格式进行内容嗅探，绝不因单行长而误杀普通后端与通用源码
    if ext not in MINIFIED_EXTENSIONS:
        return False

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            total_chars = 0
            lines_read = 0
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                lines_read += 1
                line_len = len(line)
                total_chars += line_len
                # 单行字符极大 (>10000) 判定为压缩文件
                if line_len > 10000:
                    return True
            if lines_read > 0 and (total_chars / lines_read) > 3000:
                return True
    except Exception:
        pass
    return False


def get_adaptive_backticks(content: str) -> str:
    """
    自适应反引号计算，防止源码内含有 ``` 导致 Markdown 代码块结构提前截断崩溃。
    动态计算文本中连续出现反引号的最大长度 N，返回 N + 1 个反引号作为围栏。
    """
    matches = re.findall(r"`+", content)
    if not matches:
        return "```"
    max_ticks = max(len(m) for m in matches)
    return "`" * max(3, max_ticks + 1)


def read_file_safe(file_path: Path) -> str:
    """
    多重编码平滑回退安全读取（防止 GBK/ANSI/Windows-1252 崩溃）
    """
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"[Error reading file: {e}]"
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def format_minified_content(content: str, max_line_len: int = 2000) -> str:
    """防止单行 20 万字符打崩 LLM 单行注意力，按安全长度切片纯换行折行"""
    lines = content.splitlines(keepends=True)
    safe_lines = []
    for line in lines:
        if len(line) > max_line_len:
            chunks = [line[i:i + max_line_len] for i in range(0, len(line), max_line_len)]
            safe_lines.append("\n".join(chunks))
        else:
            safe_lines.append(line)
    return "".join(safe_lines)


def sanitize_for_xml(text: str) -> str:
    """过滤 XML 1.0 非法字符 (允许 \\t=0x09, \\n=0x0A, \\r=0x0D)"""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F]", "", text)



def build_directory_tree(
    root_dir: Path,
    gitignore: GitIgnoreEngine,
    max_depth: int = 6,
    include_minified: bool = False,
    max_file_size: int = 10 * 1024 * 1024
) -> str:
    """生成整洁清晰的 ASCII 目录树，智能剔除忽略文件、超大文件、二进制与混淆文件"""
    tree_lines = [f"{root_dir.name}/"]

    def _walk(directory: Path, prefix: str, depth: int):
        if depth > max_depth:
            tree_lines.append(f"{prefix}└── ... (depth limit reached)")
            return

        try:
            items = []
            for item in directory.iterdir():
                try:
                    # 跳过断链或指向目录的符号链接，防止死循环
                    if item.is_symlink():
                        if not item.exists() or item.is_dir():
                            continue
                    is_d = item.is_dir()
                    if gitignore.is_ignored(item, is_dir=is_d):
                        continue
                    if not is_d:
                        if is_binary_file(item):
                            continue
                        try:
                            if item.stat().st_size > max_file_size:
                                continue
                        except OSError:
                            continue
                        if not include_minified and is_minified_file(item):
                            continue
                    items.append(item)
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            return

        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        count = len(items)
        for i, item in enumerate(items):
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")

            if item.is_dir():
                extension = "    " if is_last else "│   "
                _walk(item, prefix + extension, depth + 1)

    _walk(root_dir, "", 1)
    return "\n".join(tree_lines)


def estimate_tokens_approx(text: str) -> int:
    """常数级近似 Token 估算（英文~4字符/Token，中日韩代码~1.5字符/Token）"""
    length = len(text)
    if length == 0:
        return 0
    return max(1, int(length / 3.5))


def copy_to_clipboard(text: str) -> bool:
    """纯标准库跨平台安全剪贴板注入（优先 Windows clip，Linux xclip/wl-copy，macOS pbcopy）"""
    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            proc.communicate(input=text.encode("utf-16le"))
            return proc.returncode == 0
        elif sys.platform == "darwin":
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode("utf-8"))
            return proc.returncode == 0
        else:
            for tool in [["wl-copy"], ["xclip", "-selection", "clipboard"]]:
                try:
                    proc = subprocess.Popen(tool, stdin=subprocess.PIPE)
                    proc.communicate(input=text.encode("utf-8"))
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
    except Exception:
        pass
    return False


def pack_codebase(
    target_dir: str = ".",
    output_format: str = "markdown",
    include_minified: bool = False,
    output_filename: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,
    max_depth: int = 8,
    keep_build_dirs: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """核心打包函数，支持 Markdown 与 XML 格式"""
    start_time = time.time()
    root_path = Path(target_dir).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Directory not found: {target_dir}")

    # 动态将输出文件加入忽略，防自身吞噬
    extra_ignores = []
    if output_filename:
        extra_ignores.append(Path(output_filename).name)

    gitignore = GitIgnoreEngine(root_path, extra_ignores=extra_ignores, keep_build_dirs=keep_build_dirs)

    valid_files: List[Path] = []
    warned_build_dirs: Set[str] = set()
    warned_minified_files: Set[str] = set()

    for root, dirs, files in os.walk(root_path, followlinks=False):
        d_path = Path(root)
        try:
            rel_depth = len(d_path.relative_to(root_path).parts)
            if rel_depth >= max_depth:
                dirs[:] = []
                continue
        except ValueError:
            pass

        # 检查是否命中了默认构建目录并向 stderr 友好提醒 (仅纯粹由默认构建规则忽略时提示)
        if not keep_build_dirs:
            for d in list(dirs):
                dir_path = d_path / d
                if d.lower() in BUILD_DIRS and gitignore.is_ignored_by_default_build_only(dir_path, is_dir=True):
                    rel_d = dir_path.relative_to(root_path).as_posix()
                    if rel_d not in warned_build_dirs:
                        warned_build_dirs.add(rel_d)
                        sys.stderr.write(f"[RepoPrompt] 提示: 默认忽略构建目录 '{rel_d}' (如需包含源码请使用 --keep-build-dirs)\n")

        # 实时根据 .gitignore 剪枝跳过不扫描的文件夹
        dirs[:] = [d for d in dirs if not gitignore.is_ignored(d_path / d, is_dir=True)]

        for f in files:
            file_path = d_path / f
            try:
                if file_path.is_symlink() and not file_path.exists():
                    continue
                if gitignore.is_ignored(file_path, is_dir=False):
                    continue
                if is_binary_file(file_path):
                    continue
                try:
                    if file_path.stat().st_size > max_file_size:
                        continue
                except OSError:
                    continue
                if not include_minified and is_minified_file(file_path):
                    rel_p = file_path.relative_to(root_path).as_posix()
                    if rel_p not in warned_minified_files:
                        warned_minified_files.add(rel_p)
                        sys.stderr.write(f"[RepoPrompt] 提示: 自动跳过压缩文件 '{rel_p}' (如需包含请使用 --include-minified)\n")
                    continue
                valid_files.append(file_path)
            except (OSError, PermissionError):
                continue

    valid_files.sort(key=lambda x: x.as_posix().lower())

    tree_str = build_directory_tree(
        root_path,
        gitignore,
        max_depth=max_depth,
        include_minified=include_minified,
        max_file_size=max_file_size
    )

    total_lines = 0
    file_blocks = []

    for file_path in valid_files:
        rel_path = file_path.relative_to(root_path).as_posix()
        content = read_file_safe(file_path)
        content = format_minified_content(content)
        line_count = len(content.splitlines())
        total_lines += line_count

        if output_format == "xml":
            safe_rel_path = sanitize_for_xml(rel_path)
            path_attr = quoteattr(safe_rel_path)
            safe_content = sanitize_for_xml(content.rstrip())
            content_escaped = escape(safe_content)
            block = (
                f"<file path={path_attr}>\n"
                f"{content_escaped}\n"
                f"</file>"
            )
        else:
            fence = get_adaptive_backticks(content)
            ext = file_path.suffix.lstrip(".")
            lang_id = ext if ext else ""
            safe_rel_path = rel_path.replace("`", r"\`")
            block = (
                f"### File: `{safe_rel_path}`\n"
                f"{fence}{lang_id}\n"
                f"{content.rstrip()}\n"
                f"{fence}\n"
            )
        file_blocks.append(block)

    if output_format == "xml":
        root_name_attr = quoteattr(sanitize_for_xml(root_path.name))
        tree_escaped = escape(sanitize_for_xml(tree_str))
        final_output = (
            f"<project name={root_name_attr}>\n"
            f"  <generated_by>RepoPrompt v{VERSION} - Zero-Dependency Codebase Packager</generated_by>\n"
            f"  <directory_structure>\n{tree_escaped}\n  </directory_structure>\n"
            f"  <files>\n" + "\n".join(file_blocks) + "\n  </files>\n"
            f"</project>\n"
        )
    else:
        final_output = (
            f"# Project: {root_path.name}\n\n"
            f"> Generated by **[RepoPrompt](https://github.com/liveeeeee/repoprompt)** v{VERSION}  \n"
            f"> Pure Python, Zero-Dependency Codebase Packager for LLMs.  \n"
            f"> Support the project: [{PAYPAL_URL}]({PAYPAL_URL})\n\n"
            f"## Directory Structure\n\n"
            f"```text\n{tree_str}\n```\n\n"
            f"## File Contents\n\n"
            + "\n".join(file_blocks)
        )

    elapsed = round(time.time() - start_time, 3)
    meta = {
        "files_count": len(valid_files),
        "total_lines": total_lines,
        "elapsed_sec": elapsed,
        "token_estimate": estimate_tokens_approx(final_output)
    }

    return final_output, meta


def self_test():
    """自动化离线自检，包含全部红蓝对抗防御断言"""
    print("[*] 正在执行 RepoPrompt 对抗防御自检...")
    import tempfile
    import xml.etree.ElementTree as ET
    test_dir = Path(tempfile.mkdtemp(prefix="repoprompt_test_"))

    # 1. 基础代码与 .gitignore 否定规则和根路径 /secret.key 锚定规则与 ** 规则
    (test_dir / "src" / "deep").mkdir(parents=True, exist_ok=True)
    with open(test_dir / "src" / "main.py", "w", encoding="utf-8") as f:
        f.write("if x < 5 and y > 2 & z: print('valid xml escaping with \x0c control char')\n")
    with open(test_dir / ".gitignore", "w", encoding="utf-8") as f:
        f.write("*.log\n!important.log\n/secret.key\na/**/ignore_me.txt\n")
    with open(test_dir / "dropped.log", "w", encoding="utf-8") as f:
        f.write("should be dropped\n")
    with open(test_dir / "important.log", "w", encoding="utf-8") as f:
        f.write("keep me please\n")
    with open(test_dir / "secret.key", "w", encoding="utf-8") as f:
        f.write("ROOT_SECRET_DO_NOT_LEAK\n")
    with open(test_dir / "src" / "deep" / "secret.key", "w", encoding="utf-8") as f:
        f.write("DEEP_SECRET_SHOULD_BE_KEPT\n")

    # 验证普通文件名为 build 的脚本不被误杀
    with open(test_dir / "build", "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\necho building script\n")

    # 验证 ** 零层与多层
    (test_dir / "a" / "x").mkdir(parents=True, exist_ok=True)
    with open(test_dir / "a" / "ignore_me.txt", "w", encoding="utf-8") as f:
        f.write("zero_star_secret\n")
    with open(test_dir / "a" / "x" / "ignore_me.txt", "w", encoding="utf-8") as f:
        f.write("multi_star_secret\n")

    # 2. 反引号文件名与冲突文件
    with open(test_dir / "weird`name.py", "w", encoding="utf-8") as f:
        f.write("print('weird')\n")
    with open(test_dir / "doc.md", "w", encoding="utf-8") as f:
        f.write("Inner fence:\n```bash\necho 123\n```\n")

    # 3. GBK 编码中文文件
    with open(test_dir / "gbk_test.py", "wb") as f:
        f.write("# 这是 GBK 编码注释".encode("gb18030"))

    # 4. 构建目录
    (test_dir / "dist").mkdir(exist_ok=True)
    with open(test_dir / "dist" / "bundle.js", "w", encoding="utf-8") as f:
        f.write("console.log('built');\n")

    try:
        packed_text, meta = pack_codebase(str(test_dir))
        assert "important.log" in packed_text, "Negation rule !important.log failed"
        assert "dropped.log" not in packed_text, "Normal ignore rule *.log failed"
        assert "ROOT_SECRET_DO_NOT_LEAK" not in packed_text, "Root anchored rule /secret.key failed"
        assert "DEEP_SECRET_SHOULD_BE_KEPT" in packed_text, "Deep secret.key should be kept by root anchor"
        assert "echo building script" in packed_text, "Regular file named 'build' should not be ignored"
        assert "zero_star_secret" not in packed_text, "Double star ** zero-level match failed"
        assert "multi_star_secret" not in packed_text, "Double star ** multi-level match failed"
        assert "bundle.js" not in packed_text, "Default build dir ignore failed"
        assert "weird\\`name.py" in packed_text, "Filename backtick escaping failed"
        assert "````" in packed_text, "Backtick collision defense failed"
        assert "这是 GBK 编码注释" in packed_text, "GBK encoding decoding failed"
        print(f"[+] 核心安全与对抗断言全部通过！打包 {meta['files_count']} 个文件，估算 Token: {meta['token_estimate']}")

        # 验证 --keep-build-dirs
        packed_kept, _ = pack_codebase(str(test_dir), keep_build_dirs=True)
        assert "bundle.js" in packed_kept, "--keep-build-dirs failed to retain dist/ files"
        print("[+] --keep-build-dirs 构建目录豁免验证通过！")

        # 验证 XML 格式并由标准 ElementTree 解析 (包含 C0 控制字符清洗)
        packed_xml, meta_xml = pack_codebase(str(test_dir), output_format="xml")
        xml_root = ET.fromstring(packed_xml)
        assert xml_root.tag == "project"
        files_elem = xml_root.find("files")
        assert files_elem is not None and len(files_elem) > 0
        print("[+] XML 格式输出与 ElementTree (含控制字符清洗) 无损解析验证通过！")



    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)

    print("[+] RepoPrompt 对抗防御测试 100% 成功通过！")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return

    output_format = "markdown"
    output_file = None
    copy_clipboard = False
    include_minified = False
    keep_build_dirs = False
    max_depth = 8
    target = "."

    args = sys.argv[1:]
    non_flag_args = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--xml":
            output_format = "xml"
        elif arg == "--markdown":
            output_format = "markdown"
        elif arg == "--copy":
            copy_clipboard = True
        elif arg == "--include-minified":
            include_minified = True
        elif arg == "--keep-build-dirs":
            keep_build_dirs = True
        elif arg.startswith("--max-depth="):
            try: max_depth = int(arg.split("=", 1)[1])
            except ValueError: pass
        elif arg.startswith("--output="):
            output_file = arg.split("=", 1)[1]
        elif arg in ("--output", "-o"):
            if i + 1 < len(args):
                output_file = args[i + 1]
                i += 1
        elif arg.startswith("-o="):
            output_file = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            non_flag_args.append(arg)
        i += 1

    if non_flag_args:
        target = non_flag_args[0]

    default_ext = ".xml" if output_format == "xml" else ".md"
    if not output_file:
        output_file = f"repoprompt-output{default_ext}"

    print(f"[*] RepoPrompt v{VERSION} 正在扫描并打包代码库: {target} (Format: {output_format}) ...", file=sys.stderr)
    try:
        packed, meta = pack_codebase(
            target,
            output_format=output_format,
            include_minified=include_minified,
            output_filename=output_file,
            max_depth=max_depth,
            keep_build_dirs=keep_build_dirs
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(packed)

        print(f"✅ 打包成功! 耗时 {meta['elapsed_sec']}s", file=sys.stderr)
        print(f"📊 文件数: {meta['files_count']} | 代码行数: {meta['total_lines']} | 估算 Tokens: ~{meta['token_estimate']:,}", file=sys.stderr)
        print(f"📄 成果已保存至: {output_file}", file=sys.stderr)

        if copy_clipboard:
            if copy_to_clipboard(packed):
                print("📋 完整代码上下文已自动复制到系统剪贴板 (Ctrl+V 可直接发给 AI)！", file=sys.stderr)
            else:
                print("[!] 自动复制剪贴板失败，请直接打开 output 文件复制。", file=sys.stderr)

        print(f"\n☕ 觉得好用？请作者喝杯咖啡支持持续维护: {PAYPAL_URL}\n", file=sys.stderr)

    except Exception as e:
        print(f"[!] 打包出错: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
