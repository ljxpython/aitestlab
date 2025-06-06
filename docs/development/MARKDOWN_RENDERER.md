# Markdown 渲染器实现

[← 返回主文档](../../README.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 📚 相关文档
- [Gemini 功能对比](../design/GEMINI_FEATURES_COMPARISON.md) - 前端功能对比
- [Markdown 测试示例](../design/MARKDOWN_TEST_EXAMPLES.md) - 测试用例

## 🎯 实现目标

为 AI 对话界面添加 Markdown 渲染支持，让 AI 输出的文字具有更好的段落结构、代码高亮和格式化效果。

## 📦 技术选型

### 核心依赖
- **react-markdown**: React Markdown 渲染器
- **remark-gfm**: GitHub Flavored Markdown 支持
- **rehype-highlight**: 代码语法高亮
- **rehype-raw**: HTML 标签支持
- **highlight.js**: 代码高亮样式

### 安装命令
```bash
npm install react-markdown remark-gfm rehype-highlight rehype-raw highlight.js
```

## 🎨 功能特性

### 1. 基础 Markdown 支持
- ✅ **段落和换行**: 自动处理段落间距
- ✅ **标题**: H1-H6 标题样式
- ✅ **强调**: 粗体、斜体文本
- ✅ **列表**: 有序和无序列表
- ✅ **链接**: 自动链接处理
- ✅ **分割线**: 水平分割线

### 2. 代码支持
- ✅ **内联代码**: `code` 样式
- ✅ **代码块**: 多行代码格式化
- ✅ **语法高亮**: 支持多种编程语言
- ✅ **代码复制**: 便于复制代码片段

### 3. 高级功能
- ✅ **表格**: 完整的表格渲染
- ✅ **引用**: 美化的引用块
- ✅ **HTML 支持**: 部分 HTML 标签
- ✅ **GitHub 风格**: GFM 扩展支持

## 🔧 实现细节

### 1. MarkdownRenderer 组件

```typescript
interface MarkdownRendererProps {
  content: string;
  className?: string;
  style?: React.CSSProperties;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className,
  style
}) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight, rehypeRaw]}
      components={{
        // 自定义组件样式
      }}
    >
      {content}
    </ReactMarkdown>
  );
};
```

### 2. 自定义样式组件

#### 段落样式
```typescript
p: ({ children }) => (
  <p style={{
    marginBottom: '12px',
    lineHeight: '1.6',
    color: 'inherit'
  }}>
    {children}
  </p>
)
```

#### 代码块样式
```typescript
code: ({ inline, className, children, ...props }) => {
  if (inline) {
    return (
      <code style={{
        backgroundColor: '#f3f4f6',
        padding: '2px 6px',
        borderRadius: '4px',
        fontSize: '14px',
        color: '#e11d48'
      }}>
        {children}
      </code>
    );
  }
  // 代码块样式...
}
```

#### 表格样式
```typescript
table: ({ children }) => (
  <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
    <table style={{
      width: '100%',
      borderCollapse: 'collapse',
      border: '1px solid #e5e7eb',
      borderRadius: '8px'
    }}>
      {children}
    </table>
  </div>
)
```

### 3. 集成到 ChatMessage

```typescript
{isUser ? (
  // 用户消息：简单文本显示
  <div style={{ /* 用户消息样式 */ }}>
    {message.content}
  </div>
) : (
  // AI 消息：Markdown 渲染
  <MarkdownRenderer
    content={message.content}
    style={{
      fontFamily: '"Google Sans", -apple-system, BlinkMacSystemFont, sans-serif'
    }}
  />
)}
```

## 🎨 样式设计

### 1. 颜色方案
- **主文本**: #374151 (深灰色)
- **标题**: #1f2937 (更深的灰色)
- **代码**: #e11d48 (红色强调)
- **链接**: #667eea (品牌蓝色)
- **引用**: #6b7280 (中等灰色)

### 2. 间距设计
- **段落间距**: 12px
- **标题间距**: 上 20px，下 12px
- **代码块**: 16px 内边距
- **表格**: 12px 单元格内边距

### 3. 字体设计
- **正文**: Google Sans 字体系列
- **代码**: Monaco, Consolas 等等宽字体
- **大小**: 15px 正文，14px 代码

## 📊 支持的 Markdown 语法

### 基础语法
```markdown
# 一级标题
## 二级标题
### 三级标题

**粗体文本**
*斜体文本*

- 无序列表项
- 另一个列表项

1. 有序列表项
2. 另一个有序列表项

[链接文本](https://example.com)

`内联代码`

> 引用文本
> 可以多行

---
```

### 代码块
````markdown
```javascript
function hello() {
  console.log("Hello, World!");
}
```

```python
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)
```
````

### 表格
```markdown
| 算法 | 时间复杂度 | 空间复杂度 | 稳定性 |
|------|------------|------------|--------|
| 快速排序 | O(n log n) | O(log n) | 不稳定 |
| 归并排序 | O(n log n) | O(n) | 稳定 |
| 堆排序 | O(n log n) | O(1) | 不稳定 |
```

## 🚀 使用示例

### 1. 基础文本
AI 输入：
```
这是一个段落。

这是另一个段落，包含**粗体**和*斜体*文本。
```

渲染效果：
- 自动段落分隔
- 粗体和斜体样式
- 适当的行间距

### 2. 代码示例
AI 输入：
````
这是一个 Python 函数：

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

使用 `fibonacci(10)` 调用函数。
````

渲染效果：
- 语法高亮的代码块
- 内联代码样式
- 代码复制功能

### 3. 表格数据
AI 输入：
```
| 特性 | React | Vue | Angular |
|------|-------|-----|---------|
| 学习曲线 | 中等 | 简单 | 困难 |
| 性能 | 高 | 高 | 中等 |
| 生态系统 | 丰富 | 丰富 | 完整 |
```

渲染效果：
- 美观的表格样式
- 响应式表格设计
- 清晰的数据展示

## 🔄 后续优化

### 计划中的功能
1. **数学公式**: 支持 LaTeX 数学公式渲染
2. **图表支持**: Mermaid 图表渲染
3. **代码执行**: 在线代码执行功能
4. **导出功能**: 导出为 PDF 或 HTML

### 性能优化
1. **懒加载**: 大型内容的懒加载
2. **虚拟滚动**: 长对话的虚拟滚动
3. **缓存机制**: 渲染结果缓存

## 📈 用户体验提升

### 修改前
- ❌ 纯文本显示，无格式
- ❌ 代码难以阅读
- ❌ 长文本缺乏结构

### 修改后
- ✅ 丰富的格式化显示
- ✅ 语法高亮的代码
- ✅ 清晰的文档结构
- ✅ 专业的技术文档外观

---

🎨 **设计理念**: 让 AI 的回复更加专业、易读、美观，提升用户的阅读体验！
