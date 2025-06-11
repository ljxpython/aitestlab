import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import { Typography } from 'antd';
import 'highlight.js/styles/github.css'; // 代码高亮样式

const { Text } = Typography;

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
    <div
      className={className}
      style={{
        lineHeight: '1.6',
        fontSize: '15px',
        color: '#374151',
        maxWidth: '100%',
        overflow: 'hidden',
        wordBreak: 'break-word',
        ...style
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, rehypeRaw]}
        components={{
          // 自定义段落样式
          p: ({ children }) => (
            <p style={{
              marginBottom: '12px',
              lineHeight: '1.6',
              color: 'inherit'
            }}>
              {children}
            </p>
          ),

          // 自定义标题样式
          h1: ({ children }) => (
            <h1 style={{
              fontSize: '24px',
              fontWeight: 600,
              marginBottom: '16px',
              marginTop: '24px',
              color: '#1f2937',
              borderBottom: '2px solid #e5e7eb',
              paddingBottom: '8px'
            }}>
              {children}
            </h1>
          ),

          h2: ({ children }) => (
            <h2 style={{
              fontSize: '20px',
              fontWeight: 600,
              marginBottom: '12px',
              marginTop: '20px',
              color: '#1f2937'
            }}>
              {children}
            </h2>
          ),

          h3: ({ children }) => (
            <h3 style={{
              fontSize: '18px',
              fontWeight: 600,
              marginBottom: '10px',
              marginTop: '16px',
              color: '#374151'
            }}>
              {children}
            </h3>
          ),

          // 自定义代码块样式
          code: ({ inline, className, children, ...props }) => {
            if (inline) {
              return (
                <code
                  style={{
                    backgroundColor: '#f3f4f6',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '14px',
                    fontFamily: 'Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                    color: '#e11d48'
                  }}
                  {...props}
                >
                  {children}
                </code>
              );
            }

            return (
              <code
                className={className}
                style={{
                  display: 'block',
                  backgroundColor: '#f8fafc',
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontFamily: 'Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                  lineHeight: '1.5',
                  overflow: 'auto',
                  border: '1px solid #e5e7eb',
                  maxWidth: '100%',
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap'
                }}
                {...props}
              >
                {children}
              </code>
            );
          },

          // 自定义预格式化文本样式
          pre: ({ children }) => (
            <pre style={{
              backgroundColor: '#f8fafc',
              padding: '16px',
              borderRadius: '8px',
              overflow: 'auto',
              marginBottom: '16px',
              border: '1px solid #e5e7eb',
              maxWidth: '100%',
              wordBreak: 'break-all',
              whiteSpace: 'pre-wrap'
            }}>
              {children}
            </pre>
          ),

          // 自定义列表样式
          ul: ({ children }) => (
            <ul style={{
              marginBottom: '12px',
              paddingLeft: '20px'
            }}>
              {children}
            </ul>
          ),

          ol: ({ children }) => (
            <ol style={{
              marginBottom: '12px',
              paddingLeft: '20px'
            }}>
              {children}
            </ol>
          ),

          li: ({ children }) => (
            <li style={{
              marginBottom: '4px',
              lineHeight: '1.6'
            }}>
              {children}
            </li>
          ),

          // 自定义引用样式
          blockquote: ({ children }) => (
            <blockquote style={{
              borderLeft: '4px solid #667eea',
              paddingLeft: '16px',
              marginLeft: '0',
              marginBottom: '16px',
              backgroundColor: '#f8fafc',
              padding: '12px 16px',
              borderRadius: '0 8px 8px 0',
              fontStyle: 'italic',
              color: '#6b7280'
            }}>
              {children}
            </blockquote>
          ),

          // 自定义表格样式
          table: ({ children }) => (
            <div style={{
              overflowX: 'auto',
              marginBottom: '16px',
              maxWidth: '100%',
              border: '1px solid #e5e7eb',
              borderRadius: '8px'
            }}>
              <table style={{
                width: '100%',
                minWidth: '600px',
                borderCollapse: 'collapse',
                overflow: 'hidden'
              }}>
                {children}
              </table>
            </div>
          ),

          th: ({ children }) => (
            <th style={{
              backgroundColor: '#f9fafb',
              padding: '12px',
              textAlign: 'left',
              fontWeight: 600,
              borderBottom: '1px solid #e5e7eb',
              color: '#374151',
              wordBreak: 'break-word',
              maxWidth: '200px'
            }}>
              {children}
            </th>
          ),

          td: ({ children }) => (
            <td style={{
              padding: '12px',
              borderBottom: '1px solid #f3f4f6',
              color: '#6b7280',
              wordBreak: 'break-word',
              maxWidth: '200px',
              whiteSpace: 'pre-wrap'
            }}>
              {children}
            </td>
          ),

          // 自定义链接样式
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#667eea',
                textDecoration: 'none',
                borderBottom: '1px solid transparent',
                transition: 'border-color 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderBottomColor = '#667eea';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderBottomColor = 'transparent';
              }}
            >
              {children}
            </a>
          ),

          // 自定义强调样式
          strong: ({ children }) => (
            <strong style={{
              fontWeight: 600,
              color: '#1f2937'
            }}>
              {children}
            </strong>
          ),

          em: ({ children }) => (
            <em style={{
              fontStyle: 'italic',
              color: '#6b7280'
            }}>
              {children}
            </em>
          ),

          // 自定义分割线样式
          hr: () => (
            <hr style={{
              border: 'none',
              height: '1px',
              backgroundColor: '#e5e7eb',
              margin: '24px 0'
            }} />
          )
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
