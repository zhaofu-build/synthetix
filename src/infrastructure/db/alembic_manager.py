"""
Alembic 数据库迁移管理模块
"""
import os
from alembic.config import Config
from alembic import command
import logging
from src import config as alconfig
logger = logging.getLogger(__name__)


def init_database_with_alembic():
    """
    使用 Alembic 初始化数据库
    如果数据库不存在，会自动创建并应用所有迁移
    如果没有迁移脚本，会自动生成初始迁移脚本
    """

    db_path = alconfig.database_path
    versions_dir = alconfig.alembic_path
    
    # 确保 db 目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logger.info(f"创建目录: {db_dir}")
    
    # 确保 versions 目录存在
    if not os.path.exists(versions_dir):
        os.makedirs(versions_dir)
        logger.info(f"创建目录: {versions_dir}")
    
    # 检查数据库文件是否存在
    db_exists = os.path.exists(db_path)
    
    # 配置 Alembic
    alembic_cfg = Config("alembic.ini")
    
    try:
        # 检查是否存在迁移脚本
        has_migrations = any(
            f.endswith('.py') and f != '__init__.py'
            for f in os.listdir(versions_dir)
            if os.path.isfile(os.path.join(versions_dir, f))
        )
        
        if not has_migrations:
            logger.info("未找到迁移脚本，正在自动生成初始迁移...")
            # 自动生成初始迁移脚本
            command.revision(alembic_cfg, autogenerate=True, message="初始化数据库表结构")
            logger.info("迁移脚本生成成功")
        
        if not db_exists:
            logger.info("数据库不存在，正在使用 Alembic 初始化...")
            # 应用所有迁移到最新版本
            command.upgrade(alembic_cfg, "head")
            logger.info("数据库初始化成功！")
        else:
            logger.info("数据库已存在，检查是否需要迁移...")
            # 应用所有未应用的迁移
            command.upgrade(alembic_cfg, "head")
            logger.info("数据库迁移检查完成")
            
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        # 如果是新创建的数据库出错，删除不完整的数据库文件
        if not db_exists and os.path.exists(db_path):
            os.remove(db_path)
            logger.info("已删除不完整的数据库文件")
        raise


def create_migration(message: str):
    """
    创建新的迁移脚本
    
    Args:
        message: 迁移说明
    """
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)
    logger.info(f"迁移脚本创建成功: {message}")


def upgrade_database(revision: str = "head"):
    """
    升级数据库到指定版本
    
    Args:
        revision: 目标版本，默认为 "head"（最新版本）
    """
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, revision)
    logger.info(f"数据库已升级到: {revision}")


def downgrade_database(revision: str):
    """
    降级数据库到指定版本
    
    Args:
        revision: 目标版本
    """
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, revision)
    logger.info(f"数据库已降级到: {revision}")


def show_current_revision():
    """
    显示当前数据库版本
    """
    alembic_cfg = Config("alembic.ini")
    command.current(alembic_cfg)


def show_history():
    """
    显示迁移历史
    """
    alembic_cfg = Config("alembic.ini")
    command.history(alembic_cfg)
