import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Form,
  Input,
  Button,
  Card,
  Typography,
  Space,
  Alert,
  Divider,
  message
} from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons';
import { login } from '@/services/auth';

const { Title, Text } = Typography;

interface LoginForm {
  username: string;
  password: string;
}

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleLogin = async (values: LoginForm) => {
    setLoading(true);
    try {
      const response = await login(values.username, values.password);

      // 保存用户信息到localStorage
      localStorage.setItem('token', response.access_token);
      localStorage.setItem('user', JSON.stringify(response.user));

      message.success('登录成功！');
      navigate('/');
    } catch (error: any) {
      message.error(error.message || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
          borderRadius: 16,
          border: 'none'
        }}
        bodyStyle={{ padding: '40px 32px' }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Logo和标题 */}
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: 24,
                fontWeight: 'bold',
                margin: '0 auto 16px',
                boxShadow: '0 4px 16px rgba(102, 126, 234, 0.3)',
              }}
            >
              AI
            </div>
            <Title level={2} style={{ margin: 0, color: '#262626' }}>
              AI 测试平台
            </Title>
            <Text type="secondary" style={{ fontSize: 14 }}>
              智能化测试解决方案
            </Text>
          </div>



          {/* 登录表单 */}
          <Form
            form={form}
            name="login"
            onFinish={handleLogin}
            autoComplete="off"
            size="large"

          >
            <Form.Item
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 1, message: '用户名不能为空' }
              ]}
            >
              <Input
                prefix={<UserOutlined style={{ color: '#8c8c8c' }} />}
                placeholder="用户名"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 1, message: '密码不能为空' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: '#8c8c8c' }} />}
                placeholder="密码"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<LoginOutlined />}
                style={{
                  width: '100%',
                  height: 48,
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  border: 'none',
                  fontSize: 16,
                  fontWeight: 500,
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                }}
              >
                登录
              </Button>
            </Form.Item>
          </Form>

          <Divider style={{ margin: '8px 0' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              基于 AutoGen + FastAPI + React
            </Text>
          </Divider>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
