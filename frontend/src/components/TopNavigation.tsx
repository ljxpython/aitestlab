import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Space, Button, Tooltip, Dropdown, Avatar, Typography } from 'antd';
import {
  GithubOutlined,
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
  LoginOutlined
} from '@ant-design/icons';
import { isAuthenticated, getLocalUser, logout, User } from '@/services/auth';

const { Header } = Layout;
const { Text } = Typography;

interface TopNavigationProps {
  title?: string;
}

const TopNavigation: React.FC<TopNavigationProps> = ({ title = 'AI 测试平台' }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = () => {
      const isAuth = isAuthenticated();
      setAuthenticated(isAuth);
      if (isAuth) {
        setUser(getLocalUser());
      }
    };

    checkAuth();

    // 监听存储变化
    const handleStorageChange = () => {
      checkAuth();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const handleGithubClick = () => {
    window.open('https://github.com/ljxpython/aitestlab', '_blank');
  };

  const handleLogout = async () => {
    try {
      await logout();
      setUser(null);
      setAuthenticated(false);
      navigate('/login');
    } catch (error) {
      console.error('登出失败:', error);
    }
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
      onClick: () => navigate('/profile'),
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '账户设置',
      onClick: () => navigate('/profile'),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Header
      style={{
        background: '#ffffff',
        padding: '0 24px',
        boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 64,
        zIndex: 1001,
        borderBottom: '1px solid #f0f0f0',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        width: '100%',
      }}
    >
      {/* 左侧标题 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '6px',
            background: '#1890ff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontSize: 14,
            fontWeight: 'bold',
          }}
        >
          AI
        </div>
        <span style={{
          color: '#262626',
          fontSize: 18,
          fontWeight: 500,
        }}>
          {title}
        </span>
      </div>

      {/* 右侧操作区 */}
      <Space size="middle">
        {/* GitHub 链接 */}
        <Tooltip title="查看源码" placement="bottom">
          <Button
            type="text"
            icon={<GithubOutlined />}
            onClick={handleGithubClick}
            style={{
              color: '#595959',
              border: '1px solid #d9d9d9',
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              height: 32,
              padding: '0 12px',
              fontSize: 14,
              transition: 'all 0.3s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f5f5f5';
              e.currentTarget.style.borderColor = '#40a9ff';
              e.currentTarget.style.color = '#40a9ff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.borderColor = '#d9d9d9';
              e.currentTarget.style.color = '#595959';
            }}
          >
            GitHub
          </Button>
        </Tooltip>

        {/* 用户菜单 */}
        {authenticated && user ? (
          <Dropdown
            menu={{ items: userMenuItems }}
            placement="bottomRight"
            trigger={['hover', 'click']}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 6,
                cursor: 'pointer',
                transition: 'all 0.3s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f5f5f5';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <Avatar
                size={32}
                src={user.avatar_url}
                icon={<UserOutlined />}
                style={{
                  background: user.avatar_url ? 'transparent' : '#1890ff',
                }}
              />
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: '#262626',
                    lineHeight: 1.2,
                    maxWidth: 100,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {user.full_name || user.username}
                </Text>
                {user.is_superuser && (
                  <Text
                    style={{
                      fontSize: 11,
                      color: '#52c41a',
                      lineHeight: 1,
                    }}
                  >
                    管理员
                  </Text>
                )}
              </div>
            </div>
          </Dropdown>
        ) : (
          <Button
            type="primary"
            icon={<LoginOutlined />}
            onClick={() => navigate('/login')}
            style={{
              borderRadius: 6,
              height: 32,
            }}
          >
            登录
          </Button>
        )}
      </Space>
    </Header>
  );
};

export default TopNavigation;
