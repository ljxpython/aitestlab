/**
 * 请求模块使用示例
 */

import React, { useState } from 'react';
import { Button, Card, Input, Space, Typography, Alert, Spin } from 'antd';
import {
  request,
  TestCaseAPI,
  useTestCaseGeneration,
  useChat,
  TestCaseRequest,
  StreamResponse,
} from '../api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const RequestExample: React.FC = () => {
  const [textContent, setTextContent] = useState('');
  const [chatInput, setChatInput] = useState('');

  // 测试用例生成Hook
  const {
    messages: testCaseMessages,
    loading: testCaseLoading,
    error: testCaseError,
    generate: generateTestCase,
    stop: stopTestCase,
    clear: clearTestCase,
  } = useTestCaseGeneration();

  // 聊天Hook
  const {
    messages: chatMessages,
    loading: chatLoading,
    error: chatError,
    send: sendChatMessage,
    stop: stopChat,
    clear: clearChat,
  } = useChat();

  /**
   * 普通HTTP请求示例
   */
  const handleNormalRequest = async () => {
    try {
      const data: TestCaseRequest = {
        text_content: textContent,
        round_number: 1,
      };

      const response = await TestCaseAPI.generate(data);
      console.log('普通请求响应:', response);
      alert(`请求成功: ${response.message}`);
    } catch (error) {
      console.error('普通请求失败:', error);
      alert(`请求失败: ${error}`);
    }
  };

  /**
   * SSE流式请求示例
   */
  const handleSSERequest = async () => {
    if (!textContent.trim()) {
      alert('请输入内容');
      return;
    }

    const data: TestCaseRequest = {
      text_content: textContent,
      round_number: 1,
    };

    await generateTestCase(data);
  };

  /**
   * 聊天请求示例
   */
  const handleChatRequest = async () => {
    if (!chatInput.trim()) {
      alert('请输入聊天内容');
      return;
    }

    await sendChatMessage(chatInput);
    setChatInput('');
  };

  /**
   * 文件上传示例
   */
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const response = await request.upload('/file/upload', file);
      console.log('文件上传响应:', response);
      alert(`上传成功: ${response.message}`);
    } catch (error) {
      console.error('文件上传失败:', error);
      alert(`上传失败: ${error}`);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>请求模块使用示例</Title>

      {/* 普通HTTP请求示例 */}
      <Card title="1. 普通HTTP请求" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea
            placeholder="请输入测试内容"
            value={textContent}
            onChange={(e) => setTextContent(e.target.value)}
            rows={4}
          />
          <Button type="primary" onClick={handleNormalRequest}>
            发送普通请求
          </Button>
        </Space>
      </Card>

      {/* SSE流式请求示例 */}
      <Card title="2. SSE流式请求" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea
            placeholder="请输入测试用例需求"
            value={textContent}
            onChange={(e) => setTextContent(e.target.value)}
            rows={4}
          />
          <Space>
            <Button
              type="primary"
              onClick={handleSSERequest}
              loading={testCaseLoading}
              disabled={testCaseLoading}
            >
              {testCaseLoading ? '生成中...' : '开始SSE流式生成'}
            </Button>
            <Button onClick={stopTestCase} disabled={!testCaseLoading}>
              停止生成
            </Button>
            <Button onClick={clearTestCase}>
              清空结果
            </Button>
          </Space>

          {testCaseError && (
            <Alert message="错误" description={testCaseError} type="error" showIcon />
          )}

          {testCaseLoading && (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin size="large" />
              <div style={{ marginTop: '10px' }}>正在生成测试用例...</div>
            </div>
          )}

          {testCaseMessages.length > 0 && (
            <div>
              <Title level={4}>SSE流式响应结果:</Title>
              {testCaseMessages.map((message: StreamResponse, index) => (
                <Card
                  key={index}
                  size="small"
                  style={{ marginBottom: '8px' }}
                  title={`${message.agent_name} (${message.source})`}
                >
                  <Paragraph>
                    <Text code>{message.content}</Text>
                  </Paragraph>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    时间: {message.timestamp} | 完成: {message.is_complete ? '是' : '否'}
                  </Text>
                </Card>
              ))}
            </div>
          )}
        </Space>
      </Card>

      {/* 聊天请求示例 */}
      <Card title="3. 聊天SSE请求" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div style={{ height: '300px', overflowY: 'auto', border: '1px solid #d9d9d9', padding: '12px' }}>
            {chatMessages.map((message, index) => (
              <div key={index} style={{ marginBottom: '12px' }}>
                <Text strong>{message.role === 'user' ? '用户' : 'AI'}:</Text>
                <div style={{ marginLeft: '8px' }}>{message.content}</div>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {new Date(message.timestamp).toLocaleString()}
                </Text>
              </div>
            ))}
            {chatLoading && (
              <div style={{ textAlign: 'center' }}>
                <Spin /> AI正在思考...
              </div>
            )}
          </div>

          {chatError && (
            <Alert message="聊天错误" description={chatError} type="error" showIcon />
          )}

          <Space style={{ width: '100%' }}>
            <Input
              placeholder="请输入聊天内容"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onPressEnter={handleChatRequest}
              style={{ flex: 1 }}
              disabled={chatLoading}
            />
            <Button
              type="primary"
              onClick={handleChatRequest}
              loading={chatLoading}
              disabled={chatLoading || !chatInput.trim()}
            >
              发送
            </Button>
            <Button onClick={stopChat} disabled={!chatLoading}>
              停止
            </Button>
            <Button onClick={clearChat}>
              清空
            </Button>
          </Space>
        </Space>
      </Card>

      {/* 文件上传示例 */}
      <Card title="4. 文件上传" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <input
            type="file"
            onChange={handleFileUpload}
            accept=".txt,.pdf,.doc,.docx"
          />
          <Text type="secondary">
            支持上传 .txt, .pdf, .doc, .docx 格式文件
          </Text>
        </Space>
      </Card>

      {/* 使用说明 */}
      <Card title="使用说明">
        <Space direction="vertical">
          <Paragraph>
            <Title level={4}>1. 普通HTTP请求</Title>
            使用 <Text code>request.get/post/put/delete</Text> 方法发送普通HTTP请求
          </Paragraph>

          <Paragraph>
            <Title level={4}>2. SSE流式请求</Title>
            使用 <Text code>useSSE</Text> Hook 或具体的业务Hook如 <Text code>useTestCaseGeneration</Text>
          </Paragraph>

          <Paragraph>
            <Title level={4}>3. 文件上传</Title>
            使用 <Text code>request.upload</Text> 方法上传文件
          </Paragraph>

          <Paragraph>
            <Title level={4}>4. 错误处理</Title>
            所有请求都有统一的错误处理机制，会自动显示错误信息
          </Paragraph>
        </Space>
      </Card>
    </div>
  );
};

export default RequestExample;
