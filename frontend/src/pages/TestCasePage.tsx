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
import MarkdownRenderer from '@/components/MarkdownRenderer';

const { Content } = Layout;
const { TextArea } = Input;
const { Title, Text } = Typography;
const { Step } = Steps;

// 简单的类型定义
interface AgentMessageData {
  id: string;
  content: string;
  agentType: string;
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

// SSE消息类型 - 根据后端接口重新定义
interface SSEMessage {
  type?: string; // 消息类型: 'text_message', 'streaming_chunk', 'task_result', 'error'
  source?: string; // 消息来源: '需求分析智能体', '测试用例生成智能体'等
  content: string; // 消息内容
  conversation_id?: string; // 对话ID
  message_type?: string; // 业务类型: '用户需求', '文档解析结果', '需求分析', '测试用例生成', 'streaming_chunk'
  timestamp?: string; // 时间戳
  is_final?: boolean; // 是否最终消息
  is_complete?: boolean; // 是否完成（兼容性）
}

// 根据智能体名称获取类型
const getAgentTypeFromSource = (source: string): 'requirement_agent' | 'testcase_agent' | 'user_proxy' => {
  if (source.includes('需求分析智能体')) {
    return 'requirement_agent';
  } else if (source.includes('测试用例生成智能体') || source.includes('用例评审优化智能体') || source.includes('结构化入库智能体')) {
    return 'testcase_agent';
  } else {
    return 'user_proxy';
  }
};

const TestCasePage: React.FC = () => {
  // 简化的状态管理
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [currentAgent, setCurrentAgent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [agentStreamingMap, setAgentStreamingMap] = useState<Record<string, string>>({});

  // 基础状态
  const [currentStep, setCurrentStep] = useState(0);
  const [conversationId, setConversationId] = useState<string>('');
  const [roundNumber, setRoundNumber] = useState(1);
  const [textContent, setTextContent] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<UploadFile[]>([]);
  const [agentMessages, setAgentMessages] = useState<AgentMessageData[]>([]);
  const [userFeedback, setUserFeedback] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const maxRounds = 3;

  // 智能体显示相关的辅助函数
  const getAgentDisplayName = (agentType: string, agentName: string): string => {
    // 根据智能体名称或类型返回简洁的显示名称
    if (agentName.includes('需求分析') || agentType === 'requirement_agent') {
      return '需求分析师';
    } else if (agentName.includes('测试用例') || agentName.includes('优化') || agentName.includes('结构化') || agentType === 'testcase_agent') {
      return '测试用例专家';
    } else if (agentName.includes('用户') || agentType === 'user_proxy') {
      return '用户代理';
    } else {
      // 特殊命名的智能体
      switch (agentName) {
        case 'testcase_generator':
          return '测试用例专家';
        case 'requirement_analyst':
          return '需求分析师';
        case 'feedback_processor':
          return '反馈处理器';
        case 'system':
          return '系统';
        default:
          return '智能助手';
      }
    }
  };

  // 获取简化的智能体显示名称（用于流式输出）
  const getSimplifiedAgentName = (agentName: string): string => {
    if (agentName.includes('需求分析智能体')) {
      return '需求分析师';
    } else if (agentName.includes('测试用例生成智能体')) {
      return '测试用例专家';
    } else if (agentName.includes('用例评审优化智能体')) {
      return '测试用例专家';
    } else if (agentName.includes('结构化入库智能体')) {
      return '测试用例专家';
    } else {
      return getAgentDisplayName(getAgentTypeFromSource(agentName), agentName);
    }
  };

  // 判断是否应该显示流式输出（避免冗余显示）
  const shouldShowStreamingOutput = (agentName: string): boolean => {
    // 只显示主要的智能体流式输出
    return agentName.includes('需求分析智能体') ||
           agentName.includes('测试用例生成智能体') ||
           agentName.includes('用例评审优化智能体') ||
           agentName.includes('结构化入库智能体');
  };

  // 判断是否应该在消息列表中显示（避免重复显示）
  const shouldShowInMessageList = (agentName: string): boolean => {
    // 过滤掉一些中间步骤的智能体，只显示有价值的结果
    return !agentName.includes('结果收集') &&
           !agentName.includes('消息收集') &&
           !agentName.includes('流式生成');
  };

  const getAgentColor = (agentType: string, agentName: string): string => {
    switch (agentName) {
      case 'testcase_generator':
        return '#52c41a';
      case 'user_proxy':
        return '#1890ff';
      case 'requirement_analyst':
        return '#722ed1';
      case 'feedback_processor':
        return '#fa8c16';
      case 'system':
        return '#8c8c8c';
      default:
        switch (agentType) {
          case 'testcase_agent':
            return '#52c41a';
          case 'requirement_agent':
            return '#722ed1';
          case 'user_proxy':
            return '#1890ff';
          default:
            return '#8c8c8c';
        }
    }
  };

  const getAgentBackground = (agentType: string, agentName: string): string => {
    switch (agentName) {
      case 'testcase_generator':
        return '#f6ffed';
      case 'user_proxy':
        return '#e6f7ff';
      case 'requirement_analyst':
        return '#f9f0ff';
      case 'system':
        return '#f5f5f5';
      default:
        switch (agentType) {
          case 'testcase_agent':
            return '#f6ffed';
          case 'requirement_agent':
            return '#f9f0ff';
          case 'user_proxy':
            return '#e6f7ff';
          default:
            return '#f5f5f5';
        }
    }
  };

  const getAgentBorderColor = (agentType: string, agentName: string): string => {
    switch (agentName) {
      case 'testcase_generator':
        return '#b7eb8f';
      case 'user_proxy':
        return '#91d5ff';
      case 'requirement_analyst':
        return '#d3adf7';
      case 'system':
        return '#d9d9d9';
      default:
        switch (agentType) {
          case 'testcase_agent':
            return '#b7eb8f';
          case 'requirement_agent':
            return '#d3adf7';
          case 'user_proxy':
            return '#91d5ff';
          default:
            return '#d9d9d9';
        }
    }
  };

  const getAgentTagColor = (agentType: string, agentName: string): string => {
    switch (agentName) {
      case 'testcase_generator':
        return 'green';
      case 'user_proxy':
        return 'blue';
      case 'requirement_analyst':
        return 'purple';
      case 'system':
        return 'default';
      default:
        switch (agentType) {
          case 'testcase_agent':
            return 'green';
          case 'requirement_agent':
            return 'purple';
          case 'user_proxy':
            return 'blue';
          default:
            return 'default';
        }
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 移除Hook依赖的useEffect，现在直接在SSE处理中更新状态

  // 处理错误
  useEffect(() => {
    if (streamError) {
      message.error(`生成失败: ${streamError}`);
      setAnalysisProgress(0);
    }
  }, [streamError]);

  useEffect(() => {
    scrollToBottom();
  }, [agentMessages]);

  // 监控流式状态变化
  useEffect(() => {
    console.log('🔥 流式状态变化:', {
      currentAgent,
      streamingContentLength: streamingContent.length,
      streamingContent: streamingContent.substring(0, 50) + '...',
      shouldShowStreaming: !!currentAgent,
      streamingContentExists: !!streamingContent
    });
  }, [currentAgent, streamingContent]);

  const handleFilesChange = (files: UploadFile[]) => {
    setSelectedFiles(files);
    // 当有文件上传时，自动激活第一步
    if (files.length > 0 && currentStep === 0) {
      setCurrentStep(0);
    }
  };

  // 辅助函数：根据智能体来源获取智能体类型（保留，用于兼容性）
  const getAgentTypeFromSource = (source: string): AgentType => {
    if (source.includes('需求分析')) return 'requirement_agent';
    if (source.includes('测试用例生成')) return 'testcase_agent';
    if (source.includes('评审') || source.includes('优化')) return 'review_agent';
    if (source.includes('存储') || source.includes('数据库')) return 'storage_agent';
    return 'testcase_agent'; // 默认类型
  };

  // SSE处理函数 - 根据后端接口重新实现
  const processSSEStream = async (reader: ReadableStreamDefaultReader<Uint8Array>) => {
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        console.log('✅ SSE流处理完成');
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data: SSEMessage = JSON.parse(line.slice(6));
            console.log('📤 收到SSE消息:', {
              type: data.type,
              message_type: data.message_type,
              source: data.source,
              content_length: data.content?.length,
              is_final: data.is_final
            });

            // 更新conversation_id（如果还没有设置）
            if (data.conversation_id && !conversationId) {
              console.log('📋 设置conversation_id:', data.conversation_id);
              setConversationId(data.conversation_id);
            }

            // 根据后端接口逻辑处理不同类型的消息
            if (data.type === 'text_message') {
              // 处理text_message类型的消息
              console.log('📝 处理text_message:', data.message_type, data.source);

              if (data.message_type === '用户需求') {
                // 用户模块: 用户需求
                console.log('👤 处理用户需求消息');
                const userMessage: AgentMessageData = {
                  id: `user_requirement_${Date.now()}_${Math.random()}`,
                  content: data.content,
                  agentType: 'user_proxy',
                  agentName: '用户模块',
                  timestamp: data.timestamp || new Date().toISOString(),
                  roundNumber: roundNumber
                };
                setAgentMessages(prev => [...prev, userMessage]);

              } else if (data.message_type === '文档解析结果') {
                // 用户模块: 文档解析结果
                console.log('📄 处理文档解析结果消息');
                const docMessage: AgentMessageData = {
                  id: `doc_analysis_${Date.now()}_${Math.random()}`,
                  content: data.content,
                  agentType: 'user_proxy',
                  agentName: '用户模块',
                  timestamp: data.timestamp || new Date().toISOString(),
                  roundNumber: roundNumber
                };
                setAgentMessages(prev => [...prev, docMessage]);

              } else if (data.message_type === '需求分析') {
                // 需求分析智能体的完整输出
                console.log('🧠 处理需求分析完整消息');

                // 获取该智能体累积的流式内容
                const agentStreamContent = agentStreamingMap[data.source] || '';
                const finalContent = agentStreamContent.trim() || data.content;

                const analysisMessage: AgentMessageData = {
                  id: `requirement_analysis_${Date.now()}_${Math.random()}`,
                  content: finalContent,
                  agentType: 'requirement_agent',
                  agentName: '需求分析师',
                  timestamp: data.timestamp || new Date().toISOString(),
                  roundNumber: roundNumber
                };

                // 检查是否已经存在相同的消息（避免重复）
                setAgentMessages(prev => {
                  const existingIndex = prev.findIndex(msg =>
                    msg.agentType === 'requirement_agent' &&
                    msg.roundNumber === roundNumber &&
                    Math.abs(Date.now() - new Date(msg.timestamp).getTime()) < 10000
                  );

                  if (existingIndex >= 0) {
                    // 更新现有消息
                    const updated = [...prev];
                    updated[existingIndex] = { ...updated[existingIndex], content: finalContent };
                    console.log('📝 更新需求分析消息');
                    return updated;
                  } else {
                    // 添加新消息
                    console.log('📝 添加需求分析消息');
                    return [...prev, analysisMessage];
                  }
                });

                // 清理该智能体的流式内容
                setAgentStreamingMap(prev => {
                  const updated = { ...prev };
                  delete updated[data.source];
                  return updated;
                });

                // 清空流式显示
                if (currentAgent === '需求分析师') {
                  setStreamingContent('');
                  setCurrentAgent('');
                }

              } else if (data.message_type === '测试用例生成') {
                // 测试用例生成智能体的完整输出
                console.log('🧪 处理测试用例生成完整消息');

                // 获取该智能体累积的流式内容
                const agentStreamContent = agentStreamingMap[data.source] || '';
                const finalContent = agentStreamContent.trim() || data.content;

                const testcaseMessage: AgentMessageData = {
                  id: `testcase_generation_${Date.now()}_${Math.random()}`,
                  content: finalContent,
                  agentType: 'testcase_agent',
                  agentName: '测试用例专家',
                  timestamp: data.timestamp || new Date().toISOString(),
                  roundNumber: roundNumber
                };

                // 检查是否已经存在相同的消息（避免重复）
                setAgentMessages(prev => {
                  const existingIndex = prev.findIndex(msg =>
                    msg.agentType === 'testcase_agent' &&
                    msg.roundNumber === roundNumber &&
                    Math.abs(Date.now() - new Date(msg.timestamp).getTime()) < 10000
                  );

                  if (existingIndex >= 0) {
                    // 更新现有消息
                    const updated = [...prev];
                    updated[existingIndex] = { ...updated[existingIndex], content: finalContent };
                    console.log('📝 更新测试用例生成消息');
                    return updated;
                  } else {
                    // 添加新消息
                    console.log('📝 添加测试用例生成消息');
                    return [...prev, testcaseMessage];
                  }
                });

                // 清理该智能体的流式内容
                setAgentStreamingMap(prev => {
                  const updated = { ...prev };
                  delete updated[data.source];
                  return updated;
                });

                // 清空流式显示
                if (currentAgent === '测试用例专家') {
                  setStreamingContent('');
                  setCurrentAgent('');
                }

                // 标记完成
                setIsComplete(true);
                setCurrentStep(2);
                setAnalysisProgress(100);
                message.success('测试用例生成完成！');
              }

            } else if (data.message_type === 'streaming_chunk') {
              // 处理流式输出块
              console.log('🔥 处理streaming_chunk:', data.source);

              // 更新当前智能体的流式内容
              setAgentStreamingMap(prev => ({
                ...prev,
                [data.source]: (prev[data.source] || '') + data.content
              }));

              // 根据智能体来源显示流式输出
              if (data.source === '需求分析智能体') {
                setCurrentAgent('需求分析师');
                setStreamingContent(prev => prev + data.content);
                setAnalysisProgress(60);
              } else if (data.source === '测试用例生成智能体') {
                setCurrentAgent('测试用例专家');
                setStreamingContent(prev => prev + data.content);
                setAnalysisProgress(80);
              }

            } else if (data.type === 'task_result') {
              // 任务完成
              console.log('🏁 任务完成');
              setIsComplete(true);
              setCurrentStep(2);
              setAnalysisProgress(100);
              message.success('测试用例生成完成！');
              break;

            } else if (data.type === 'error') {
              // 错误处理
              console.error('❌ 收到错误消息:', data.content);
              setStreamError(data.content);
              message.error('生成过程中出现错误');
              break;
            }

          } catch (e) {
            console.error('❌ 解析SSE数据失败:', e, '原始行:', line);
          }
        }
      }
    }
  };

