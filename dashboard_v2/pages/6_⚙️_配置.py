"""
MarketRadar Dashboard V2 - 配置页面
系统配置管理
"""
import sys
from pathlib import Path
import yaml

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="配置 - MarketRadar V2",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ 系统配置")

# ═══════════════════════════════════════════════════════════════
# OpenD 配置
# ═══════════════════════════════════════════════════════════════

st.subheader("🔌 FutuOpenD 配置")

config_file = ROOT / "config" / "opend_config.yaml"

# 加载当前配置
try:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
except Exception as e:
    st.error(f"配置文件加载失败: {e}")
    st.stop()

# 显示当前平台
import platform
current_platform = platform.system()
platform_map = {
    "Windows": "windows",
    "Linux": "linux",
    "Darwin": "darwin"
}
platform_key = platform_map.get(current_platform, "linux")

st.info(f"📌 当前操作系统: **{current_platform}** (配置键: `{platform_key}`)")

st.divider()

# ── 可执行文件路径配置 ──
st.markdown("### 📂 可执行文件路径")

col_path1, col_path2 = st.columns([3, 1])

with col_path1:
    # 获取当前平台的路径
    current_path = config["opend"]["executable"].get(platform_key, "")

    new_path = st.text_input(
        f"{current_platform} 平台路径",
        value=current_path,
        help="FutuOpenD 可执行文件的完整路径",
        key="opend_path"
    )

with col_path2:
    st.markdown("##### 操作")
    if st.button("📁 浏览文件", use_container_width=True):
        st.info("请手动输入路径（文件浏览器功能待实现）")

# 路径验证
if new_path:
    path_obj = Path(new_path)
    if path_obj.exists():
        st.success(f"✅ 路径有效: {new_path}")
    else:
        st.warning(f"⚠️ 路径不存在: {new_path}")

# 其他平台路径（只读显示）
with st.expander("查看其他平台配置"):
    for platform_name, key in platform_map.items():
        if key != platform_key:
            path = config["opend"]["executable"].get(key, "未配置")
            st.text(f"{platform_name}: {path}")

st.divider()

# ── 网络配置 ──
st.markdown("### 🌐 网络配置")

col_net1, col_net2 = st.columns(2)

with col_net1:
    new_host = st.text_input(
        "主机地址",
        value=config["opend"]["host"],
        help="OpenD 监听地址，通常为 127.0.0.1",
        key="opend_host"
    )

with col_net2:
    new_port = st.number_input(
        "端口",
        value=config["opend"]["port"],
        min_value=1024,
        max_value=65535,
        help="OpenD 监听端口，默认 11111",
        key="opend_port"
    )

st.divider()

# ── 启动参数配置 ──
st.markdown("### 🚀 启动参数")

col_startup1, col_startup2, col_startup3 = st.columns(3)

with col_startup1:
    new_wait_seconds = st.number_input(
        "启动等待时间（秒）",
        value=config["opend"]["startup"]["wait_seconds"],
        min_value=1,
        max_value=30,
        help="启动后等待进程稳定的时间",
        key="wait_seconds"
    )

with col_startup2:
    new_check_interval = st.number_input(
        "健康检查间隔（秒）",
        value=config["opend"]["startup"]["check_interval"],
        min_value=1,
        max_value=10,
        help="进程健康检查的间隔时间",
        key="check_interval"
    )

with col_startup3:
    new_max_retries = st.number_input(
        "最大重试次数",
        value=config["opend"]["startup"]["max_retries"],
        min_value=1,
        max_value=10,
        help="启动失败时的最大重试次数",
        key="max_retries"
    )

st.divider()

# ── 保存配置 ──
st.markdown("### 💾 保存配置")

col_save1, col_save2, col_save3 = st.columns([2, 1, 1])

with col_save1:
    st.info("修改配置后需要重启 OpenD 才能生效")

with col_save2:
    if st.button("💾 保存配置", type="primary", use_container_width=True):
        try:
            # 更新配置
            config["opend"]["executable"][platform_key] = new_path
            config["opend"]["host"] = new_host
            config["opend"]["port"] = new_port
            config["opend"]["startup"]["wait_seconds"] = new_wait_seconds
            config["opend"]["startup"]["check_interval"] = new_check_interval
            config["opend"]["startup"]["max_retries"] = new_max_retries

            # 写入文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            # 强制重新加载 OpenD 管理器
            try:
                from integrations.opend_manager import get_opend_manager
                opend_mgr = get_opend_manager(force_reload=True)
                st.success("✅ 配置已保存，OpenD 管理器已重新加载")
            except Exception as e:
                st.success("✅ 配置已保存")
                st.warning(f"⚠️ OpenD 管理器重新加载失败: {e}")

            st.rerun()

        except Exception as e:
            st.error(f"保存失败: {e}")

with col_save3:
    if st.button("🔄 重置默认", use_container_width=True):
        st.warning("重置功能待实现")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 数据源配置
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 数据源配置")

