import React, { useState, useRef, useEffect } from 'react';
import {
  Layout,
  Card,
  Button,
  Input,
  Space,
  Typography,
  Steps,
  message,
  Spin,
  Row,
  Col,
  Divider,
  Timeline,
  Badge,
  Progress,
  Alert,
  List,
  Tag,
  Tooltip
} from 'antd';
import {
  SendOutlined,
  ReloadOutlined,
  RobotOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  UploadOutlined,
  BulbOutlined,
  DownloadOutlined,
  CopyOutlined,
  EditOutlined
} from '@ant-design/icons';
import type { UploadFile } from 'antd';

import FileUpload from '@/components/FileUpload';
import AgentMessage from '@/components/AgentMessage';
import PageLayout from '@/components/PageLayout';
import {
  generateTestCaseStream,
  uploadFiles,
  convertFilesToUploads,
  TestCaseRequest,
  AgentMessage as APIAgentMessage,
  TestCaseStreamChunk
} from '@/services/testcase';

const { Content } = Layout;
const { TextArea } = Input;
const { Title, Text } = Typography;
const { Step } = Steps;

interface AgentMessageData {
  id: string;
  content: string;
  agentType: 'requirement_agent' | 'testcase_agent' | 'user_proxy';
  agentName: string;
  timestamp: string;
  roundNumber: number;
}

interface TestCase {
  id: string;
  title: string;
  description: string;
  steps: string[];
  expectedResult: string;
  priority: 'high' | 'medium' | 'low';
  category: string;
}

