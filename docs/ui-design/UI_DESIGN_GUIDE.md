# UI 设计指南

## 设计理念

AI 测试平台的界面设计遵循现代化、专业化、易用性的原则，采用 Ant Design Pro 风格，打造简洁高效的用户体验。

## 设计原则

### 1. 简约主义
- **Less is More**: 去除不必要的装饰元素
- **功能优先**: 突出核心功能，弱化次要信息
- **留白运用**: 合理的空间分配，提升视觉舒适度

### 2. 一致性
- **视觉一致**: 统一的色彩、字体、间距规范
- **交互一致**: 相同功能使用相同的交互模式
- **信息一致**: 统一的信息架构和表达方式

### 3. 易用性
- **直观操作**: 符合用户习惯的交互方式
- **清晰反馈**: 及时的操作反馈和状态提示
- **容错设计**: 友好的错误处理和恢复机制

## 配色方案

### 主色调
```css
/* 品牌主色 - 科技蓝 */
--primary-color: #1890ff;
--primary-hover: #40a9ff;
--primary-active: #096dd9;

/* 辅助色 - 渐变紫蓝 */
--gradient-start: #667eea;
--gradient-end: #764ba2;
--gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

### 中性色
```css
/* 文字颜色 */
--text-primary: #262626;      /* 主要文字 */
--text-secondary: #595959;    /* 次要文字 */
--text-tertiary: #8c8c8c;     /* 辅助文字 */
--text-disabled: #bfbfbf;     /* 禁用文字 */

/* 背景颜色 */
--bg-primary: #ffffff;        /* 主背景 */
--bg-secondary: #fafafa;      /* 次背景 */
--bg-tertiary: #f5f5f5;       /* 三级背景 */
--bg-disabled: #f5f5f5;       /* 禁用背景 */
```

### 边框颜色
```css
/* 边框 */
--border-light: #f0f0f0;      /* 浅边框 */
--border-normal: #d9d9d9;     /* 普通边框 */
--border-dark: #bfbfbf;       /* 深边框 */
```

### 状态颜色
```css
/* 成功 */
--success-color: #52c41a;
--success-bg: #f6ffed;
--success-border: #b7eb8f;

/* 警告 */
--warning-color: #faad14;
--warning-bg: #fffbe6;
--warning-border: #ffe58f;

/* 错误 */
--error-color: #ff4d4f;
--error-bg: #fff2f0;
--error-border: #ffccc7;

/* 信息 */
--info-color: #1890ff;
--info-bg: #e6f7ff;
--info-border: #91d5ff;
```

## 字体规范

### 字体族
```css
/* 主字体 */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
             'Helvetica Neue', Arial, 'Noto Sans', sans-serif;

/* 代码字体 */
font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo,
             Courier, monospace;
```

### 字体大小
```css
/* 标题 */
--font-size-h1: 32px;         /* 主标题 */
--font-size-h2: 24px;         /* 二级标题 */
--font-size-h3: 20px;         /* 三级标题 */
--font-size-h4: 18px;         /* 四级标题 */

/* 正文 */
--font-size-lg: 16px;         /* 大号正文 */
--font-size-base: 14px;       /* 基础正文 */
--font-size-sm: 12px;         /* 小号正文 */
--font-size-xs: 10px;         /* 极小正文 */
```

### 字重
```css
--font-weight-light: 300;     /* 细体 */
--font-weight-normal: 400;    /* 常规 */
--font-weight-medium: 500;    /* 中等 */
--font-weight-bold: 600;      /* 粗体 */
```

## 间距规范

### 基础间距
```css
/* 8px 基础单位 */
--space-xs: 4px;              /* 极小间距 */
--space-sm: 8px;              /* 小间距 */
--space-md: 12px;             /* 中等间距 */
--space-lg: 16px;             /* 大间距 */
--space-xl: 24px;             /* 超大间距 */
--space-xxl: 32px;            /* 极大间距 */
```

### 组件间距
```css
/* 内边距 */
--padding-xs: 4px 8px;        /* 极小内边距 */
--padding-sm: 8px 12px;       /* 小内边距 */
--padding-md: 12px 16px;      /* 中等内边距 */
--padding-lg: 16px 24px;      /* 大内边距 */

