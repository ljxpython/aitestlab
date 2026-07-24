# service-account-project-grants Specification

## Purpose

定义服务账号项目授权、API key 项目访问限制和控制台管理行为。确保机器身份只能访问显式授予的活动项目，授权失效后立即拒绝访问，并在控制台中分开管理项目 grant 与令牌。

## Requirements

### Requirement: 服务账号必须获得显式项目授权
系统 MUST 保证每个服务账号与项目组合最多只有一个活动角色 grant，并复用现有项目角色进行机器身份授权。

#### Scenario: 超级管理员授予项目执行者权限
- **当** 超级管理员为活动服务账号在活动项目中分配 `project_executor`
- **那么** 系统持久化该 grant，并记录语义化授权变更审计事件

#### Scenario: 无权限主体修改服务账号项目授权
- **当** 不具备服务账号项目授权管理权限的主体创建、修改或删除 grant
- **那么** 系统拒绝请求并保留现有 grant

### Requirement: API key 的项目访问必须受 grant 限制
API key 认证 MUST 只加载当前项目的 grant，不得根据平台角色推断项目访问权。

#### Scenario: 服务账号访问已授权项目
- **当** 有效 API key 调用项目接口，且其活动 grant 角色允许所请求权限
- **那么** 系统以该服务账号身份授权请求

#### Scenario: 服务账号访问未授权项目
- **当** 有效 API key 调用一个不存在活动 grant 的项目接口
- **那么** 系统拒绝请求

#### Scenario: 服务账号替换请求项目标识
- **当** 只获得项目 A grant 的服务账号请求属于项目 B 的资源
- **那么** 系统拒绝请求，且不得返回项目 B 数据

### Requirement: 失效凭据或授权必须拒绝访问
当服务账号被停用、API key 已过期或撤销、项目已删除或项目 grant 不存在时，系统 MUST 拒绝项目访问。

#### Scenario: API key 仍有效但项目 grant 被删除
- **当** 超级管理员删除服务账号的项目 grant
- **那么** 后续对该项目的请求立即被拒绝，且无需轮换 API key

### Requirement: 控制台必须分开管理项目授权和令牌
服务账号详情页面 MUST 将项目 grant 与 API key 令牌分区展示，并在删除 grant 前要求用户确认。

#### Scenario: 超级管理员查看服务账号
- **当** 超级管理员打开服务账号详情
- **那么** 页面将令牌生命周期信息和项目 grant 展示为两个独立区域
