import React, { useState } from 'react';
import { Card, Avatar, Typography, Tag, Collapse, Space, Button } from 'antd';
import {
  RobotOutlined,
  UserOutlined,
  ClockCircleOutlined,
  DownOutlined,
  UpOutlined,
  CopyOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { message } from 'antd';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface AgentMessageProps {
  agentType: 'requirement_agent' | 'testcase_agent' | 'user_proxy';
  agentName: string;
  content: string;
  timestamp: string;
  roundNumber: number;
  isExpanded?: boolean;
}

const AgentMessage: React.FC<AgentMessageProps> = ({
  agentType,
  agentName,
  content,
  timestamp,
  roundNumber,
  isExpanded = false
}) => {
  const [expanded, setExpanded] = useState(isExpanded);

  const getAgentConfig = (type: string) => {
    switch (type) {
      case 'requirement_agent':
        return {
          name: '需求分析师',
          color: '#1890ff',
          bgColor: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          icon: <RobotOutlined />,
          description: '负责分析用户需求，提取核心功能点'
        };
      case 'testcase_agent':
        return {
          name: '测试用例专家',
          color: '#52c41a',
          bgColor: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
          icon: <RobotOutlined />,
          description: '基于需求生成专业的测试用例'
        };
      case 'user_proxy':
        return {
          name: '用户代理',
          color: '#722ed1',
          bgColor: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          icon: <UserOutlined />,
          description: '处理用户反馈和交互'
        };
      default:
        return {
          name: '智能体',
          color: '#666',
          bgColor: 'linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)',
          icon: <RobotOutlined />,
          description: '智能体助手'
        };
    }
  };

  const agentConfig = getAgentConfig(agentType);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(content);
      message.success('内容已复制到剪贴板');
    } catch (err) {
      message.error('复制失败');
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <div className="agent-message-container" style={{ marginBottom: 16 }}>
      <Card
        style={{
          borderRadius: 16,
          overflow: 'hidden',
          border: 'none',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          background: 'white'
        }}
      >
        {/* 智能体头部 */}
        <div
          style={{
            background: agentConfig.bgColor,
            margin: '-24px -24px 16px -24px',
            padding: '16px 24px',
            color: 'white'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Space>
              <Avatar
                icon={agentConfig.icon}
                style={{
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  color: 'white',
                  border: '2px solid rgba(255,255,255,0.3)'
                }}
                size="large"
              />
              <div>
                <Title level={5} style={{ color: 'white', margin: 0 }}>
                  {agentConfig.name}
                </Title>
                <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 12 }}>
                  {agentConfig.description}
                </Text>
              </div>
            </Space>

            <Space>
              <Tag color="rgba(255,255,255,0.2)" style={{ color: 'white', border: 'none' }}>
                第 {roundNumber} 轮
              </Tag>
              <Button
                type="text"
                icon={expanded ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setExpanded(!expanded)}
                style={{ color: 'white' }}
                size="small"
              />
            </Space>
          </div>
        </div>

        {/* 时间戳 */}
        <div style={{ marginBottom: 12 }}>
          <Space>
            <ClockCircleOutlined style={{ color: '#666' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {formatTimestamp(timestamp)}
            </Text>
            <Button
              type="text"
              icon={<CopyOutlined />}
              size="small"
              onClick={copyToClipboard}
              style={{ marginLeft: 'auto' }}
            >
              复制
            </Button>
          </Space>
        </div>

        {/* 消息内容 */}
        <Collapse
          ghost
          activeKey={expanded ? ['content'] : []}
          onChange={() => setExpanded(!expanded)}
        >
          <Panel
            header={
              <Text strong style={{ color: agentConfig.color }}>
                {expanded ? '收起内容' : '展开查看详细内容'}
              </Text>
            }
            key="content"
            showArrow={false}
          >
            <div
              style={{
                maxHeight: '400px',
                overflowY: 'auto',
                padding: '16px',
                background: '#fafafa',
                borderRadius: 8,
                border: '1px solid #f0f0f0'
              }}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th style={{
                      border: '1px solid #d9d9d9',
                      padding: '8px 12px',
                      background: '#fafafa',
                      fontWeight: 'bold',
                      textAlign: 'left'
                    }}>
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td style={{
                      border: '1px solid #d9d9d9',
                      padding: '8px 12px'
                    }}>
                      {children}
                    </td>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className;
                    return (
                      <code
                        style={{
                          background: isInline ? '#f5f5f5' : '#f0f0f0',
                          padding: isInline ? '2px 4px' : '8px 12px',
                          borderRadius: 4,
                          fontSize: '0.9em',
                          fontFamily: 'Monaco, Consolas, monospace',
                          display: isInline ? 'inline' : 'block',
                          whiteSpace: isInline ? 'nowrap' : 'pre-wrap'
                        }}
                      >
                        {children}
                      </code>
                    );
                  },
                  h1: ({ children }) => (
                    <h1 style={{ color: agentConfig.color, borderBottom: `2px solid ${agentConfig.color}`, paddingBottom: 8 }}>
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 style={{ color: agentConfig.color, marginTop: 24, marginBottom: 12 }}>
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 style={{ color: agentConfig.color, marginTop: 20, marginBottom: 10 }}>
                      {children}
                    </h3>
                  )
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          </Panel>
        </Collapse>
      </Card>

      <style jsx>{`
        .agent-message-container .ant-collapse-content-box {
          padding: 0 !important;
        }

        .agent-message-container .ant-collapse-header {
          padding: 0 !important;
        }

        .agent-message-container .ant-collapse-item {
          border: none !important;
        }
      `}</style>
    </div>
  );
};

export default AgentMessage;
