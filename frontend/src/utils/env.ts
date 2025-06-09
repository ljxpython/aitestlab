/**
 * 环境检测工具
 * 安全地处理环境变量和浏览器兼容性
 */

/**
 * 检查是否在浏览器环境
 */
export function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

/**
 * 检查是否在Node.js环境
 */
export function isNode(): boolean {
  return typeof process !== 'undefined' && process.versions && process.versions.node;
}

/**
 * 安全地获取环境变量
 */
export function getEnvVar(key: string, defaultValue: string = ''): string {
  try {
    // 浏览器环境
    if (isBrowser()) {
      // 尝试从window对象获取
      const windowEnv = (window as any).__ENV__;
      if (windowEnv && windowEnv[key]) {
        return windowEnv[key];
      }

      // 尝试从meta标签获取
      const metaTag = document.querySelector(`meta[name="env-${key.toLowerCase()}"]`);
      if (metaTag) {
        return metaTag.getAttribute('content') || defaultValue;
      }

      return defaultValue;
    }

    // Node.js环境
    if (isNode() && process.env) {
      return process.env[key] || defaultValue;
    }

    return defaultValue;
  } catch (error) {
    console.warn(`获取环境变量 ${key} 失败，使用默认值:`, defaultValue);
    return defaultValue;
  }
}

/**
 * 获取当前环境类型
 */
export function getEnvironment(): 'development' | 'production' | 'test' {
  const nodeEnv = getEnvVar('NODE_ENV', 'development');

  if (nodeEnv === 'production' || nodeEnv === 'test') {
    return nodeEnv as 'production' | 'test';
  }

  // 在浏览器环境中，根据hostname判断
  if (isBrowser()) {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.includes('dev')) {
      return 'development';
    }
    if (hostname.includes('test') || hostname.includes('staging')) {
      return 'test';
    }
    return 'production';
  }

  return 'development';
}

/**
 * 检查是否为开发环境
 */
export function isDevelopment(): boolean {
  return getEnvironment() === 'development';
}

/**
 * 检查是否为生产环境
 */
export function isProduction(): boolean {
  return getEnvironment() === 'production';
}

/**
 * 检查是否为测试环境
 */
export function isTest(): boolean {
  return getEnvironment() === 'test';
}

/**
 * 安全地执行只在浏览器环境中运行的代码
 */
export function runInBrowser<T>(fn: () => T, fallback?: T): T | undefined {
  if (isBrowser()) {
    try {
      return fn();
    } catch (error) {
      console.warn('浏览器环境代码执行失败:', error);
      return fallback;
    }
  }
  return fallback;
}

/**
 * 安全地执行只在Node.js环境中运行的代码
 */
export function runInNode<T>(fn: () => T, fallback?: T): T | undefined {
  if (isNode()) {
    try {
      return fn();
    } catch (error) {
      console.warn('Node.js环境代码执行失败:', error);
      return fallback;
    }
  }
  return fallback;
}

/**
 * 获取API基础URL
 */
export function getApiBaseUrl(): string {
  // 优先级：环境变量 > 当前域名推断 > 默认值
  const envBaseUrl = getEnvVar('REACT_APP_API_BASE_URL');
  if (envBaseUrl) {
    return envBaseUrl;
  }

  // 在浏览器环境中，根据当前URL推断API地址
  if (isBrowser()) {
    const { protocol, hostname, port } = window.location;

    if (isDevelopment()) {
      // 开发环境，假设后端运行在8000端口
      return `${protocol}//${hostname}:8000/api`;
    } else {
      // 生产环境，使用相对路径
      return '/api';
    }
  }

  // 默认值
  return '/api';
}

/**
 * 调试信息
 */
export function getDebugInfo() {
  return {
    isBrowser: isBrowser(),
    isNode: isNode(),
    environment: getEnvironment(),
    apiBaseUrl: getApiBaseUrl(),
    userAgent: runInBrowser(() => navigator.userAgent, 'Unknown'),
    nodeVersion: runInNode(() => process.version, 'Unknown'),
  };
}

// 在开发环境中打印调试信息
if (isDevelopment()) {
  console.log('环境信息:', getDebugInfo());
}
