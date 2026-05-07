"""
OpenD 进程管理器
负责启动、停止、检查 FutuOpenD 进程状态
"""
import os
import sys
import time
import subprocess
import psutil
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class OpenDManager:
    """FutuOpenD 进程管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 OpenD 管理器

        Args:
            config_path: 配置文件路径，默认为 config/opend_config.yaml
        """
        if config_path is None:
            repo_root = Path(__file__).parent.parent
            config_path = repo_root / "config" / "opend_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.repo_root = Path(__file__).parent.parent

        # 获取当前平台的可执行文件路径
        platform = sys.platform
        if platform.startswith("win"):
            platform_key = "windows"
        elif platform.startswith("linux"):
            platform_key = "linux"
        elif platform.startswith("darwin"):
            platform_key = "darwin"
        else:
            platform_key = "linux"

        self.executable = self.config["opend"]["executable"].get(platform_key)
        self.host = self.config["opend"]["host"]
        self.port = self.config["opend"]["port"]

        # 日志和PID文件路径
        log_file = self.config["opend"]["process"]["log_file"]
        pid_file = self.config["opend"]["process"]["pid_file"]

        self.log_file = self.repo_root / log_file
        self.pid_file = self.repo_root / pid_file

        # 确保目录存在
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"[OpenDManager] 加载配置: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"[OpenDManager] 配置加载失败: {e}")
            raise

    def reload_config(self):
        """重新加载配置文件"""
        self.config = self._load_config()

        # 重新获取当前平台的可执行文件路径
        platform = sys.platform
        if platform.startswith("win"):
            platform_key = "windows"
        elif platform.startswith("linux"):
            platform_key = "linux"
        elif platform.startswith("darwin"):
            platform_key = "darwin"
        else:
            platform_key = "linux"

        self.executable = self.config["opend"]["executable"].get(platform_key)
        self.host = self.config["opend"]["host"]
        self.port = self.config["opend"]["port"]

        logger.info(f"[OpenDManager] 配置已重新加载: executable={self.executable}")

    def is_running(self) -> bool:
        """
        检查 OpenD 进程是否在运行

        Returns:
            True 如果进程在运行，否则 False
        """
        # 方法1: 检查 PID 文件
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    # 检查进程名是否包含 OpenD
                    if "opend" in proc.name().lower() or "futu" in proc.name().lower():
                        return True
            except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 方法2: 遍历所有进程查找 OpenD
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()

                if 'opend' in name or 'futuopend' in name:
                    return True
                if 'opend' in cmdline or 'futuopend' in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def get_pid(self) -> Optional[int]:
        """
        获取 OpenD 进程 PID

        Returns:
            PID 或 None
        """
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    return pid
            except (ValueError, psutil.NoSuchProcess):
                pass

        # 遍历进程查找
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()

                if 'opend' in name or 'futuopend' in name:
                    return proc.info['pid']
                if 'opend' in cmdline or 'futuopend' in cmdline:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return None

    def start(self, wait: bool = True) -> Dict[str, Any]:
        """
        启动 OpenD 进程

        Args:
            wait: 是否等待进程启动完成

        Returns:
            结果字典 {"success": bool, "message": str, "pid": int}
        """
        # 重新加载配置（确保使用最新配置）
        self.reload_config()

        # 检查是否已经在运行
        if self.is_running():
            pid = self.get_pid()
            logger.info(f"[OpenDManager] OpenD 已在运行 (PID: {pid})")
            return {
                "success": True,
                "message": f"OpenD 已在运行 (PID: {pid})",
                "pid": pid
            }

        # 检查可执行文件是否存在
        if not self.executable or not Path(self.executable).exists():
            error_msg = f"OpenD 可执行文件不存在: {self.executable}"
            logger.error(f"[OpenDManager] {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "pid": None
            }

        # 启动进程
        try:
            logger.info(f"[OpenDManager] 启动 OpenD: {self.executable}")

            # 打开日志文件
            log_handle = open(self.log_file, "a", encoding="utf-8")

            # 启动进程
            if sys.platform.startswith("win"):
                # Windows: 使用 DETACHED_PROCESS
                proc = subprocess.Popen(
                    [self.executable],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    cwd=Path(self.executable).parent,
                )
            else:
                # Linux/macOS: 使用 nohup
                proc = subprocess.Popen(
                    [self.executable],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    cwd=Path(self.executable).parent,
                )

            # 写入 PID 文件
            self.pid_file.write_text(str(proc.pid))
            logger.info(f"[OpenDManager] OpenD 已启动 (PID: {proc.pid})")

            # 等待启动完成
            if wait:
                wait_seconds = self.config["opend"]["startup"]["wait_seconds"]
                logger.info(f"[OpenDManager] 等待 {wait_seconds} 秒...")
                time.sleep(wait_seconds)

                # 检查进程是否仍在运行
                if not self.is_running():
                    return {
                        "success": False,
                        "message": "OpenD 启动后立即退出，请检查日志",
                        "pid": None
                    }

            return {
                "success": True,
                "message": f"OpenD 已启动 (PID: {proc.pid})",
                "pid": proc.pid
            }

        except Exception as e:
            error_msg = f"启动 OpenD 失败: {e}"
            logger.error(f"[OpenDManager] {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "pid": None
            }

    def stop(self) -> Dict[str, Any]:
        """
        停止 OpenD 进程

        Returns:
            结果字典 {"success": bool, "message": str}
        """
        pid = self.get_pid()

        if pid is None:
            logger.info("[OpenDManager] OpenD 未在运行")
            return {
                "success": True,
                "message": "OpenD 未在运行"
            }

        try:
            logger.info(f"[OpenDManager] 停止 OpenD (PID: {pid})")
            proc = psutil.Process(pid)

            # 尝试优雅关闭
            proc.terminate()

            # 等待最多 5 秒
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # 强制杀死
                logger.warning(f"[OpenDManager] 优雅关闭超时，强制杀死进程 {pid}")
                proc.kill()
                proc.wait(timeout=2)

            # 删除 PID 文件
            if self.pid_file.exists():
                self.pid_file.unlink()

            logger.info(f"[OpenDManager] OpenD 已停止 (PID: {pid})")
            return {
                "success": True,
                "message": f"OpenD 已停止 (PID: {pid})"
            }

        except psutil.NoSuchProcess:
            # 进程已不存在，清理 PID 文件
            if self.pid_file.exists():
                self.pid_file.unlink()
            return {
                "success": True,
                "message": "OpenD 进程已不存在"
            }

        except Exception as e:
            error_msg = f"停止 OpenD 失败: {e}"
            logger.error(f"[OpenDManager] {error_msg}")
            return {
                "success": False,
                "message": error_msg
            }

    def restart(self) -> Dict[str, Any]:
        """
        重启 OpenD 进程

        Returns:
            结果字典 {"success": bool, "message": str, "pid": int}
        """
        logger.info("[OpenDManager] 重启 OpenD")

        # 停止
        stop_result = self.stop()
        if not stop_result["success"]:
            return stop_result

        # 等待 2 秒
        time.sleep(2)

        # 启动
        return self.start(wait=True)

    def status(self) -> Dict[str, Any]:
        """
        获取 OpenD 状态

        Returns:
            状态字典 {
                "running": bool,
                "pid": int,
                "host": str,
                "port": int,
                "executable": str,
                "log_file": str
            }
        """
        running = self.is_running()
        pid = self.get_pid() if running else None

        return {
            "running": running,
            "pid": pid,
            "host": self.host,
            "port": self.port,
            "executable": self.executable,
            "log_file": str(self.log_file),
        }


# 全局单例
_manager_instance: Optional[OpenDManager] = None


def get_opend_manager(force_reload: bool = False) -> OpenDManager:
    """
    获取 OpenD 管理器单例

    Args:
        force_reload: 是否强制重新创建实例（用于配置更新后）
    """
    global _manager_instance
    if _manager_instance is None or force_reload:
        _manager_instance = OpenDManager()
    return _manager_instance
