# Markdown 渲染测试示例

[← 返回主文档](../../README.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 📚 相关文档
- [Markdown 渲染器](../development/MARKDOWN_RENDERER.md) - 技术实现说明
- [Gemini 功能对比](./GEMINI_FEATURES_COMPARISON.md) - 设计对比

## 🧪 测试用例

以下是一些可以在 AI 对话中测试的 Markdown 示例，用于验证渲染效果。

### 1. 测试用例生成示例

**输入提示**：
```
请为用户登录功能生成完整的测试用例，包含正常流程和异常情况，用 Markdown 格式展示。
```

**期望输出**：
```markdown
# 用户登录功能测试用例

## 测试目标
验证用户登录功能的正确性和安全性

## 测试环境
- 测试环境：UAT
- 浏览器：Chrome 最新版
- 操作系统：Windows 10

## 正常流程测试

### TC001 - 有效用户名和密码登录
**前置条件**：用户已注册且账号状态正常
**测试步骤**：
1. 打开登录页面
2. 输入有效用户名
3. 输入正确密码
4. 点击登录按钮

**预期结果**：
- 登录成功，跳转到首页
- 显示用户信息
- 记录登录日志

## 异常流程测试

### TC002 - 无效用户名登录
**测试步骤**：
1. 输入不存在的用户名
2. 输入任意密码
3. 点击登录按钮

**预期结果**：
- 显示"用户名不存在"错误提示
- 不允许登录
- 记录失败日志

### TC003 - 密码错误
**测试步骤**：
1. 输入有效用户名
2. 输入错误密码
3. 点击登录按钮

**预期结果**：
- 显示"密码错误"提示
- 连续错误3次锁定账号
```

### 2. 自动化脚本生成示例

**输入提示**：
```
用 Selenium Python 编写用户登录的自动化测试脚本，使用页面对象模式。
```

**期望输出**：
````markdown
# 用户登录自动化测试脚本

## 页面对象类

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class LoginPage:
    """登录页面对象"""

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    # 页面元素定位
    USERNAME_INPUT = (By.ID, "username")
    PASSWORD_INPUT = (By.ID, "password")
    LOGIN_BUTTON = (By.ID, "login-btn")
    ERROR_MESSAGE = (By.CLASS_NAME, "error-message")

    def enter_username(self, username):
        """输入用户名"""
        element = self.wait.until(EC.presence_of_element_located(self.USERNAME_INPUT))
        element.clear()
        element.send_keys(username)

    def enter_password(self, password):
        """输入密码"""
        element = self.wait.until(EC.presence_of_element_located(self.PASSWORD_INPUT))
        element.clear()
        element.send_keys(password)

    def click_login(self):
        """点击登录按钮"""
        element = self.wait.until(EC.element_to_be_clickable(self.LOGIN_BUTTON))
        element.click()

    def get_error_message(self):
        """获取错误信息"""
        try:
            element = self.wait.until(EC.presence_of_element_located(self.ERROR_MESSAGE))
            return element.text
        except:
            return None
```

## 测试用例类

```python
import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class LoginTest(unittest.TestCase):
    """登录功能测试类"""

    def setUp(self):
        """测试前置条件"""
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service)
        self.driver.get("https://example.com/login")
        self.login_page = LoginPage(self.driver)

    def tearDown(self):
        """测试后清理"""
        self.driver.quit()

    def test_valid_login(self):
        """测试有效登录"""
        self.login_page.enter_username("testuser")
        self.login_page.enter_password("password123")
        self.login_page.click_login()

        # 验证登录成功
        self.assertIn("dashboard", self.driver.current_url)

    def test_invalid_username(self):
        """测试无效用户名"""
        self.login_page.enter_username("invaliduser")
        self.login_page.enter_password("password123")
        self.login_page.click_login()

        # 验证错误信息
        error_msg = self.login_page.get_error_message()
        self.assertIn("用户名不存在", error_msg)

    def test_wrong_password(self):
        """测试错误密码"""
        self.login_page.enter_username("testuser")
        self.login_page.enter_password("wrongpassword")
        self.login_page.click_login()

        # 验证错误信息
        error_msg = self.login_page.get_error_message()
        self.assertIn("密码错误", error_msg)

if __name__ == "__main__":
    unittest.main()
