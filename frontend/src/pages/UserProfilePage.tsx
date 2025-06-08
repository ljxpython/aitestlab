import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Avatar,
  Space,
  Typography,
  Divider,
  message,
  Modal,
  Row,
  Col
} from 'antd';
import {
  UserOutlined,
  MailOutlined,
  EditOutlined,
  LockOutlined,
  SaveOutlined,
  CameraOutlined
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';
import { getCurrentUser, updateUser, changePassword } from '@/services/auth';

const { Title, Text } = Typography;

interface UserInfo {
  id: number;
  username: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at?: string;
  updated_at?: string;
  last_login?: string;
}

interface PasswordForm {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

const UserProfilePage: React.FC = () => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [passwordModalVisible, setPasswordModalVisible] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const [form] = Form.useForm();
  const [passwordForm] = Form.useForm();

  useEffect(() => {
    loadUserInfo();
  }, []);

  const loadUserInfo = async () => {
    try {
      const user = await getCurrentUser();
      setUserInfo(user);
      form.setFieldsValue({
        username: user.username,
        email: user.email,
        full_name: user.full_name,
        avatar_url: user.avatar_url,
      });
    } catch (error: any) {
      message.error('获取用户信息失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async (values: any) => {
    setUpdating(true);
    try {
      const updatedUser = await updateUser({
        email: values.email,
        full_name: values.full_name,
        avatar_url: values.avatar_url,
      });

      setUserInfo(updatedUser);

      // 更新localStorage中的用户信息
      const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
      localStorage.setItem('user', JSON.stringify({ ...currentUser, ...updatedUser }));

      message.success('用户信息更新成功');
    } catch (error: any) {
      message.error(error.message || '更新失败');
    } finally {
      setUpdating(false);
    }
  };

  const handleChangePassword = async (values: PasswordForm) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的密码不一致');
      return;
    }

    setPasswordLoading(true);
    try {
      await changePassword(values.old_password, values.new_password);
      message.success('密码修改成功');
      setPasswordModalVisible(false);
      passwordForm.resetFields();
    } catch (error: any) {
      message.error(error.message || '密码修改失败');
    } finally {
      setPasswordLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Text>加载中...</Text>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 页面标题 */}
          <Card>
            <Title level={2} style={{ margin: 0 }}>
              <UserOutlined style={{ marginRight: 8, color: '#1890ff' }} />
              用户资料
            </Title>
            <Text type="secondary">管理您的个人信息和账户设置</Text>
          </Card>

          {/* 用户头像和基本信息 */}
          <Card title="基本信息">
            <Row gutter={24}>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <Avatar
                    size={120}
                    src={userInfo?.avatar_url}
                    icon={<UserOutlined />}
                    style={{
                      marginBottom: 16,
                      border: '4px solid #f0f0f0',
                    }}
                  />
                  <div>
                    <Button
                      type="text"
                      icon={<CameraOutlined />}
                      size="small"
                      style={{ color: '#1890ff' }}
                    >
                      更换头像
                    </Button>
                  </div>
                </div>
              </Col>
              <Col span={18}>
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <div>
                    <Text strong style={{ fontSize: 18 }}>
                      {userInfo?.full_name || userInfo?.username}
                    </Text>
                    {userInfo?.is_superuser && (
                      <span style={{
                        marginLeft: 8,
                        padding: '2px 8px',
                        background: '#f6ffed',
                        color: '#52c41a',
                        borderRadius: 4,
                        fontSize: 12,
                        border: '1px solid #b7eb8f'
                      }}>
                        管理员
                      </span>
                    )}
                  </div>
                  <div>
                    <Text type="secondary">@{userInfo?.username}</Text>
                  </div>
                  <div>
                    <Text type="secondary">
                      注册时间: {userInfo?.created_at ? new Date(userInfo.created_at).toLocaleDateString() : '未知'}
                    </Text>
                  </div>
                  <div>
                    <Text type="secondary">
                      最后登录: {userInfo?.last_login ? new Date(userInfo.last_login).toLocaleString() : '未知'}
                    </Text>
                  </div>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* 编辑用户信息 */}
          <Card
            title="编辑资料"
            extra={
              <Button
                type="primary"
                icon={<LockOutlined />}
                onClick={() => setPasswordModalVisible(true)}
              >
                修改密码
              </Button>
            }
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleUpdateProfile}
              autoComplete="off"
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="用户名"
                    name="username"
                  >
                    <Input
                      prefix={<UserOutlined />}
                      disabled
                      style={{ background: '#f5f5f5' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="邮箱"
                    name="email"
                    rules={[
                      { type: 'email', message: '请输入有效的邮箱地址' }
                    ]}
                  >
                    <Input
                      prefix={<MailOutlined />}
                      placeholder="请输入邮箱"
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                label="全名"
                name="full_name"
              >
                <Input
                  prefix={<EditOutlined />}
                  placeholder="请输入全名"
                />
              </Form.Item>

              <Form.Item
                label="头像URL"
                name="avatar_url"
              >
                <Input
                  placeholder="请输入头像URL"
                />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={updating}
                  icon={<SaveOutlined />}
                  size="large"
                >
                  保存更改
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Space>

        {/* 修改密码模态框 */}
        <Modal
          title="修改密码"
          open={passwordModalVisible}
          onCancel={() => {
            setPasswordModalVisible(false);
            passwordForm.resetFields();
          }}
          footer={null}
          width={400}
        >
          <Form
            form={passwordForm}
            layout="vertical"
            onFinish={handleChangePassword}
            autoComplete="off"
          >
            <Form.Item
              label="当前密码"
              name="old_password"
              rules={[{ required: true, message: '请输入当前密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="请输入当前密码"
              />
            </Form.Item>

            <Form.Item
              label="新密码"
              name="new_password"
              rules={[
                { required: true, message: '请输入新密码' },
                { min: 6, message: '密码至少6位字符' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="请输入新密码"
              />
            </Form.Item>

            <Form.Item
              label="确认新密码"
              name="confirm_password"
              rules={[
                { required: true, message: '请确认新密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('new_password') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'));
                  },
                }),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="请确认新密码"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
              <Space>
                <Button onClick={() => setPasswordModalVisible(false)}>
                  取消
                </Button>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={passwordLoading}
                >
                  确认修改
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </PageLayout>
  );
};

export default UserProfilePage;
