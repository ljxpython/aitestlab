import React from 'react';
import { Avatar, Typography, Button, Space } from 'antd';
import { UserOutlined, CopyOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import { ChatMessage as ChatMessageType } from '@/types/chat';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import dayjs from 'dayjs';

const { Text } = Typography;

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
  };

  return (
    <div
      className="fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        marginBottom: 32,
        maxWidth: '100%',
      }}
    >
      {/* 消息头部 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        marginBottom: 8,
        gap: 8
      }}>
        {isUser ? (
          <>
            <Avatar
              size={24}
              icon={<UserOutlined />}
              style={{
                backgroundColor: '#667eea',
                fontSize: 12
              }}
            />
            <Text style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              您
            </Text>
          </>
        ) : (
          <>
            <div style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 12,
              fontWeight: 'bold'
            }}>
              T
            </div>
            <Text style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              测试助手
            </Text>
          </>
        )}
        <Text style={{ fontSize: 12, color: '#9ca3af' }}>
          {dayjs(message.timestamp).format('HH:mm')}
        </Text>
      </div>

      {/* 消息内容 */}
      <div style={{
        marginLeft: isUser ? 0 : 32,
        backgroundColor: isUser ? '#f3f4f6' : 'transparent',
        padding: isUser ? '12px 16px' : '0',
        borderRadius: isUser ? '12px' : '0',
        border: isUser ? '1px solid #e5e7eb' : 'none'
      }}>
        {isUser ? (
          // 用户消息：简单文本显示
          <div
            style={{
              margin: 0,
              color: '#374151',
              fontSize: '15px',
              lineHeight: '1.6',
              wordBreak: 'break-word'
            }}
          >
            {message.content}
          </div>
        ) : (
          // AI 消息：Markdown 渲染
          <div style={{ position: 'relative' }}>
            <MarkdownRenderer
              content={message.content}
              style={{
                fontFamily: '"Google Sans", -apple-system, BlinkMacSystemFont, sans-serif'
              }}
            />
            {isStreaming && (
              <span className="typing-indicator" style={{ marginLeft: 8 }}>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
              </span>
            )}
          </div>
        )}

        {/* 操作按钮 - 仅对 AI 回复显示 */}
        {!isUser && !isStreaming && message.content && (
          <div style={{
            marginTop: 12,
            display: 'flex',
            gap: 8,
            opacity: 0.7,
            transition: 'opacity 0.2s'
          }}>
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={handleCopy}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<LikeOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<DislikeOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
