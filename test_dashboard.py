"""
简化的Dashboard测试 - 验证标签页是否正常工作
"""
import streamlit as st

st.set_page_config(page_title="Test Dashboard", layout="wide")

st.title("MarketRadar Dashboard 测试")

# 创建标签页
tab1, tab2, tab3 = st.tabs(["测试1", "测试2", "工作流测试"])

with tab1:
    st.header("测试标签页 1")
    st.write("如果你能看到这段文字，说明标签页1正常工作")
    st.button("测试按钮1")

with tab2:
    st.header("测试标签页 2")
    st.write("如果你能看到这段文字，说明标签页2正常工作")
    st.metric("测试指标", "123")

with tab3:
    st.header("🎛️ 工作流控制中心测试")
    st.write("如果你能看到这段文字，说明工作流标签页正常工作")

    st.subheader("⚙️ 调度器控制测试")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("状态", "🟢 测试")
    with col2:
        st.metric("任务数", "14")
    with col3:
        st.metric("成功率", "100%")

    if st.button("🚀 测试按钮", use_container_width=True):
        st.success("按钮点击成功！")

    st.divider()

    st.subheader("🎯 手动触发测试")
    st.markdown("**测试说明：** 这是一个简化的测试页面")

    test_col1, test_col2 = st.columns(2)
    with test_col1:
        st.markdown("##### 左侧测试")
        st.selectbox("选择选项", ["选项1", "选项2", "选项3"])

    with test_col2:
        st.markdown("##### 右侧测试")
        st.radio("单选测试", ["A", "B", "C"])

st.sidebar.success("✅ 测试Dashboard已加载")
st.sidebar.info("如果所有标签页都能正常显示内容，说明Streamlit工作正常")
