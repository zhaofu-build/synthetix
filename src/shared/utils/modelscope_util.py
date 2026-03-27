"""
ModelScope工具类，用于处理ModelScope模型下载和管理功能
"""
from modelscope import snapshot_download
import os
import logging
from src.config import MODEL_CACHE_DIR


class ModelScopeUtil:
    """
    ModelScope工具类，封装ModelScope相关功能
    """
    
    def __init__(self, cache_dir=None):
        """
        初始化ModelScope工具类
        
        Args:
            cache_dir (str): 模型缓存目录，默认为None
        """
        self.cache_dir = cache_dir or MODEL_CACHE_DIR
        self.logger = logging.getLogger(__name__)
    
    def download_model(self, model_id, revision=None, cache_dir=None, **kwargs):
        """
        下载模型到本地缓存
        
        Args:
            model_id (str): 模型标识符，如 'Qwen/Qwen3-VL-2B-Instruct'
            revision (str, optional): 版本号，如 'master', 'v1.0.0' 等
            cache_dir (str, optional): 缓存目录，如果提供则覆盖实例默认值
            **kwargs: 其他传递给snapshot_download的参数
            
        Returns:
            str: 模型本地存储路径
        """
        download_cache_dir = cache_dir or self.cache_dir
        
        # 确保缓存目录存在
        os.makedirs(download_cache_dir, exist_ok=True)
        
        # 设置默认参数
        default_kwargs = {
            'cache_dir': download_cache_dir,
        }
        default_kwargs.update(kwargs)
        
        if revision:
            default_kwargs['revision'] = revision
            
        try:
            model_path = snapshot_download(model_id, **default_kwargs)
            self.logger.info(f"模型 {model_id} 已成功下载到 {model_path}")
            return model_path
        except Exception as e:
            self.logger.error(f"下载模型 {model_id} 时发生错误: {str(e)}")
            raise
    
    def get_cached_model_path(self, model_id, revision=None):
        """
        获取已缓存的模型路径（不重新下载）
        
        Args:
            model_id (str): 模型标识符
            revision (str, optional): 版本号
            
        Returns:
            str: 模型本地存储路径，如果不存在则返回None
        """
        # ModelScope会自动处理缓存，直接尝试下载即可
        try:
            return self.download_model(model_id, revision=revision, force_download=False)
        except Exception:
            # 如果下载失败，表示模型未缓存
            return None
    
    def download_with_progress(self, model_id, revision=None, cache_dir=None, progress_callback=None):
        """
        带进度回调的模型下载
        
        Args:
            model_id (str): 模型标识符
            revision (str, optional): 版本号
            cache_dir (str, optional): 缓存目录
            progress_callback (callable, optional): 进度回调函数，接收下载进度百分比作为参数
            
        Returns:
            str: 模型本地存储路径
        """
        # 注意：当前ModelScope的snapshot_download不直接支持进度回调
        # 这里仅保留接口，实际实现依赖ModelScope本身的功能
        return self.download_model(model_id, revision=revision, cache_dir=cache_dir)
    
    def list_local_models(self):
        """
        列出本地缓存的所有模型目录
        
        Returns:
            list: 本地模型目录列表
        """
        if not os.path.exists(self.cache_dir):
            return []
        
        model_dirs = []
        for item in os.listdir(self.cache_dir):
            item_path = os.path.join(self.cache_dir, item)
            if os.path.isdir(item_path):
                model_dirs.append(item_path)
        
        return model_dirs


# 便捷函数
def download_model(model_id, cache_dir=MODEL_CACHE_DIR, revision=None, **kwargs):
    """
    便捷函数：下载模型
    
    Args:
        model_id (str): 模型标识符
        cache_dir (str): 缓存目录
        revision (str, optional): 版本号
        **kwargs: 其他参数
        
    Returns:
        str: 模型本地路径
    """
    util = ModelScopeUtil(cache_dir=cache_dir)
    return util.download_model(model_id, revision=revision, **kwargs)


def get_cached_model_path(model_id, cache_dir=MODEL_CACHE_DIR, revision=None):
    """
    便捷函数：获取已缓存模型路径
    
    Args:
        model_id (str): 模型标识符
        cache_dir (str): 缓存目录
        revision (str, optional): 版本号
        
    Returns:
        str: 模型本地路径或None
    """
    util = ModelScopeUtil(cache_dir=cache_dir)
    return util.get_cached_model_path(model_id, revision=revision)