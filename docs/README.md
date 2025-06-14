# AI测试实验室 - 文档中心

[← 返回主项目](../README.md)

欢迎来到AI测试实验室的文档中心！这里包含了项目的完整文档，帮助您快速了解和使用本平台。

## 📚 文档导航

### 🚀 快速开始
- [项目概述](./overview/PROJECT_OVERVIEW.md) - 了解项目背景、目标和核心功能
- [开发环境搭建](./development/DEVELOPMENT_SETUP.md) - 快速搭建开发环境
- [Makefile使用指南](./setup/MAKEFILE_GUIDE.md) - 项目管理命令详解

### 🏗️ 系统架构
- [系统架构概览](./architecture/SYSTEM_ARCHITECTURE.md) - 整体架构设计
- [AI模块架构](./architecture/AI_MODULES.md) - AI智能体协作架构
- [用户系统架构](./architecture/USER_SYSTEM.md) - 用户认证和权限管理

### 💻 开发指南
- [开发环境配置](./development/README.md) - 开发环境详细配置
- [前后端集成](./development/FRONTEND_BACKEND_INTEGRATION.md) - API集成和数据流
- [代码重构总结](./development/CODE_REFACTORING_SUMMARY.md) - 代码优化记录
- [日志系统](./development/LOGGING_GUIDE.md) - 日志配置和使用
- [Markdown渲染器](./development/MARKDOWN_RENDERER.md) - 前端Markdown支持

### 🎨 UI设计
- [UI设计指南](./ui-design/UI_DESIGN_GUIDE.md) - 设计规范和组件库
- [导航系统](./ui-design/NAVIGATION_SYSTEM.md) - 导航栏和侧边栏设计
- [测试用例页面优化](./ui-design/TESTCASE_PAGE_OPTIMIZATION.md) - 页面设计优化

### 🔧 项目配置
- [Factory模式配置](./setup/FACTORY_PATTERN.md) - FastAPI应用工厂模式
- [项目配置说明](./setup/README.md) - 配置文件和环境变量

### 🗄️ 数据库
- [数据库设计](./database/DATABASE_DESIGN.md) - 数据模型和关系设计
- [迁移管理](./database/MIGRATION_GUIDE.md) - Aerich迁移使用指南
- [数据初始化](./database/DATA_INITIALIZATION.md) - 默认数据和种子数据

### 🚨 故障排除
- [常见问题](./troubleshooting/README.md) - 常见问题和解决方案
- [进程管理](./troubleshooting/PROCESS_MANAGEMENT.md) - 服务进程管理
- [AutoGen修复](./troubleshooting/AUTOGEN_FIXES.md) - AutoGen相关问题
- [前端图标修复](./troubleshooting/FRONTEND_ICON_FIX.md) - 前端图标问题

### 🔧 修复记录
- [修复记录总览](./fixes/README.md) - 项目修复历史记录
- [后端修复](./fixes/backend/README.md) - 后端相关问题修复
- [前端修复](./fixes/frontend/README.md) - 前端相关问题修复
- [流式处理修复](./fixes/streaming/README.md) - SSE和流式处理修复

### ⚡ 优化记录
- [优化记录总览](./optimizations/README.md) - 项目优化历史记录
- [UI优化](./optimizations/ui/README.md) - 界面和交互优化
- [性能优化](./optimizations/performance/README.md) - 性能提升记录
- [架构优化](./optimizations/architecture/README.md) - 架构改进记录

### 📝 工作记录
- [工作记录总览](./work/README.md) - 项目开发工作记录
- [开发历程](./work/) - 详细的开发过程记录

## 📖 文档说明

### 文档组织原则
- **分类清晰**: 按功能模块和使用场景分类
- **层次分明**: 从概览到详细，从入门到进阶
- **双向链接**: 文档间相互引用，便于导航
- **持续更新**: 随项目发展同步更新

### 新的文档结构特点
- **主入口统一**: docs目录只保留一个README.md作为总入口
- **分类管理**: 相关文档归类到对应的子目录中
- **专题组织**: 修复记录、优化记录、工作记录分别管理
- **导航清晰**: 每个分类都有独立的导航和索引

### 文档分类说明

#### 🔧 修复记录 (fixes/)
记录项目开发过程中遇到的问题和解决方案：
- **后端修复**: API、数据库、日志等后端问题
- **前端修复**: UI、交互、显示等前端问题
- **流式处理修复**: SSE、实时通信等流式处理问题

#### ⚡ 优化记录 (optimizations/)
记录项目的各种优化改进：
- **UI优化**: 界面设计和用户体验优化
- **性能优化**: 系统性能和响应速度优化
- **架构优化**: 代码结构和系统架构优化

#### 📝 工作记录 (work/)
记录项目开发的历程和经验：
- **开发历程**: 详细的开发过程记录
- **经验总结**: 开发过程中的经验和教训

### 文档格式规范
- 使用Markdown格式编写
- 统一的标题层级和格式
- 清晰的代码示例和配置说明
- 丰富的图表和流程图

### 贡献指南
- 新增功能时同步更新相关文档
- 遵循现有的文档结构和格式
- 将文档放到合适的分类目录中
- 及时更新过时的信息

## 🔗 相关链接

- [项目主页](../README.md) - 返回项目根目录
- [在线API文档](http://localhost:8000/docs) - FastAPI自动生成的API文档
- [前端应用](http://localhost:3000) - 前端应用访问地址

## 📞 获取帮助

如果您在使用过程中遇到问题：

1. 首先查看[故障排除](./troubleshooting/README.md)文档
2. 查看相关的[修复记录](./fixes/README.md)
3. 搜索相关的文档和示例
4. 查看项目的Issue和讨论
5. 联系项目维护者

## 📊 文档统计

### 文档数量概览
- **核心文档**: 架构、开发、设计等核心文档 20+ 个
- **修复记录**: 问题修复历史记录 35+ 个
- **优化记录**: 项目优化改进记录 30+ 个
- **工作记录**: 开发历程和经验总结 10+ 个
- **总计**: 95+ 个文档

### 文档覆盖范围
- ✅ 项目概览和快速开始
- ✅ 系统架构和设计文档
- ✅ 开发指南和最佳实践
- ✅ 问题修复和优化记录
- ✅ 故障排除和运维指南
- ✅ 完整的历史记录和经验总结

---

**最后更新**: 2024年12月
**文档版本**: v2.0.0 - 重新整理版