const TestCasePage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [conversationId, setConversationId] = useState<string>('');
  const [roundNumber, setRoundNumber] = useState(1);
  const [textContent, setTextContent] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<UploadFile[]>([]);
  const [agentMessages, setAgentMessages] = useState<AgentMessageData[]>([]);
  const [userFeedback, setUserFeedback] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [generatedTestCases, setGeneratedTestCases] = useState<TestCase[]>([]);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const maxRounds = 3;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [agentMessages]);

  const handleFilesChange = (files: UploadFile[]) => {
    setSelectedFiles(files);
    // 当有文件上传时，自动激活第一步
    if (files.length > 0 && currentStep === 0) {
      setCurrentStep(0);
    }
  };

  const generateTestCase = async () => {
    if (!textContent.trim() && selectedFiles.length === 0) {
      message.warning('请输入文本内容或上传文件');
      return;
    }

    setLoading(true);
    setCurrentStep(1);
    setAgentMessages([]);
    setAnalysisProgress(0);

    // 进度更新函数
    const updateProgress = (progress: number) => {
      setAnalysisProgress(progress);
    };

    try {
      let uploadedConversationId = conversationId;

      // 如果有文件，先上传文件
      if (selectedFiles.length > 0) {
        updateProgress(10);
        const files = selectedFiles.map(file => file.originFileObj as File).filter(Boolean);

        const uploadResult = await uploadFiles(files, textContent, conversationId);
        uploadedConversationId = uploadResult.conversation_id;
        setConversationId(uploadedConversationId);

        message.success(`成功上传 ${files.length} 个文件`);
        updateProgress(30);
      }

      // 准备请求数据
      const fileUploads = selectedFiles.length > 0
        ? await convertFilesToUploads(selectedFiles.map(file => file.originFileObj as File).filter(Boolean))
        : undefined;

      const request: TestCaseRequest = {
        conversation_id: uploadedConversationId,
        files: fileUploads,
        text_content: textContent.trim() || undefined,
        round_number: roundNumber
      };

      updateProgress(40);

      // 使用流式API生成测试用例
      await generateTestCaseStream(
        request,
        (chunk: TestCaseStreamChunk) => {
          // 处理流式响应
          const newMessage: AgentMessageData = {
            id: Date.now().toString() + Math.random(),
            content: chunk.content,
            agentType: chunk.agent_type,
            agentName: chunk.agent_name,
            timestamp: chunk.timestamp || new Date().toISOString(),
            roundNumber: chunk.round_number
          };

          setAgentMessages(prev => [...prev, newMessage]);
          setConversationId(chunk.conversation_id);

          // 更新进度
          updateProgress(Math.min(90, 40 + (agentMessages.length * 10)));

          if (chunk.is_complete) {
            setCurrentStep(2);
            setIsComplete(chunk.round_number >= 3);
            updateProgress(100);
            message.success('测试用例生成完成！');
          }
        },
        (error: Error) => {
          console.error('生成测试用例失败:', error);
          message.error(`生成测试用例失败: ${error.message}`);
          setCurrentStep(0);
        },
        () => {
          updateProgress(100);
          setCurrentStep(2);
        }
      );

    } catch (error: any) {
      console.error('生成测试用例失败:', error);
      message.error(`生成测试用例失败: ${error.message || '请重试'}`);
      setCurrentStep(0);
      updateProgress(0);
    } finally {
      setLoading(false);
    }
  };

  const submitFeedback = async () => {
    if (!userFeedback.trim()) {
      message.warning('请输入反馈内容');
      return;
    }

    if (roundNumber >= maxRounds) {
      message.warning('已达到最大交互轮次');
      return;
    }

    setLoading(true);

    try {
      // 使用API服务提交反馈
      const { submitFeedback: submitFeedbackAPI } = await import('@/services/testcase');

      const result = await submitFeedbackAPI(conversationId, userFeedback, roundNumber);

      if (result.max_rounds_reached) {
        message.info('已达到最大交互轮次');
        setIsComplete(true);
        setCurrentStep(3);
        setUserFeedback('');
        return;
      }

      // 使用反馈重新生成测试用例
      const request: TestCaseRequest = {
        conversation_id: conversationId,
        user_feedback: userFeedback,
        round_number: result.next_round
      };

      await generateTestCaseStream(
        request,
        (chunk: TestCaseStreamChunk) => {
          const newMessage: AgentMessageData = {
            id: Date.now().toString() + Math.random(),
            content: chunk.content,
            agentType: chunk.agent_type,
            agentName: chunk.agent_name,
            timestamp: chunk.timestamp || new Date().toISOString(),
            roundNumber: chunk.round_number
          };

          setAgentMessages(prev => [...prev, newMessage]);

          if (chunk.is_complete) {
            setIsComplete(chunk.round_number >= maxRounds);
            setCurrentStep(chunk.round_number >= maxRounds ? 3 : 2);
            setRoundNumber(chunk.round_number);
          }
        },
        (error: Error) => {
          console.error('处理反馈失败:', error);
          message.error(`处理反馈失败: ${error.message}`);
        }
      );

      setUserFeedback('');
      message.success('反馈提交成功，正在生成改进的测试用例...');
    } catch (error) {
      console.error('提交反馈失败:', error);
      message.error('提交反馈失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const resetConversation = () => {
    setAgentMessages([]);
    setConversationId('');
    setRoundNumber(1);
    setCurrentStep(0);
    setTextContent('');
    setSelectedFiles([]);
    setUserFeedback('');
    setIsComplete(false);
    setGeneratedTestCases([]);
    setAnalysisProgress(0);
    message.info('已重置对话');
  };

  return (
    <PageLayout background="#f8f9fa">
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        {/* 页面标题 */}
        <div style={{
          background: 'white',
          padding: '20px 24px',
          borderBottom: '1px solid #f0f0f0',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
        }}>
          <Row align="middle" justify="space-between">
            <Col>
              <Space size="large">
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 20,
                  fontWeight: 'bold',
                }}>
                  AI
                </div>
                <div>
                  <Title level={3} style={{ margin: 0, color: '#262626' }}>
                    需求分析
                  </Title>
                  <Text type="secondary">智能分析需求文档，自动生成专业测试用例</Text>
                </div>
              </Space>
            </Col>
            <Col>
              <Button
                icon={<ReloadOutlined />}
                onClick={resetConversation}
                disabled={loading}
                size="large"
              >
                重新开始
              </Button>
            </Col>
          </Row>
        </div>

        {/* 主要内容区域 */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* 左侧步骤和操作区域 */}
          <div style={{
            width: 400,
            background: 'white',
            borderRight: '1px solid #f0f0f0',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* 步骤指示器 */}
            <div style={{ padding: '24px 24px 0' }}>
              <div style={{ marginBottom: 24 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 16,
                  fontSize: 16,
                  fontWeight: 600,
                  color: '#262626'
                }}>
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: currentStep >= 0 ? '#52c41a' : '#d9d9d9',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    fontWeight: 'bold',
                    marginRight: 12
                  }}>
                    1
                  </div>
                  导入需求文档
                </div>
                <div style={{ marginLeft: 36, color: '#8c8c8c', fontSize: 14 }}>
                  上传需求相关文档资料，填写关键信息
                </div>
              </div>
              <div style={{ marginBottom: 24 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 16,
                  fontSize: 16,
                  fontWeight: 600,
                  color: '#262626'
                }}>
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: currentStep >= 1 ? '#52c41a' : '#d9d9d9',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    fontWeight: 'bold',
                    marginRight: 12
                  }}>
                    2
                  </div>
                  输入分析重点
                </div>
                <div style={{ marginLeft: 36, color: '#8c8c8c', fontSize: 14 }}>
                  描述您希望重点关注的测试内容、功能要求、性能要求等
                </div>
              </div>

              <div style={{ marginBottom: 24 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 16,
                  fontSize: 16,
                  fontWeight: 600,
                  color: '#262626'
                }}>
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: currentStep >= 2 ? '#52c41a' : '#d9d9d9',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    fontWeight: 'bold',
                    marginRight: 12
                  }}>
                    3
                  </div>
                  开始智能分析
                </div>
                <div style={{ marginLeft: 36, color: '#8c8c8c', fontSize: 14 }}>
                  根据文档和需求进行智能分析，生成测试结果
                </div>
              </div>
            </div>

            {/* 分隔线 */}
            <Divider style={{ margin: '0 24px 24px' }} />

            {/* 输入区域 */}
            <div style={{ flex: 1, padding: '0 24px', overflow: 'auto' }}>
              {/* 第一步：导入需求文档 */}
              <div style={{ marginBottom: 32 }}>
                <div style={{
                  background: currentStep >= 0 ? '#f6ffed' : '#fafafa',
                  border: `1px solid ${currentStep >= 0 ? '#b7eb8f' : '#d9d9d9'}`,
                  borderRadius: 8,
                  padding: 16
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: 12,
                    color: currentStep >= 0 ? '#52c41a' : '#8c8c8c'
                  }}>
                    <UploadOutlined style={{ marginRight: 8 }} />
                    <Text strong style={{ color: 'inherit' }}>导入需求文档</Text>
                  </div>

                  <div style={{ marginBottom: 16 }}>
                    <FileUpload onFilesChange={handleFilesChange} />
                  </div>

                  <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                    支持格式：PDF、Word、Excel、TXT等，最大5个文件
                  </div>
                </div>
              </div>

              {/* 第二步：输入分析重点 */}
              <div style={{ marginBottom: 32 }}>
                <div style={{
                  background: currentStep >= 1 ? '#f6ffed' : '#fafafa',
                  border: `1px solid ${currentStep >= 1 ? '#b7eb8f' : '#d9d9d9'}`,
                  borderRadius: 8,
                  padding: 16
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: 12,
                    color: currentStep >= 1 ? '#52c41a' : '#8c8c8c'
                  }}>
                    <EditOutlined style={{ marginRight: 8 }} />
                    <Text strong style={{ color: 'inherit' }}>输入分析重点</Text>
                  </div>

                  <TextArea
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    placeholder="请描述您希望重点关注的测试内容、功能要求、性能要求等..."
                    rows={4}
                    disabled={loading}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      resize: 'none'
                    }}
                  />
                </div>
              </div>

              {/* 第三步：开始分析 */}
              <div style={{ marginBottom: 32 }}>
                <div style={{
                  background: currentStep >= 2 ? '#f6ffed' : '#fafafa',
                  border: `1px solid ${currentStep >= 2 ? '#b7eb8f' : '#d9d9d9'}`,
                  borderRadius: 8,
                  padding: 16
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: 12,
                    color: currentStep >= 2 ? '#52c41a' : '#8c8c8c'
                  }}>
                    <BulbOutlined style={{ marginRight: 8 }} />
                    <Text strong style={{ color: 'inherit' }}>AI智能分析</Text>
                  </div>

                  {loading && (
                    <div style={{ marginBottom: 16 }}>
                      <Progress
                        percent={analysisProgress}
                        size="small"
                        status="active"
                        strokeColor={{
                          '0%': '#667eea',
                          '100%': '#764ba2',
                        }}
                      />
                      <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 8 }}>
                        正在分析需求文档，生成测试用例...
                      </div>
                    </div>
                  )}

                  {currentStep === 0 && (
                    <Button
                      type="primary"
                      icon={<BulbOutlined />}
                      onClick={generateTestCase}
                      loading={loading}
                      size="large"
                      disabled={!textContent.trim() && selectedFiles.length === 0}
                      style={{
                        width: '100%',
                        height: 48,
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        borderRadius: 8,
                        fontSize: 16,
                        fontWeight: 600
                      }}
                    >
                      AI智能分析
                    </Button>
                  )}
                </div>
              </div>
            </div>

          </div>

          {/* 右侧测试用例展示区域 */}
          <div style={{ flex: 1, background: '#f8f9fa', display: 'flex', flexDirection: 'column' }}>
            {/* 标题栏 */}
            <div style={{
              background: 'white',
              padding: '20px 24px',
              borderBottom: '1px solid #f0f0f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <Title level={4} style={{ margin: 0, color: '#262626' }}>
                  AI分析结果表
                </Title>
                <Text type="secondary">根据需求内容生成的测试用例</Text>
              </div>

              {generatedTestCases.length > 0 && (
                <Space>
                  <Button icon={<DownloadOutlined />} type="text">
                    导出
                  </Button>
                  <Button icon={<CopyOutlined />} type="text">
                    复制
                  </Button>
                </Space>
              )}
            </div>

            {/* 内容区域 */}
            <div style={{ flex: 1, padding: 24, overflow: 'auto' }}>
              {agentMessages.length === 0 ? (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: '#8c8c8c'
                }}>
                  <div style={{
                    width: 120,
                    height: 120,
                    borderRadius: '50%',
                    background: '#f5f5f5',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 24
                  }}>
                    <FileTextOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                  </div>
                  <Title level={4} style={{ color: '#8c8c8c', margin: 0 }}>
                    等待分析结果
                  </Title>
                  <Text type="secondary" style={{ marginTop: 8 }}>
                    请先上传需求文档并开始AI分析
                  </Text>
                </div>
              ) : (
                <div>
                  {/* AI生成的消息列表 */}
                  <div style={{ marginBottom: 24 }}>
                    {agentMessages.map((msg, index) => (
                      <div key={msg.id} style={{ marginBottom: 24 }}>
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          marginBottom: 12,
                          padding: '8px 12px',
                          background: msg.agentType === 'requirement_agent' ? '#e6f7ff' : '#f6ffed',
                          borderRadius: 6,
                          border: `1px solid ${msg.agentType === 'requirement_agent' ? '#91d5ff' : '#b7eb8f'}`
                        }}>
                          <RobotOutlined style={{
                            color: msg.agentType === 'requirement_agent' ? '#1890ff' : '#52c41a',
                            marginRight: 8
                          }} />
                          <Text strong style={{
                            color: msg.agentType === 'requirement_agent' ? '#1890ff' : '#52c41a'
                          }}>
                            {msg.agentName === 'requirement_analyst' ? '需求分析师' : '测试用例生成器'}
                          </Text>
                          <Tag
                            color={msg.agentType === 'requirement_agent' ? 'blue' : 'green'}
                            style={{ marginLeft: 'auto' }}
                          >
                            第 {msg.roundNumber} 轮
                          </Tag>
                        </div>

                        <div style={{
                          marginLeft: 0,
                          padding: 16,
                          background: 'white',
                          borderRadius: 8,
                          border: '1px solid #f0f0f0',
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.6
                        }}>
                          <AgentMessage
                            agentType={msg.agentType}
                            agentName={msg.agentName}
                            content={msg.content}
                            timestamp={msg.timestamp}
                            roundNumber={msg.roundNumber}
                            isExpanded={true}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* 用户反馈区域 */}
                  {currentStep === 2 && !isComplete && (
                    <div style={{
                      background: 'white',
                      padding: 20,
                      borderRadius: 8,
                      border: '1px solid #f0f0f0',
                      marginTop: 24
                    }}>
                      <div style={{ marginBottom: 12 }}>
                        <Text strong>反馈意见 (第 {roundNumber}/{maxRounds} 轮)</Text>
                      </div>
                      <TextArea
                        value={userFeedback}
                        onChange={(e) => setUserFeedback(e.target.value)}
                        placeholder="请提出您的修改意见..."
                        rows={3}
                        disabled={loading}
                        style={{ marginBottom: 12 }}
                      />
                      <Button
                        type="primary"
                        icon={<SendOutlined />}
                        onClick={submitFeedback}
                        loading={loading}
                        disabled={!userFeedback.trim()}
                        style={{
                          background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
                          border: 'none',
                          borderRadius: 6
                        }}
                      >
                        提交反馈
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  );
};

export default TestCasePage;
