# runtime_service 鉴权与验证指南

## 认证入口

统一实现文件：`runtime_service/auth/provider.py`

- `custom_auth`：本地 demo token 模式
- `oauth_auth`：Supabase OAuth 模式

## 两套配置文件的职责

- `runtime_service/langgraph.json`
  - 本地默认开发配置
  - 当前不声明 `auth` 段，因此默认按无鉴权模式启动
- `runtime_service/langgraph_auth.json`
  - 鉴权模式配置
  - 显式声明 `auth.path = ./runtime_service/auth/provider.py:oauth_auth`

如果要验证 OAuth / Supabase 鉴权，应使用 `langgraph_auth.json`，而不是修改默认 `langgraph.json` 的说明文案来推断行为。

## OAuth 模式所需环境变量

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- 可选：`SUPABASE_TIMEOUT_SECONDS`

## 启动命令

本地无鉴权模式：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

OAuth 鉴权模式：

```bash
uv run langgraph dev --config runtime_service/langgraph_auth.json --port 8123 --no-browser
```

## 推荐验证

自动化：

```bash
uv run pytest runtime_service/tests/test_auth_core.py runtime_service/tests/test_custom_routes.py runtime_service/tests/test_model_smoke.py -q
```

手工联调时，重点确认：

1. 未鉴权配置下服务可正常启动
2. 鉴权配置下 OAuth provider 可被加载
3. 自定义能力路由不因鉴权切换而失效
