# LLM Runtime Repair Anchor — 2026-04-14

## 本轮目标
先修 LLM runtime chain，再恢复产品功能推进。

## 已确认现状
1. `python -m pytest` 直接失败：当前 Python 环境未安装 `pytest`。
2. `config/llm_config.yaml` 原默认 provider 是 `deepseek`，不符合本轮“优先非-Claude / `gongfeng/gpt-5-4`”要求。
3. `providers.gongfeng.model` 原值是 `claude-sonnet-4-6`，且 `core/llm_client.py` 还硬编码 `X-Model-Name: Claude Sonnet 4.6`，说明 runtime chain 实际上会落到 Claude 语义路径。
4. `test_pipeline.py` 未强制 provider，实际解析结果完全取决于 `llm_config.yaml` + 环境变量。
5. 仓库内存在多份临时测试脚本直接硬编码 API key，后续需要专门清理。

## 本轮已做修复
1. 将 `config/llm_config.yaml` 默认 provider 改为 `openai`。
2. 将 `providers.openai.model` 改为 `gongfeng/gpt-5-4`。
3. 将 `providers.gongfeng.model` 改为 `gongfeng/gpt-5-4`，并新增 `model_header` 供 header 透传。
4. 修改 `core/llm_client.py`：`X-Model-Name` 不再硬编码 Claude，而是从配置解析。
5. 新增 `scripts/inspect_llm_runtime.py`，用于打印模块级 provider/model 实际解析结果。
6. 更新 `README.md`，把默认说明从 DeepSeek 切到非-Claude 修复路径。

## 当前阻塞
1. ~~**测试入口阻塞**：宿主 Python 环境缺少 `pytest`，无法完成优先级(1)的标准验证。~~
   - 已通过 `python -m pip install pytest` 修复，`python -m pytest` 现在可以启动。
2. **有效 provider 仍未最终坐实**：
   - `scripts/inspect_llm_runtime.py` 已确认模块解析统一落到 `openai -> gongfeng/gpt-5-4`。
   - 但当前环境中 `OPENAI_BASE_URL` / `OPENAI_API_KEY` 均未配置，因此所有 LLM 测试会在运行前被明确拦截。
   - 若改用 `gongfeng` provider，虽然 model/header 已改，但尚未确认上游 gateway 是否真实接受 `gongfeng/gpt-5-4`，需要连通验证。
3. **LLM 错误暴露层刚完成修复**：
   - 之前 `APIConnectionError` 会被错误访问 `status_code/message` 再次打崩，掩盖真实问题。
   - 现在已改为：未解析的 `base_url` 直接抛出明确 RuntimeError，便于定位环境缺失。
4. **除 LLM 外仍有独立测试失败**：
   - `tests/_backtest_test.py`：样本涨幅断言与当前数据不一致。
   - `tests/_m7_test.py`：默认任务集合新增 `sentiment_collect`，测试预期未更新。
   - `tests/_m6_test.py`：仍有 Pydantic 校验错误，需单独处理。
5. **文档与代码尚未完全一致**：`docs/LLM_Config.md`、若干联调脚本仍大量描述 DeepSeek/Claude 旧路线。

## 下一轮建议顺序
1. 注入一个真实可用的非-Claude endpoint（优先 `OPENAI_BASE_URL` + `OPENAI_API_KEY`）
2. 运行：`python .\scripts\inspect_llm_runtime.py`
3. 运行：`python -m pytest test_core_llm.py test_pipeline.py tests\_m1_test.py tests\_m3_test.py tests\_full_pipeline_test.py`
4. 执行：`python test_pipeline.py`
5. 若 `openai` 路径失败，再用相同模型名验证 `gongfeng` provider 是否可直通
6. 之后再分别修复 `_backtest_test` / `_m6_test` / `_m7_test`
7. 完成后统一清理仓库中的硬编码 key 与旧脚本

## 本轮结论
本轮已经把“默认会掉到 Claude”这个结构性问题从配置层和 header 层拆掉，并补齐了 pytest 入口与更清晰的 LLM 失败提示。当前新的主 blocker 很明确：本机尚未配置可用的 `OPENAI_BASE_URL` / `OPENAI_API_KEY`，因此 `gongfeng/gpt-5-4` 非-Claude 主链路还无法真正打通。在拿到有效 endpoint 前，应停在此 anchor，而不是继续堆产品功能。
