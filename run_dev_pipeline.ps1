param(
    [string]$Provider = "deepseek"
)

switch ($Provider.ToLower()) {
    "deepseek" {
        if (-not $env:DEEPSEEK_API_KEY) {
            throw "DEEPSEEK_API_KEY 未设置。请先在当前 PowerShell 会话中注入 key。"
        }
        python test_pipeline.py
    }
    "gongfeng" {
        python test_pipeline.py
    }
    "xfyun" {
        if (-not $env:XFYUN_API_KEY) {
            throw "XFYUN_API_KEY 未设置。请先在当前 PowerShell 会话中注入 key。"
        }
        python test_pipeline.py
    }
    default {
        throw "不支持的 Provider: $Provider。可选值：deepseek / gongfeng / xfyun"
    }
}
