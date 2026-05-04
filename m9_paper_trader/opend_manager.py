"""
OpenD进程管理器
负责启动、停止、健康检查FutuOpenD服务
"""
import os
import sys
import time
import subprocess
import platform
from pathlib import Path
from typing import Optional
import yaml
import logging

logger = logging.getLogger(__name__)


class OpenDManager:
    """FutuOpenD进程管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化OpenD管理器
        
        Args:
            config_path: 配置文件路径，默认使用config/opend_config.yaml
        """
        if config_path is None:
            # 默认配置路径
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "opend_config.yaml"
        
        self.config = self._load_config(config_path)
        self.host = self.config["opend"]["host"]
        self.port = self.config["opend"]["port"]
        self.executable = self._get_executable_path()
        self.startup_config = self.config["opend"]["startup"]
        self.process_config = self.config["opend"]["process"]
        
    def _load_config(self, config_path: Path) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载OpenD配置失败: {e}")
            raise
    
    def _get_executable_path(self) -> str:
        """根据操作系统获取OpenD可执行文件路径"""
        system = platform.system().lower()
        
        # 映射platform.system()返回值到配置文件的key
        system_map = {
            "linux": "linux",
            "windows": "windows",
            "darwin": "darwin"  # macOS
        }
        
        config_key = system_map.get(system)
        if not config_key:
            raise RuntimeError(f"不支持的操作系统: {system}")
        
        executable = self.config["opend"]["executable"].get(config_key)
        if not executable:
            raise RuntimeError(f"配置文件中未找到{system}的OpenD路径")
        
        # 检查文件是否存在
        if not os.path.exists(executable):
            raise FileNotFoundError(f"OpenD可执行文件不存在: {executable}")
        
        return executable
    
    def is_running(self) -> bool:
        """检查OpenD是否正在运行"""
        try:
            if platform.system().lower() == "windows":
                # Windows: 使用tasklist
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq OpenD.exe"],
                    capture_output=True,
                    text=True
                )
                return "OpenD.exe" in result.stdout
            else:
                # Linux/macOS: 使用pgrep
                check_cmd = self.process_config["check_command"]
                result = subprocess.run(
                    check_cmd,
                    shell=True,
                    capture_output=True
                )
                return result.returncode == 0
        except Exception as e:
            logger.warning(f"检查OpenD进程失败: {e}")
            return False
    
    def start(self) -> bool:
        """
        启动OpenD服务
        
        Returns:
            bool: 启动成功返回True，否则返回False
        """
        if self.is_running():
            logger.info("OpenD已在运行中")
            return True
        
        try:
            logger.info(f"正在启动OpenD: {self.executable}")
            
            # 准备日志目录
            log_file = Path(self.process_config["log_file"])
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 启动OpenD进程
            with open(log_file, 'a') as log:
                if platform.system().lower() == "windows":
                    # Windows: 使用CREATE_NEW_CONSOLE避免阻塞
                    subprocess.Popen(
                        [self.executable],
                        stdout=log,
                        stderr=log,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    # Linux/macOS: 使用nohup后台运行
                    subprocess.Popen(
                        [self.executable],
                        stdout=log,
                        stderr=log,
                        start_new_session=True
                    )
            
            # 等待启动
            wait_seconds = self.startup_config["wait_seconds"]
            logger.info(f"等待OpenD启动（{wait_seconds}秒）...")
            time.sleep(wait_seconds)
            
            # 健康检查
            max_retries = self.startup_config["max_retries"]
            check_interval = self.startup_config["check_interval"]
            
            for i in range(max_retries):
                if self.is_running():
                    logger.info("✅ OpenD启动成功")
                    return True
                
                logger.warning(f"OpenD未就绪，重试 {i+1}/{max_retries}...")
                time.sleep(check_interval)
            
            logger.error("❌ OpenD启动失败：超时")
            return False
            
        except Exception as e:
            logger.error(f"❌ OpenD启动异常: {e}")
            return False
    
    def stop(self) -> bool:
        """
        停止OpenD服务
        
        Returns:
            bool: 停止成功返回True，否则返回False
        """
        if not self.is_running():
            logger.info("OpenD未运行")
            return True
        
        try:
            logger.info("正在停止OpenD...")
            
            if platform.system().lower() == "windows":
                # Windows: 使用taskkill
                subprocess.run(
                    ["taskkill", "/F", "/IM", "OpenD.exe"],
                    capture_output=True
                )
            else:
                # Linux/macOS: 使用pkill
                subprocess.run(
                    ["pkill", "-f", "FutuOpenD"],
                    capture_output=True
                )
            
            # 等待进程退出
            time.sleep(2)
            
            if not self.is_running():
                logger.info("✅ OpenD已停止")
                return True
            else:
                logger.warning("⚠️ OpenD可能未完全停止")
                return False
                
        except Exception as e:
            logger.error(f"❌ 停止OpenD异常: {e}")
            return False
    
    def ensure_running(self) -> bool:
        """
        确保OpenD正在运行（如果未运行则启动）
        
        Returns:
            bool: OpenD运行中返回True，否则返回False
        """
        if not self.startup_config.get("auto_start", True):
            logger.info("auto_start=False，跳过OpenD启动")
            return self.is_running()
        
        if self.is_running():
            return True
        
        logger.warning("OpenD未运行，尝试启动...")
        return self.start()
    
    def get_connection_info(self) -> dict:
        """获取连接信息"""
        return {
            "host": self.host,
            "port": self.port,
            "running": self.is_running(),
            "executable": self.executable
        }


def main():
    """命令行测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenD进程管理器")
    parser.add_argument("action", choices=["start", "stop", "status", "restart"],
                       help="操作：start启动 | stop停止 | status状态 | restart重启")
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    manager = OpenDManager()
    
    if args.action == "start":
        success = manager.start()
        sys.exit(0 if success else 1)
    
    elif args.action == "stop":
        success = manager.stop()
        sys.exit(0 if success else 1)
    
    elif args.action == "status":
        info = manager.get_connection_info()
        print(f"OpenD状态:")
        print(f"  运行中: {'✅ 是' if info['running'] else '❌ 否'}")
        print(f"  地址: {info['host']}:{info['port']}")
        print(f"  路径: {info['executable']}")
        sys.exit(0 if info['running'] else 1)
    
    elif args.action == "restart":
        manager.stop()
        time.sleep(2)
        success = manager.start()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
