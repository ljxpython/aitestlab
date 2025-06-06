import React, { useState, useEffect, useRef } from 'react';
import { Button, Space, Typography, message as antMessage, Avatar, Tooltip, Dropdown } from 'antd';
import {
  ClearOutlined,
  SettingOutlined,
  RobotOutlined,
  StarOutlined,
  ShareAltOutlined,
  MoreOutlined,
  BulbOutlined,
  CodeOutlined,
  EditOutlined,
  FileTextOutlined,
  HistoryOutlined
} from '@ant-design/icons';
import { v4 as uuidv4 } from 'uuid';
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import ConversationHistory from '@/components/ConversationHistory';
import SettingsPanel from '@/components/SettingsPanel';
import { ChatMessage as ChatMessageType, StreamChunk } from '@/types/chat';
import { chatApi } from '@/services/api';

const { Title, Text } = Typography;

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>('');
  const [historyVisible, setHistoryVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初始化对话ID
  useEffect(() => {
    setConversationId(uuidv4());
  }, []);

  // 清理 EventSource
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const userMessage: ChatMessageType = {
      id: uuidv4(),
      content,
      role: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    // 创建助手消息占位符
    const assistantMessageId = uuidv4();
    const assistantMessage: ChatMessageType = {
      id: assistantMessageId,
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      // 使用流式API
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
          system_message: '你是一个有用的AI助手，请用中文回答问题。',
        }),
      });

      if (!response.ok) {
        throw new Error('网络请求失败');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                const chunk: StreamChunk = data;

                if (chunk.content) {
                  setMessages(prev =>
                    prev.map(msg =>
                      msg.id === assistantMessageId
                        ? { ...msg, content: msg.content + chunk.content }
                        : msg
                    )
                  );
                }

                if (chunk.is_complete) {
                  setMessages(prev =>
                    prev.map(msg =>
                      msg.id === assistantMessageId
                        ? { ...msg, isStreaming: false }
                        : msg
                    )
                  );
                  break;
                }
              } catch (e) {
                console.error('解析SSE数据失败:', e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      antMessage.error('发送消息失败，请重试');

      // 移除失败的助手消息
      setMessages(prev => prev.filter(msg => msg.id !== assistantMessageId));
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = async () => {
    try {
      if (conversationId) {
        await chatApi.clearConversation(conversationId);
      }
      setMessages([]);
      setConversationId(uuidv4());
      antMessage.success('对话已清除');
    } catch (error) {
      console.error('清除对话失败:', error);
      antMessage.error('清除对话失败');
    }
  };

  // 测试平台相关的建议卡片
  const suggestionCards = [
    {
      icon: <FileTextOutlined />,
      title: "测试用例生成",
      description: "根据用户登录功能需求，生成完整的测试用例",
      color: "#f59e0b"
    },
    {
      icon: <CodeOutlined />,
      title: "自动化脚本",
      description: "用 Selenium 编写 Web 自动化测试脚本，包含页面对象模式",
      color: "#10b981"
    },
    {
      icon: <BulbOutlined />,
      title: "问题诊断",
      description: "分析测试失败的原因，并提供解决方案和优化建议",
      color: "#8b5cf6"
    },
    {
      icon: <EditOutlined />,
      title: "测试报告",
      description: "帮我分析测试结果数据，生成测试报告和改进建议",
      color: "#ef4444"
    }
  ];

  const menuItems = [
    {
      key: 'history',
      icon: <HistoryOutlined />,
      label: '对话历史',
      onClick: () => setHistoryVisible(true)
    },
    {
      key: 'clear',
      icon: <ClearOutlined />,
      label: '清除对话',
      onClick: handleClearChat,
      disabled: messages.length === 0
    },
    {
      key: 'share',
      icon: <ShareAltOutlined />,
      label: '分享对话'
    },
    {
      key: 'star',
      icon: <StarOutlined />,
      label: '收藏对话'
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
      onClick: () => setSettingsVisible(true)
    }
  ];

  return (
    <div className="gemini-gradient" style={{ minHeight: '100vh', position: 'relative' }}>
      {/* 背景装饰 */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%)',
        pointerEvents: 'none'
      }} />

      <div style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '0 20px',
        position: 'relative',
        zIndex: 1
      }}>
        {/* Gemini 风格头部 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 0',
          borderBottom: messages.length > 0 ? '1px solid rgba(255, 255, 255, 0.1)' : 'none'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 18,
              fontWeight: 'bold'
            }}>
              G
            </div>
            <div>
              <Title level={3} style={{ margin: 0, color: 'white', fontWeight: 400 }}>
                测试助手
              </Title>
              <Text style={{ color: 'rgba(255, 255, 255, 0.8)', fontSize: 14 }}>
                自动化测试平台 AI 模块
              </Text>
            </div>
          </div>

          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button
              type="text"
              icon={<MoreOutlined />}
              style={{
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: 20
              }}
              className="gemini-hover"
            />
          </Dropdown>
        </div>

        {/* 主要内容区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingTop: 20 }}>
          {messages.length === 0 ? (
            /* 欢迎页面 - Gemini 风格 */
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '40px 20px'
            }}>
              <div style={{
                marginBottom: 48,
                animation: 'geminiSlideIn 0.8s cubic-bezier(0.4, 0, 0.2, 1)'
              }}>
                <Title level={1} style={{
                  color: 'white',
                  fontSize: 48,
                  fontWeight: 300,
                  marginBottom: 16,
                  background: 'linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.8) 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  你好，我是测试助手
                </Title>
                <Text style={{
                  color: 'rgba(255, 255, 255, 0.9)',
                  fontSize: 18,
                  display: 'block',
                  marginBottom: 8
                }}>
                  我可以帮助您生成测试用例、编写自动化脚本、诊断问题等
                </Text>
                <Text style={{
                  color: 'rgba(255, 255, 255, 0.7)',
                  fontSize: 14
                }}>
                  选择下面的测试场景开始对话，或者直接描述您的测试需求
                </Text>
              </div>

              {/* 建议卡片 */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 16,
                width: '100%',
                maxWidth: 800,
                marginBottom: 40
              }}>
                {suggestionCards.map((card, index) => (
                  <div
                    key={index}
                    className="glass-effect gemini-hover"
                    style={{
                      padding: 20,
                      borderRadius: 16,
                      cursor: 'pointer',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      animationDelay: `${index * 0.1}s`
                    }}
                    onClick={() => handleSendMessage(card.description)}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      marginBottom: 12
                    }}>
                      <div style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        backgroundColor: card.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        marginRight: 12
                      }}>
                        {card.icon}
                      </div>
                      <Text style={{
                        color: 'white',
                        fontWeight: 500,
                        fontSize: 16
                      }}>
                        {card.title}
                      </Text>
                    </div>
                    <Text style={{
                      color: 'rgba(255, 255, 255, 0.8)',
                      fontSize: 14,
                      lineHeight: 1.5
                    }}>
                      {card.description}
                    </Text>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* 对话模式 */
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              borderRadius: '20px 20px 0 0',
              backdropFilter: 'blur(10px)',
              overflow: 'hidden'
            }}>
              {/* 消息列表 */}
              <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '24px',
                backgroundColor: 'transparent'
              }}>
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}

          {/* 输入区域 - 始终显示 */}
          <div style={{
            backgroundColor: messages.length > 0 ? 'rgba(255, 255, 255, 0.95)' : 'transparent',
            backdropFilter: messages.length > 0 ? 'blur(10px)' : 'none',
            borderRadius: messages.length > 0 ? '0 0 20px 20px' : '20px'
          }}>
            <ChatInput
              onSend={handleSendMessage}
              loading={loading}
              placeholder="输入您的问题..."
            />
          </div>
        </div>
      </div>

      {/* 对话历史侧边栏 */}
      <ConversationHistory
        visible={historyVisible}
        onClose={() => setHistoryVisible(false)}
        onSelectConversation={(id) => {
          // 这里应该加载选中的对话
          console.log('选择对话:', id);
          setHistoryVisible(false);
        }}
        currentConversationId={conversationId}
      />

      {/* 设置面板 */}
      <SettingsPanel
        visible={settingsVisible}
        onClose={() => setSettingsVisible(false)}
      />
    </div>
  );
};

export default ChatPage;
