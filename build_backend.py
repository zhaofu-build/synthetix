"""
将 Python 后端打包为 Tauri sidecar 可执行文件。

用法:
    python build_backend.py

输出:
    src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT_NAME = "backend-x86_64-pc-windows-msvc"
SIDECAR_DIR = ROOT / "src-tauri" / "binaries"


def main():
    if not shutil.which("pyinstaller"):
        print("错误: PyInstaller 未安装，请运行: pip install pyinstaller")
        sys.exit(1)

    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", OUTPUT_NAME,
        "--distpath", str(SIDECAR_DIR),
        "--workpath", str(ROOT / "build_pyinstaller"),
        "--specpath", str(ROOT / "build_pyinstaller"),
        "--clean",
        str(ROOT / "main.py"),
    ]

    print(f"运行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    exe = SIDECAR_DIR / f"{OUTPUT_NAME}.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n成功: {exe} ({size_mb:.1f} MB)")
    else:
        print(f"\n失败: 未找到 {exe}")
        sys.exit(1)


if __name__ == "__main__":
    main()
