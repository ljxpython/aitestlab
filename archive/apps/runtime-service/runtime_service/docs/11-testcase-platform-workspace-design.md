# Testcase 平台工作区一期设计

状态：`Historical-in-place`

这篇文档记录的是 testcase 平台工作区的早期一期设计思路。

当前其中大量目标已经落地，但文中的“当前事实”和部分接口路径已经不是最新状态，因此不能再把它当成当前实现真相源。

## 当前实现应优先看哪里

当前正式链路与代码真相源请优先参考：

- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/src/modules/testcase/pages/**`
- `apps/platform-api/app/modules/testcase/presentation/http.py`
- `apps/platform-api/app/modules/testcase/application/service.py`
- `apps/interaction-data-service/docs/README.md`
- `apps/runtime-service/runtime_service/docs/10-test-case-service-persistence-design.md`

## 这篇文档为什么还保留

它仍然保留两类价值：

1. 解释 testcase 工作区最初为什么拆成 `生成 / 用例管理 / 文档解析` 三块
2. 记录平台工作区、结果域和 runtime 之间的早期收敛路径

## 当前正式架构结果

当前正式 testcase 链路已经收敛为：

```text
platform-web /workspace/testcase/*
  -> platform-api /api/projects/{project_id}/testcase/*
    -> interaction-data-service /api/test-case-service/*

platform-web /workspace/testcase/generate
  -> platform-api runtime gateway
    -> runtime-service/test_case_service
```

其中：

- 正式平台前端宿主是 `platform-web`，不是旧 `platform-web`
- 正式控制面宿主是 `platform-api`，不是旧 `platform-api`
- testcase 管理接口当前前缀是 `/api/projects/{project_id}/testcase`
- testcase 工作区当前已经有正式路由和页面，而不是仅停留在设计阶段

## 相比原设计，当前已经落地的内容

### 1. 平台工作区入口已存在

当前 `platform-web` 已存在：

- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`

默认路由：

- `/workspace/testcase` -> `/workspace/testcase/generate`

### 2. 控制面 testcase 模块已存在

当前 `platform-api` 已提供 testcase 模块接口，包括：

- `GET /api/projects/{project_id}/testcase/overview`
- `GET /api/projects/{project_id}/testcase/role`
- `GET /api/projects/{project_id}/testcase/batches`
- `GET /api/projects/{project_id}/testcase/batches/{batch_id}`
- `GET /api/projects/{project_id}/testcase/documents`
- `GET /api/projects/{project_id}/testcase/documents/{document_id}`
- `GET /api/projects/{project_id}/testcase/documents/{document_id}/relations`
- `GET /api/projects/{project_id}/testcase/documents/{document_id}/preview`
- `GET /api/projects/{project_id}/testcase/documents/{document_id}/download`
- `GET /api/projects/{project_id}/testcase/documents/export`
- `GET /api/projects/{project_id}/testcase/cases`
- `GET /api/projects/{project_id}/testcase/cases/{case_id}`
- `POST /api/projects/{project_id}/testcase/cases`
- `PATCH /api/projects/{project_id}/testcase/cases/{case_id}`
- `DELETE /api/projects/{project_id}/testcase/cases/{case_id}`
- `GET /api/projects/{project_id}/testcase/cases/export`

### 3. 结果域聚合接口已存在

当前 `interaction-data-service` 已提供：

- `GET /api/test-case-service/overview`
- `GET /api/test-case-service/batches`
- `GET /api/test-case-service/batches/{batch_id}`

### 4. 文档已支持即时持久化方向

原始设计里把“上传后立即可见”放在后续阶段；当前 `test_case_service` 已经沿服务私有持久化层推进到“文档即时持久化 + 正式 testcase 保存分离”的模式。

因此，文档里关于“当前不是上传即落库”的描述已经过期。

## 这篇历史设计里哪些内容不再代表当前事实

以下内容现在应按历史设计理解，而不是当前实现：

- `platform-web` 作为正式 testcase 工作区宿主
- `platform-api` 作为正式 testcase 控制面宿主
- `/_management/projects/{project_id}/testcase` 作为正式接口前缀
- “当前没有 testcase 一级入口 / 页面仍未落地”
- “当前不是上传即落库” 这类早期阶段判断
- “一期只读为主” 这类阶段性冻结表述

## 仍然有效的设计判断

下面这些判断在今天仍然成立：

1. 正式平台前端不应直连 `interaction-data-service`
2. 项目权限、导出、预览代理、聚合读取应继续放在控制面
3. `interaction-data-service` 只维护结果域资源，不接管平台治理
4. testcase 工作区应继续围绕 `生成 / 用例管理 / 文档解析` 三块展开
5. 真实联调验证必须跑通平台链路、runtime 链路和结果域链路，而不是只做局部 mock

## 推荐怎么使用这篇文档

- 想看当前实现：看上面的代码真相源
- 想理解 testcase 工作区为什么是这三个页面、为什么坚持控制面聚合：看本文
- 想看当前 runtime 到结果域的正式持久化设计：看 `10-test-case-service-persistence-design.md`