/* 外边距 */
--margin-xs: 4px;             /* 极小外边距 */
--margin-sm: 8px;             /* 小外边距 */
--margin-md: 16px;            /* 中等外边距 */
--margin-lg: 24px;            /* 大外边距 */
```

## 圆角规范

```css
/* 圆角半径 */
--border-radius-sm: 4px;      /* 小圆角 */
--border-radius-md: 6px;      /* 中等圆角 */
--border-radius-lg: 8px;      /* 大圆角 */
--border-radius-xl: 12px;     /* 超大圆角 */
--border-radius-round: 50%;   /* 圆形 */
```

## 阴影规范

```css
/* 阴影效果 */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.03);
--shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06);
--shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.08);
--shadow-xl: 0 8px 32px rgba(0, 0, 0, 0.12);

/* 品牌阴影 */
--shadow-primary: 0 4px 12px rgba(102, 126, 234, 0.3);
--shadow-primary-hover: 0 6px 16px rgba(102, 126, 234, 0.4);
```

## 组件设计规范

### 按钮设计
```css
/* 主要按钮 */
.btn-primary {
  background: var(--gradient-primary);
  border: none;
  border-radius: var(--border-radius-md);
  color: white;
  font-weight: var(--font-weight-medium);
  box-shadow: var(--shadow-primary);
  transition: all 0.3s ease;
}

.btn-primary:hover {
  box-shadow: var(--shadow-primary-hover);
  transform: translateY(-1px);
}
```

### 卡片设计
```css
.card {
  background: var(--bg-primary);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-light);
  overflow: hidden;
  transition: all 0.3s ease;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### 表单设计
```css
.form-item {
  margin-bottom: var(--space-lg);
}

.form-input {
  border-radius: var(--border-radius-md);
  border: 1px solid var(--border-normal);
  padding: var(--padding-sm);
  font-size: var(--font-size-base);
  transition: all 0.3s ease;
}

.form-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}
```

## 动画规范

### 过渡动画
```css
/* 标准过渡 */
--transition-fast: 0.2s ease;
--transition-normal: 0.3s ease;
--transition-slow: 0.5s ease;

/* 缓动函数 */
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-out: cubic-bezier(0.0, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
```

### 常用动画
```css
/* 淡入淡出 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 滑入效果 */
@keyframes slideInUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* 缩放效果 */
@keyframes scaleIn {
  from {
    transform: scale(0.9);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
```

## 响应式设计

### 断点规范
```css
/* 断点定义 */
--breakpoint-xs: 480px;       /* 超小屏 */
--breakpoint-sm: 768px;       /* 小屏 */
--breakpoint-md: 992px;       /* 中屏 */
--breakpoint-lg: 1200px;      /* 大屏 */
--breakpoint-xl: 1600px;      /* 超大屏 */
```

### 响应式布局
```css
/* 移动端优先 */
.container {
  width: 100%;
  padding: 0 var(--space-md);
}

@media (min-width: 768px) {
  .container {
    max-width: 750px;
    margin: 0 auto;
  }
}

@media (min-width: 992px) {
  .container {
    max-width: 970px;
  }
}

@media (min-width: 1200px) {
  .container {
    max-width: 1170px;
  }
}
```

## 无障碍设计

### 颜色对比度
- 正文文字对比度 ≥ 4.5:1
- 大号文字对比度 ≥ 3:1
- 非文字元素对比度 ≥ 3:1

### 键盘导航
- 所有交互元素支持键盘访问
- 清晰的焦点指示器
- 合理的Tab顺序

### 屏幕阅读器
- 语义化HTML结构
- 适当的ARIA标签
- 有意义的alt文本

## 设计工具

### 设计系统
- **Figma**: 界面设计和原型
- **Ant Design**: 组件库参考
- **Color Hunt**: 配色方案

### 开发工具
- **CSS Variables**: 设计令牌管理
- **Styled Components**: 组件样式
- **PostCSS**: CSS处理

## 相关文档

- [导航系统设计](./NAVIGATION_SYSTEM.md)
- [响应式设计](./RESPONSIVE_DESIGN.md)
- [组件库文档](../development/COMPONENT_GUIDE.md)
- [设计资源](./DESIGN_RESOURCES.md)
