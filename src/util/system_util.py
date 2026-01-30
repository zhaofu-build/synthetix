"""
系统工具类，用于判断当前运行环境
"""

import platform


def is_linux_system():
    """
    判断当前是否为Linux系统（包括WSL）
    
    Returns:
        bool: 如果是Linux系统返回True，否则返回False
    """
    system = platform.system().lower()
    # 检测是否为Linux或WSL环境
    is_linux = system == 'linux'
    is_wsl = 'microsoft' in platform.uname().release.lower()
    return is_linux or is_wsl


def is_windows_system():
    """
    判断当前是否为Windows系统
    
    Returns:
        bool: 如果是Windows系统返回True，否则返回False
    """
    return platform.system().lower() == 'windows'


def get_current_system():
    """
    获取当前系统类型
    
    Returns:
        str: 返回 'linux', 'windows' 或 'other'
    """
    if is_linux_system():
        return 'linux'
    elif is_windows_system():
        return 'windows'
    else:
        return 'other'