```

## 运行说明

1. 安装依赖：`pip install selenium webdriver-manager`
2. 运行测试：`python test_login.py`
3. 查看报告：测试结果会在控制台显示
````

### 2. 代码块测试

**输入提示**：
```
用 Python 实现快速排序算法，并用 Markdown 格式展示代码和说明。
```

**期望输出**：
````markdown
# 快速排序算法

快速排序是一种高效的排序算法，采用分治策略。

## 算法实现

```python
def quick_sort(arr):
    """
    快速排序算法实现

    Args:
        arr: 待排序的数组

    Returns:
        排序后的数组
    """
    if len(arr) <= 1:
        return arr

    # 选择基准元素
    pivot = arr[len(arr) // 2]

    # 分割数组
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    # 递归排序并合并
    return quick_sort(left) + middle + quick_sort(right)

# 使用示例
numbers = [64, 34, 25, 12, 22, 11, 90]
sorted_numbers = quick_sort(numbers)
print(f"排序结果: {sorted_numbers}")
```

## 时间复杂度

- **最佳情况**: O(n log n)
- **平均情况**: O(n log n)
- **最坏情况**: O(n²)

## 空间复杂度

O(log n) - 递归调用栈的深度
````

### 3. 表格测试

**输入提示**：
```
用表格对比不同排序算法的特点，用 Markdown 格式展示。
```

**期望输出**：
```markdown
# 排序算法对比

| 算法名称 | 时间复杂度(平均) | 时间复杂度(最坏) | 空间复杂度 | 稳定性 | 适用场景 |
|----------|------------------|------------------|------------|--------|----------|
| 冒泡排序 | O(n²) | O(n²) | O(1) | 稳定 | 小数据集 |
| 选择排序 | O(n²) | O(n²) | O(1) | 不稳定 | 小数据集 |
| 插入排序 | O(n²) | O(n²) | O(1) | 稳定 | 小数据集、部分有序 |
| 快速排序 | O(n log n) | O(n²) | O(log n) | 不稳定 | 大数据集 |
| 归并排序 | O(n log n) | O(n log n) | O(n) | 稳定 | 大数据集、要求稳定 |
| 堆排序 | O(n log n) | O(n log n) | O(1) | 不稳定 | 大数据集、内存受限 |

## 选择建议

- **小数据集 (n < 50)**: 插入排序
- **大数据集**: 快速排序或归并排序
- **要求稳定性**: 归并排序
- **内存受限**: 堆排序
```

### 4. 引用和链接测试

**输入提示**：
```
介绍 React 框架，包含引用、链接和多级标题，用 Markdown 格式。
```

**期望输出**：
```markdown
# React 框架介绍

React 是由 Facebook 开发的用于构建用户界面的 JavaScript 库。

## 核心特性

### 1. 组件化
React 采用组件化的开发模式，将 UI 拆分为独立、可复用的组件。

### 2. 虚拟 DOM
React 使用虚拟 DOM 来提高性能，减少直接操作真实 DOM 的开销。

### 3. 单向数据流
数据在 React 中是单向流动的，从父组件流向子组件。

## 官方资源

- [React 官方文档](https://reactjs.org/)
- [React GitHub 仓库](https://github.com/facebook/react)
- [Create React App](https://create-react-app.dev/)

## 社区评价

> React 的学习曲线相对平缓，文档完善，社区活跃。它的组件化思想和虚拟 DOM 机制使得开发大型应用变得更加容易。
>
> —— 《现代前端开发指南》

## 版本历史

React 经历了多个重要版本：

- **React 16**: 引入 Fiber 架构
- **React 17**: 改进事件系统
- **React 18**: 并发特性和自动批处理
```

### 5. 混合内容测试

**输入提示**：
```
写一份完整的技术文档，介绍如何搭建 React + TypeScript 项目，包含代码、表格、列表等多种格式。
```

**期望输出**：
````markdown
# React + TypeScript 项目搭建指南

本文档将指导您从零开始搭建一个 React + TypeScript 项目。

## 环境要求

在开始之前，请确保您的开发环境满足以下要求：

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| Node.js | >= 14.0.0 | JavaScript 运行环境 |
| npm | >= 6.0.0 | 包管理器 |
| Git | >= 2.0.0 | 版本控制工具 |

## 创建项目

### 1. 使用 Create React App

```bash
# 创建 TypeScript 项目
npx create-react-app my-app --template typescript

# 进入项目目录
cd my-app

# 启动开发服务器
npm start
```

### 2. 项目结构

创建完成后，项目结构如下：

```
my-app/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── components/
│   ├── App.tsx
│   ├── index.tsx
│   └── index.css
├── package.json
└── tsconfig.json
```

## 配置 TypeScript

### 1. tsconfig.json 配置

```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "es6"],
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": [
    "src"
  ]
}
```

### 2. 类型定义

创建 `src/types/index.ts` 文件：

```typescript
// 用户接口定义
export interface User {
  id: number;
  name: string;
  email: string;
  avatar?: string;
}

// API 响应接口
export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

// 组件 Props 类型
export interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary';
}
```

## 最佳实践

### 代码组织
1. **组件分离**: 将组件放在独立的文件中
2. **类型定义**: 统一管理类型定义
3. **样式管理**: 使用 CSS Modules 或 Styled Components

### 开发规范
- 使用 **ESLint** 进行代码检查
- 使用 **Prettier** 进行代码格式化
- 编写 **单元测试** 确保代码质量

> **提示**: 建议使用 VS Code 编辑器，配合 TypeScript 插件可以获得更好的开发体验。

## 常用依赖

以下是一些常用的依赖包：

- **路由**: `react-router-dom`
- **状态管理**: `redux`, `zustand`
- **UI 库**: `antd`, `material-ui`
- **HTTP 客户端**: `axios`, `fetch`
- **工具库**: `lodash`, `dayjs`

---

**总结**: React + TypeScript 是现代前端开发的优秀组合，提供了类型安全和良好的开发体验。
````

## 🎯 测试方法

### 1. 在 AI 对话中测试
1. 启动前端服务：`make start-frontend`
2. 访问 http://localhost:3000
3. 输入上述测试提示
4. 观察 AI 回复的 Markdown 渲染效果

### 2. 验证要点
- ✅ 标题层级正确显示
- ✅ 代码块有语法高亮
- ✅ 表格格式整齐
- ✅ 列表缩进正确
- ✅ 链接可以点击
- ✅ 引用块样式美观
- ✅ 强调文本突出显示

### 3. 常见问题
- 如果代码高亮不显示，检查 highlight.js 是否正确加载
- 如果表格显示异常，检查 CSS 样式是否冲突
- 如果链接无法点击，检查 rehype-raw 插件是否启用

---

🧪 **测试目标**: 确保 Markdown 渲染器能够正确处理各种格式，提供优秀的阅读体验！