  const generateTestCase = async () => {
    if (!textContent.trim() && selectedFiles.length === 0) {
      message.warning('请输入文本内容或上传文件');
      return;
    }

    // 检查文件是否都已成功选择
    const hasUploadingFiles = selectedFiles.some(file => file.status === 'uploading');
    const hasFailedFiles = selectedFiles.some(file => file.status === 'error');

    if (hasUploadingFiles) {
      message.warning('请等待文件处理完成');
      return;
    }

    if (hasFailedFiles) {
      message.error('存在处理失败的文件，请重新选择');
      return;
    }

    setLoading(true);
    setCurrentStep(1);
    setAnalysisProgress(0);
    setStreamError(null);
    setStreamingContent('');
    setCurrentAgent('');
    setAgentMessages([]);
    setAgentStreamingMap({});

    try {
      // 步骤1: 先上传文件（如果有文件需要上传）
      let filePaths: string[] = [];

      if (selectedFiles.length > 0) {
        console.log('📁 开始上传文件:', selectedFiles.length, '个');

        // 准备FormData
        const formData = new FormData();
        formData.append('user_id', '1'); // 默认用户ID

        selectedFiles.forEach((file, index) => {
          if (file.originFileObj) {
            formData.append('files', file.originFileObj);
            console.log(`📄 添加文件 ${index + 1}:`, file.name);
          }
        });

        // 调用上传接口
        const uploadResponse = await fetch('/api/testcase/upload', {
          method: 'POST',
          body: formData,
        });

        if (!uploadResponse.ok) {
          throw new Error(`文件上传失败: ${uploadResponse.status}`);
        }

        const uploadResult = await uploadResponse.json();
        console.log('📁 文件上传成功:', uploadResult);

        // 提取文件路径
        filePaths = uploadResult.files?.map((file: any) => file.filePath) || [];
        console.log('📎 获得文件路径:', filePaths);
      }

      // 步骤2: 构建生成请求数据 - 使用文件路径而不是文件内容
      // 如果没有conversation_id，生成一个新的
      let currentConversationId = conversationId;
      if (!currentConversationId) {
        currentConversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        console.log('🆕 生成新的conversation_id:', currentConversationId);
        setConversationId(currentConversationId);
      }

      const requestData = {
        conversation_id: currentConversationId,
        text_content: textContent.trim() || "",
        file_paths: filePaths.length > 0 ? filePaths : null,  // 使用文件路径
        files: null,  // 不再使用文件内容
        round_number: roundNumber,
        enable_streaming: true
      };

      setAnalysisProgress(40);
      console.log('🚀 开始生成测试用例:', requestData);

      // 发送请求 - 与ChatPage对齐的处理方式
      const response = await fetch('/api/testcase/generate/streaming', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法获取响应流');
      }

      // 处理SSE流
      await processSSEStream(reader);

    } catch (error: any) {
      console.error('生成测试用例失败:', error);
      message.error(`生成测试用例失败: ${error.message || '请重试'}`);
      setCurrentStep(0);
      setAnalysisProgress(0);
      setStreamError(error.message || '网络请求失败');
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

    if (!conversationId) {
      message.error('没有有效的对话ID');
      return;
    }

    setLoading(true);
    setStreamError(null);
    setStreamingContent('');
    setCurrentAgent('');
    setAgentStreamingMap({});

    try {
      // 构建反馈数据 - 确保所有字段都符合后端模型要求
      const feedbackData = {
        conversation_id: conversationId,
        feedback: userFeedback.trim(),
        round_number: roundNumber,
        previous_testcases: agentMessages
          .filter(msg => msg.agentName.includes('测试用例') || msg.agentName.includes('优化'))
          .map(msg => msg.content)
          .join('\n\n') || ""  // 确保是字符串，不能是undefined
      };

      console.log('🔄 提交反馈:', userFeedback.trim());

      // 发送反馈请求 - 与ChatPage对齐的处理方式
      const response = await fetch('/api/testcase/feedback/streaming', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(feedbackData),
      });

      if (!response.ok) {
        throw new Error(`反馈请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法获取反馈响应流');
      }

      // 处理反馈的SSE流
      await processSSEStream(reader);

      setUserFeedback('');
      setRoundNumber(prev => prev + 1);
      message.success('反馈提交成功！');
    } catch (error: any) {
      console.error('提交反馈失败:', error);
      message.error(`提交反馈失败: ${error.message || '请重试'}`);
      setStreamError(error.message || '反馈提交失败');
    } finally {
      setLoading(false);
    }
  };

  const stopGeneration = () => {
    setLoading(false);
    setCurrentStep(0);
    setAnalysisProgress(0);
    setStreamingContent('');
    setCurrentAgent('');
    setAgentStreamingMap({});
    message.info('已停止生成');
  };

  const resetConversation = async () => {
    console.log('🔄 开始重置对话');

    // 如果有现有的conversation_id，先清除后端历史记录
    if (conversationId) {
      try {
        console.log('🗑️ 清除后端历史记录:', conversationId);
        const response = await fetch(`/api/testcase/conversation/${conversationId}`, {
          method: 'DELETE',
        });

        if (response.ok) {
          console.log('✅ 后端历史记录清除成功');
        } else {
          console.warn('⚠️ 后端历史记录清除失败，但继续重置前端状态');
        }
      } catch (error) {
        console.warn('⚠️ 清除后端历史记录时出错:', error);
      }
    }

    // 生成新的conversation_id
    const newConversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    console.log('🆕 生成新的conversation_id:', newConversationId);

    // 重置所有状态
    setAgentMessages([]);
    setConversationId(newConversationId);  // 设置新的conversation_id
    setRoundNumber(1);
    setCurrentStep(0);
    setTextContent('');
    setSelectedFiles([]);
    setUserFeedback('');
    setIsComplete(false);
    setAnalysisProgress(0);
    setStreamingContent('');
    setCurrentAgent('');
    setAgentStreamingMap({});
    setLoading(false);
    setStreamError(null);

    message.success('已重新开始，生成新的对话');
    console.log('🎉 对话重置完成，新conversation_id:', newConversationId);
  };

  return (
    <PageLayout background="#f8f9fa">
      <style>
        {`
          @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
          }
        `}
      </style>
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
                      {loading ? '正在生成...' : 'AI智能分析'}
                    </Button>
                  )}

                  {loading && (
                    <Button
                      danger
                      icon={<ReloadOutlined />}
                      onClick={stopGeneration}
                      size="large"
                      style={{
                        width: '100%',
                        height: 48,
                        fontSize: 16,
                        fontWeight: 600,
                        borderRadius: 8,
                        marginTop: 12
                      }}
                    >
                      停止生成
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

              {agentMessages.length > 0 && (
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
              {agentMessages.length === 0 && !currentAgent ? (
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
                  {/* 流式内容显示 */}
                  {currentAgent && (
                    <div style={{ marginBottom: 24 }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        marginBottom: 12,
                        padding: '8px 12px',
                        background: '#e6f7ff',
                        borderRadius: 6,
                        border: '1px solid #91d5ff'
                      }}>
                        <RobotOutlined style={{
                          color: '#1890ff',
                          marginRight: 8
                        }} />
                        <Text strong style={{ color: '#1890ff' }}>
                          {currentAgent}
                        </Text>
                        <Tag color="processing" style={{ marginLeft: 'auto' }}>
                          正在输出...
                        </Tag>
                      </div>

                      <div style={{
                        marginLeft: 0,
                        padding: 16,
                        background: 'white',
                        borderRadius: 8,
                        border: '1px solid #f0f0f0',
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.6,
                        minHeight: 60,
                        maxWidth: '100%',
                        overflow: 'hidden',
                        wordBreak: 'break-word'
                      }}>
                        {streamingContent ? (
                          <MarkdownRenderer content={streamingContent} />
                        ) : (
                          <span style={{ color: '#8c8c8c', fontStyle: 'italic' }}>
                            正在等待输出...
                          </span>
                        )}
                        <span style={{
                          display: 'inline-block',
                          width: 8,
                          height: 16,
                          background: '#1890ff',
                          animation: 'blink 1s infinite',
                          marginLeft: 4
                        }} />
                      </div>
                    </div>
                  )}

                  {/* AI生成的消息列表 */}
                  <div style={{ marginBottom: 24 }}>
                    {agentMessages.map((msg, index) => (
                      <div key={msg.id} style={{ marginBottom: 24 }}>
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          marginBottom: 12,
                          padding: '8px 12px',
                          background: getAgentBackground(msg.agentType, msg.agentName),
                          borderRadius: 6,
                          border: `1px solid ${getAgentBorderColor(msg.agentType, msg.agentName)}`
                        }}>
                          <RobotOutlined style={{
                            color: getAgentColor(msg.agentType, msg.agentName),
                            marginRight: 8
                          }} />
                          <Text strong style={{
                            color: getAgentColor(msg.agentType, msg.agentName)
                          }}>
                            {getAgentDisplayName(msg.agentType, msg.agentName)}
                          </Text>
                          <Tag
                            color={getAgentTagColor(msg.agentType, msg.agentName)}
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
                          lineHeight: 1.6,
                          minHeight: 60,
                          maxWidth: '100%',
                          overflow: 'hidden',
                          wordBreak: 'break-word'
                        }}>
                          {msg.content ? (
                            <AgentMessage
                              agentType={msg.agentType}
                              agentName={msg.agentName}
                              content={msg.content}
                              timestamp={msg.timestamp}
                              roundNumber={msg.roundNumber}
                              isExpanded={true}
                            />
                          ) : (
                            <div style={{
                              color: '#8c8c8c',
                              fontStyle: 'italic',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              minHeight: 40
                            }}>
                              正在生成内容...
                            </div>
                          )}
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
