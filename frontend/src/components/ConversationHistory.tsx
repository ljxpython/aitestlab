import React, { useState, useEffect } from 'react';
import { Drawer, List, Button, Typography, Space, Popconfirm, Input } from 'antd';
import {
  HistoryOutlined,
  DeleteOutlined,
  EditOutlined,
  SearchOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';

const { Text, Title } = Typography;
const { Search } = Input;

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
}

interface ConversationHistoryProps {
  visible: boolean;
  onClose: () => void;
  onSelectConversation: (conversationId: string) => void;
  currentConversationId?: string;
}

const ConversationHistory: React.FC<ConversationHistoryProps> = ({
  visible,
  onClose,
  onSelectConversation,
  currentConversationId
}) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchText, setSearchText] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // 模拟数据 - 实际项目中应该从 API 获取
  useEffect(() => {
    const mockConversations: Conversation[] = [
      {
        id: '1',
        title: '关于 React 的问题',
        lastMessage: '谢谢你的详细解答！',
        timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30分钟前
        messageCount: 8
      },
      {
        id: '2',
        title: 'Python 数据分析',
        lastMessage: '请帮我分析这个数据集',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2小时前
        messageCount: 15
      },
      {
        id: '3',
        title: '写一首关于春天的诗',
        lastMessage: '春风十里不如你...',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1天前
        messageCount: 3
      }
    ];
    setConversations(mockConversations);
  }, []);

  const filteredConversations = conversations.filter(conv =>
    conv.title.toLowerCase().includes(searchText.toLowerCase()) ||
    conv.lastMessage.toLowerCase().includes(searchText.toLowerCase())
  );

  const handleDelete = (id: string) => {
    setConversations(prev => prev.filter(conv => conv.id !== id));
  };

  const handleEdit = (id: string, newTitle: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, title: newTitle } : conv
      )
    );
    setEditingId(null);
    setEditTitle('');
  };

  const startEdit = (conversation: Conversation) => {
    setEditingId(conversation.id);
    setEditTitle(conversation.title);
  };

  const formatTime = (timestamp: Date) => {
    const now = dayjs();
    const time = dayjs(timestamp);

    if (now.diff(time, 'day') === 0) {
      return time.format('HH:mm');
    } else if (now.diff(time, 'day') === 1) {
      return '昨天';
    } else if (now.diff(time, 'day') < 7) {
      return `${now.diff(time, 'day')}天前`;
    } else {
      return time.format('MM/DD');
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <HistoryOutlined />
          <span>对话历史</span>
        </Space>
      }
      placement="left"
      onClose={onClose}
      open={visible}
      width={320}
      styles={{
        body: { padding: 0 }
      }}
    >
      {/* 搜索框 */}
      <div style={{ padding: '16px 16px 0' }}>
        <Search
          placeholder="搜索对话..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ marginBottom: 16 }}
        />
      </div>

      {/* 对话列表 */}
      <List
        dataSource={filteredConversations}
        renderItem={(conversation) => (
          <List.Item
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #f0f0f0',
              backgroundColor: conversation.id === currentConversationId ? '#f0f9ff' : 'transparent',
              cursor: 'pointer'
            }}
            onClick={() => onSelectConversation(conversation.id)}
          >
            <div style={{ width: '100%' }}>
              {/* 标题 */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: 4
              }}>
                {editingId === conversation.id ? (
                  <Input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onPressEnter={() => handleEdit(conversation.id, editTitle)}
                    onBlur={() => handleEdit(conversation.id, editTitle)}
                    style={{ fontSize: 14, fontWeight: 500 }}
                    autoFocus
                  />
                ) : (
                  <Text
                    style={{
                      fontSize: 14,
                      fontWeight: 500,
                      color: '#1f2937',
                      lineHeight: 1.4
                    }}
                    ellipsis={{ tooltip: conversation.title }}
                  >
                    {conversation.title}
                  </Text>
                )}

                <Space size={4}>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      startEdit(conversation);
                    }}
                    style={{
                      color: '#6b7280',
                      padding: 0,
                      width: 20,
                      height: 20
                    }}
                  />
                  <Popconfirm
                    title="确定删除这个对话吗？"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDelete(conversation.id);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        color: '#ef4444',
                        padding: 0,
                        width: 20,
                        height: 20
                      }}
                    />
                  </Popconfirm>
                </Space>
              </div>

              {/* 最后一条消息 */}
              <Text
                style={{
                  fontSize: 12,
                  color: '#6b7280',
                  display: 'block',
                  marginBottom: 4
                }}
                ellipsis={{ tooltip: conversation.lastMessage }}
              >
                {conversation.lastMessage}
              </Text>

              {/* 时间和消息数量 */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <Space size={4}>
                  <ClockCircleOutlined style={{ fontSize: 10, color: '#9ca3af' }} />
                  <Text style={{ fontSize: 10, color: '#9ca3af' }}>
                    {formatTime(conversation.timestamp)}
                  </Text>
                </Space>
                <Text style={{ fontSize: 10, color: '#9ca3af' }}>
                  {conversation.messageCount} 条消息
                </Text>
              </div>
            </div>
          </List.Item>
        )}
      />

      {filteredConversations.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '40px 20px',
          color: '#9ca3af'
        }}>
          <HistoryOutlined style={{ fontSize: 32, marginBottom: 8 }} />
          <div>
            {searchText ? '没有找到匹配的对话' : '暂无对话历史'}
          </div>
        </div>
      )}
    </Drawer>
  );
};

export default ConversationHistory;