data_sources_file = ROOT / "config" / "data_sources.yaml"

try:
    with open(data_sources_file, 'r', encoding='utf-8') as f:
        data_sources = yaml.safe_load(f)
except Exception as e:
    st.error(f"数据源配置加载失败: {e}")
    st.stop()

# ── 主数据源 ──
st.markdown("### 🎯 主数据源")

col_ds1, col_ds2, col_ds3 = st.columns(3)

with col_ds1:
    st.markdown("##### A股")
    a_share_primary = st.selectbox(
        "主数据源",
        ["futu", "baostock", "akshare"],
        index=["futu", "baostock", "akshare"].index(data_sources["primary"]["a_share"]),
        key="a_share_primary"
    )

with col_ds2:
    st.markdown("##### 港股")
    hk_primary = st.selectbox(
        "主数据源",
        ["futu", "yfinance"],
        index=["futu", "yfinance"].index(data_sources["primary"]["hk_share"]),
        key="hk_primary"
    )

with col_ds3:
    st.markdown("##### 美股")
    us_primary = st.selectbox(
        "主数据源",
        ["futu", "yfinance"],
        index=["futu", "yfinance"].index(data_sources["primary"]["us_share"]),
        key="us_primary"
    )

st.divider()

# ── 备用数据源 ──
st.markdown("### 🔄 备用数据源")

col_fb1, col_fb2, col_fb3 = st.columns(3)

with col_fb1:
    st.markdown("##### A股")
    a_share_fallback = st.selectbox(
        "备用数据源",
        ["akshare", "baostock"],
        index=["akshare", "baostock"].index(data_sources["fallback"]["a_share"]),
        key="a_share_fallback"
    )

with col_fb2:
    st.markdown("##### 港股")
    hk_fallback = st.selectbox(
        "备用数据源",
        ["yfinance", "futu"],
        index=["yfinance", "futu"].index(data_sources["fallback"]["hk_share"]),
        key="hk_fallback"
    )

with col_fb3:
    st.markdown("##### 美股")
    us_fallback = st.selectbox(
        "备用数据源",
        ["yfinance", "futu"],
        index=["yfinance", "futu"].index(data_sources["fallback"]["us_share"]),
        key="us_fallback"
    )

st.divider()

# ── 保存数据源配置 ──
col_ds_save1, col_ds_save2 = st.columns([3, 1])

with col_ds_save1:
    st.info("修改数据源配置后需要重启调度器才能生效")

with col_ds_save2:
    if st.button("💾 保存数据源配置", type="primary", use_container_width=True):
        try:
            # 更新配置
            data_sources["primary"]["a_share"] = a_share_primary
            data_sources["primary"]["hk_share"] = hk_primary
            data_sources["primary"]["us_share"] = us_primary
            data_sources["fallback"]["a_share"] = a_share_fallback
            data_sources["fallback"]["hk_share"] = hk_fallback
            data_sources["fallback"]["us_share"] = us_fallback

            # 写入文件
            with open(data_sources_file, 'w', encoding='utf-8') as f:
                yaml.dump(data_sources, f, allow_unicode=True, default_flow_style=False)

            st.success("✅ 数据源配置已保存")
            st.rerun()

        except Exception as e:
            st.error(f"保存失败: {e}")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 配置说明
# ═══════════════════════════════════════════════════════════════

st.subheader("📖 配置说明")

with st.expander("数据源特性对比"):
    st.markdown("""
    | 数据源 | 市场 | 延迟 | 依赖 | 限制 |
    |--------|------|------|------|------|
    | **futu** | A股/港股/美股 | 实时（A/港）<br>15分钟（美） | OpenD进程 | 需要富途账号 |
    | **baostock** | A股 | T+1日线 | 无 | 仅历史数据 |
    | **akshare** | A股 | 3-5分钟 | 无 | 中等限流 |
    | **yfinance** | 港股/美股 | 15分钟 | 无 | 严格限流 |
    """)

with st.expander("OpenD 路径示例"):
    st.markdown("""
    **Windows**:
    ```
    C:/Program Files/Futu/FutuOpenD/OpenD.exe
    D:/Software/FutuOpenD/OpenD.exe
    ```

    **Linux**:
    ```
    /root/futu/FutuOpenD_10.4.6408/FutuOpenD
    /opt/futu/FutuOpenD
    ```

    **macOS**:
    ```
    /Applications/FutuOpenD.app/Contents/MacOS/FutuOpenD
    ```
    """)

with st.expander("配置文件位置"):
    st.markdown(f"""
    - **OpenD 配置**: `{config_file}`
    - **数据源配置**: `{data_sources_file}`
    - **OpenD 日志**: `{ROOT / 'logs' / 'opend.log'}`
    - **OpenD PID**: `{ROOT / 'logs' / 'opend.pid'}`
    """)
