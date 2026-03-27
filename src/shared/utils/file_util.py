import os
import subprocess
import re
import shutil
import ast
import base64
import logging

logger = logging.getLogger(__name__)

def format_windows_path(path):
    """安全格式化 Windows 路径"""
    # 替换错误转义字符 + 标准化路径分隔符
    return os.path.normpath(path.replace('\\', '/')).replace('\\', '/')


# 获取文件名称(有后缀)
def get_file_name(file_path):
    return os.path.basename(file_path)


# 获取文件名称(无后缀)
def get_file_name_no_suffix(file_path):
    return os.path.splitext(os.path.basename(file_path))[0]


# 获取文件后缀
def get_file_suffix(file_path):
    return os.path.splitext(os.path.basename(file_path))[1]


def rename_file(old_path, new_path):
    # 修改文件名称
    os.rename(old_path, new_path)


# 文件夹添加文件
def join_suffix(folder, file_url):
    return os.path.join(folder, file_url)


def del_file(file_path):
    if not os.path.exists(file_path):
        logger.warning(f"路径 {file_path} 不存在")
        return

    try:
        if os.path.isfile(file_path):
            # 删除单个文件
            os.remove(file_path)
            logger.info(f"文件 {file_path} 已删除")
        else:
            # 清空文件夹下所有内容
            for filename in os.listdir(file_path):
                file_item = os.path.join(file_path, filename)
                if os.path.isfile(file_item) or os.path.islink(file_item):
                    os.unlink(file_item)  # 删除文件或符号链接
                else:
                    shutil.rmtree(file_item)  # 递归删除子目录
            logger.info(f"文件夹 {file_path} 内容已清空")

    except Exception as e:
        logger.error(f"删除操作失败: {e}")


# 保存文本到文件
def save_text_file(content):
    file_name = "subtitle.srt"
    # Windows系统中"C盘/下载"文件夹的通用路径
    download_path = os.path.join('C:\\Users', os.getlogin(), 'Downloads')
    # 指定保存的文件路径
    file_path = os.path.join(download_path, file_name)
    # 将字幕内容写入到文件
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)
    return f"字幕文件已保存至: {file_path}"


# 读取文件内容
def read_text_file(file):
    if file is None:
        return ""
    with open(file.name, "r", encoding="utf-8") as f:
        content = f.read()
    return content


# 获取文件夹下所有文件名称
def get_folder_file_name(operate_folder):
    # 确保文件夹存在
    if not os.path.exists(operate_folder):
        os.makedirs(operate_folder)
    filenames = []
    # 遍历文件夹中的每个文件
    for file_path in operate_folder.iterdir():
        # 只处理文件，跳过子目录
        if file_path.is_file():
            # 去除文件扩展名并将结果添加到列表
            # filenames.append(file_path.stem)
            # 保留文件扩展名并将结果添加到列表
            filenames.append(file_path.name)
    return filenames


# 获取下载文件夹地址
def get_download_folder():
    if os.name == 'nt':  # Windows系统
        download_folder = os.path.join(os.getenv('USERPROFILE'), 'Downloads')
    elif os.name == 'posix':  # macOS和Linux系统
        download_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
    else:
        raise OSError("Unsupported operating system")
    return download_folder + "/"


# 打开文件夹
def open_folder(open_path):
    # 获取下载文件夹地址
    if not open_path:
        open_path = get_download_folder()
    subprocess.run(['explorer', open_path])


# 判断文件和文件夹是否存在
def check_folder(target_file):
    # 分离文件路径和文件名
    folder_path, _ = os.path.split(target_file)
    # 检查文件夹是否存在,不存在返回False
    if not os.path.exists(folder_path):
        return False
    # 检查目标文件是否存在,不存在返回False
    if not os.path.exists(target_file):
        return False
    return True


def clean_upload_dir(clean_dir):
    """清空上传目录"""
    try:
        if os.path.exists(clean_dir):
            # 删除整个目录（包括所有子文件和子目录）
            shutil.rmtree(clean_dir)
        # 重新创建目录（保持目录存在）
        os.makedirs(clean_dir, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"目录清理失败: {str(e)}")


# 配置缓存
_config_cache: dict = None


def load_config(use_cache: bool = True) -> dict:
    """读取配置到字典（带缓存）

    Args:
        use_cache: 是否使用缓存，默认为True

    Returns:
        配置字典
    """
    global _config_cache

    # 检查缓存
    if use_cache and _config_cache is not None:
        return _config_cache

    # 从 src.config 模块获取配置
    try:
        from src import config as src_config
        import inspect

        config = {}
        # 获取模块中的所有变量（排除私有变量和函数）
        for name, value in inspect.getmembers(src_config):
            if not name.startswith('_') and not inspect.isfunction(value) and not inspect.isclass(value) and not inspect.ismodule(value):
                config[name] = value

        _config_cache = config
        return config

    except ImportError as e:
        logger.warning(f"无法导入配置模块: {e}")
        return {}
    except Exception as e:
        logger.error(f"读取配置失败: {e}")
        return {}


def clear_config_cache():
    """清除配置缓存"""
    global _config_cache
    _config_cache = None


def update_value(key: str, value):
    """更新配置值（仅更新缓存，不写入文件）"""
    global _config_cache
    if _config_cache is not None:
        _config_cache[key] = value
    logger.warning(f"配置项 {key} 已更新为 {value}（仅缓存，未持久化）")


def audio_to_base64(file_path: str) -> str:
    """
    将音频文件转换为 Base64 编码的字符串

    :param file_path: 音频文件路径
    :return: Base64 编码的字符串
    """
    with open(file_path, "rb") as audio_file:
        audio_data = audio_file.read()
        return base64.b64encode(audio_data).decode("utf-8")


async def save_uploaded_file(upload_file: "UploadFile", upload_dir: str, max_size_mb: int = 500) -> dict:
    """
    通用的文件上传处理函数

    :param upload_file: FastAPI UploadFile 对象
    :param upload_dir: 上传目录
    :param max_size_mb: 最大文件大小（MB），默认500MB
    :return: 包含文件路径信息的字典
    :raises ValueError: 文件大小超过限制
    """
    import uuid

    # 获取文件扩展名
    file_ext = upload_file.filename.split('.')[-1] if upload_file.filename else 'tmp'
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(upload_dir, filename)

    # 分块写入文件（每次读取1MB）
    chunk_size = 1024 * 1024
    total_size = 0
    max_bytes = max_size_mb * 1024 * 1024

    with open(file_path, "wb") as buffer:
        while content := await upload_file.read(chunk_size):
            total_size += len(content)
            if total_size > max_bytes:
                # 超过大小限制，删除已写入的文件
                buffer.close()
                os.remove(file_path)
                raise ValueError(f"文件大小超过限制 ({max_size_mb}MB)")
            buffer.write(content)

    return {
        "filename": filename,
        "webPath": os.path.join(upload_dir, filename),
        "localPath": os.path.abspath(file_path),
        "size": total_size
    }
