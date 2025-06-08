import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Row, Col, Typography, Button, Space } from 'antd';
import {
  MessageOutlined,
  FileTextOutlined,
  RobotOutlined,
  ArrowRightOutlined,
  BulbOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';

const { Content } = Layout;
const { Title, Paragraph, Text } = Typography;

const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const modules = [
    {
      key: 'chat',
      title: 'AI 对话模块',
      description: '智能对话助手，为测试人员提供专业咨询和建议',
      icon: <MessageOutlined style={{ fontSize: 48, color: '#1890ff' }} />,
      features: [
        '实时流式对话',
        'Markdown 渲染',
        '对话历史管理',
        '智能建议'
      ],
      gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      path: '/chat',
      status: '已完成'
    },
    {
      key: 'testcase',
      title: 'AI 测试用例生成',
      description: '多智能体协作，自动分析需求并生成专业测试用例',
      icon: <FileTextOutlined style={{ fontSize: 48, color: '#52c41a' }} />,
      features: [
        '多智能体协作',
        '文件上传支持',
        '交互式优化',
        '专业测试用例'
      ],
      gradient: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
      path: '/testcase',
      status: '已完成'
    }
  ];

  const handleModuleClick = (path: string) => {
    navigate(path);
  };

  return (
    <Layout style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <Content style={{ padding: '50px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          {/* 页面标题 */}
          <div style={{ textAlign: 'center', marginBottom: 60 }}>
            <Space direction="vertical" size="large">
              <RobotOutlined style={{ fontSize: 80, color: 'white' }} />
              <Title
                level={1}
                style={{
                  color: 'white',
                  margin: 0,
                  fontSize: 48,
                  fontWeight: 'bold'
                }}
              >
                AI 测试平台
              </Title>
              <Paragraph
                style={{
                  color: 'rgba(255,255,255,0.9)',
                  fontSize: 18,
                  margin: 0,
                  maxWidth: 600
                }}
              >
                集成多个AI驱动的测试功能模块，提升测试效率，智能化测试流程
              </Paragraph>
            </Space>
          </div>

          {/* 功能模块卡片 */}
          <Row gutter={[32, 32]} justify="center">
            {modules.map((module) => (
              <Col xs={24} lg={12} key={module.key}>
                <Card
                  hoverable
                  style={{
                    borderRadius: 20,
                    overflow: 'hidden',
                    border: 'none',
                    boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
                    background: 'rgba(255,255,255,0.95)',
                    backdropFilter: 'blur(10px)',
                    height: '100%',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease'
                  }}
                  bodyStyle={{ padding: 0 }}
                  onClick={() => handleModuleClick(module.path)}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-8px)';
                    e.currentTarget.style.boxShadow = '0 20px 40px rgba(0,0,0,0.3)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = '0 10px 30px rgba(0,0,0,0.2)';
                  }}
                >
                  {/* 卡片头部 */}
                  <div
                    style={{
                      background: module.gradient,
                      padding: '30px 24px',
                      color: 'white',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                  >
                    <div style={{ position: 'relative', zIndex: 2 }}>
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          {module.icon}
                          <div
                            style={{
                              background: 'rgba(255,255,255,0.2)',
                              padding: '4px 12px',
                              borderRadius: 20,
                              fontSize: 12,
                              fontWeight: 'bold'
                            }}
                          >
                            {module.status}
                          </div>
                        </div>
                        <Title level={3} style={{ color: 'white', margin: 0 }}>
                          {module.title}
                        </Title>
                        <Text style={{ color: 'rgba(255,255,255,0.9)', fontSize: 14 }}>
                          {module.description}
                        </Text>
                      </Space>
                    </div>

                    {/* 装饰性背景 */}
                    <div
                      style={{
                        position: 'absolute',
                        top: -50,
                        right: -50,
                        width: 100,
                        height: 100,
                        background: 'rgba(255,255,255,0.1)',
                        borderRadius: '50%',
                        zIndex: 1
                      }}
                    />
                  </div>

                  {/* 卡片内容 */}
                  <div style={{ padding: '24px' }}>
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      <div>
                        <Title level={5} style={{ marginBottom: 12, color: '#333' }}>
                          <BulbOutlined style={{ marginRight: 8, color: '#faad14' }} />
                          核心功能
                        </Title>
                        <Row gutter={[8, 8]}>
                          {module.features.map((feature, index) => (
                            <Col span={12} key={index}>
                              <div
                                style={{
                                  padding: '8px 12px',
                                  background: '#f0f2f5',
                                  borderRadius: 8,
                                  fontSize: 12,
                                  textAlign: 'center',
                                  color: '#666'
                                }}
                              >
                                <ThunderboltOutlined style={{ marginRight: 4, color: '#52c41a' }} />
                                {feature}
                              </div>
                            </Col>
                          ))}
                        </Row>
                      </div>

                      <Button
                        type="primary"
                        size="large"
                        icon={<ArrowRightOutlined />}
                        style={{
                          width: '100%',
                          background: module.gradient,
                          border: 'none',
                          borderRadius: 10,
                          height: 50,
                          fontSize: 16,
                          fontWeight: 'bold'
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleModuleClick(module.path);
                        }}
                      >
                        立即体验
                      </Button>
                    </Space>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          {/* 底部信息 */}
          <div style={{ textAlign: 'center', marginTop: 60 }}>
            <Paragraph style={{ color: 'rgba(255,255,255,0.7)', fontSize: 14 }}>
              基于 AutoGen 0.5.7 + FastAPI + React 构建的智能测试平台
            </Paragraph>
          </div>
        </div>
      </Content>
    </Layout>
  );
};

export default HomePage;
