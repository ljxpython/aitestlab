import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Tooltip } from 'antd';
import {
  HomeOutlined,
  MessageOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons';
import TopNavigation from './TopNavigation';
import SidebarToggleButton from './FloatingToggleButton';
import './SideNavigation.css';

const { Sider } = Layout;
const { Text } = Typography;

interface SideNavigationProps {
  children: React.ReactNode;
}

const SideNavigation: React.FC<SideNavigationProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState(['ai-modules']); // 默认展开AI模块

  // 根据当前路径确定选中的菜单项
  const getSelectedKey = () => {
    const path = location.pathname;
    if (path === '/') return 'home';
    if (path === '/chat') return 'chat';
    if (path === '/testcase') return 'testcase';
    return 'home';
  };

  const menuItems = [
    {
      key: 'home',
      icon: <HomeOutlined />,
      label: collapsed ? null : '首页',
    },
    {
      key: 'divider1',
      type: 'divider',
    },
    {
      key: 'ai-modules',
      icon: <RobotOutlined />,
      label: collapsed ? null : 'AI 模块',
      children: [
        {
          key: 'chat',
          icon: <MessageOutlined />,
          label: 'AI 对话',
        },
        {
          key: 'testcase',
          icon: <FileTextOutlined />,
          label: '测试用例生成',
        },
      ],
    },
    {
      key: 'divider2',
      type: 'divider',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: collapsed ? null : '设置',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    switch (key) {
      case 'home':
        navigate('/');
        break;
      case 'chat':
        navigate('/chat');
        break;
      case 'testcase':
        navigate('/testcase');
        break;
      case 'settings':
        console.log('设置页面');
        break;
      default:
        break;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 顶部导航栏 */}
      <TopNavigation />

      {/* 主体布局 */}
      <Layout style={{ marginTop: 64 }}>
        <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={240}
        collapsedWidth={48}
        className="ant-layout-sider-fixed"
        style={{
          background: '#ffffff',
          boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
          position: 'fixed',
          left: 0,
          top: 64,
          height: 'calc(100vh - 64px)',
          zIndex: 1000,
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
        }}
      >
        {/* 顶部间距 */}
        <div style={{ height: 16 }} />



        {/* 导航菜单 */}
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          openKeys={collapsed ? [] : openKeys}
          onOpenChange={setOpenKeys}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 14,
            padding: '0 8px',
          }}
          items={menuItems}
        />

        {/* 底部信息 */}
        {!collapsed && (
          <div
            style={{
              position: 'absolute',
              bottom: 16,
              left: 16,
              right: 16,
              padding: 12,
              background: '#fafafa',
              borderRadius: 6,
              border: '1px solid #f0f0f0',
            }}
          >
            <Text
              style={{
                color: '#8c8c8c',
                fontSize: 12,
                display: 'block',
                textAlign: 'center',
                lineHeight: 1.4,
              }}
            >
              基于 AutoGen 0.5.7
              <br />
              FastAPI + React
            </Text>
          </div>
        )}

        {/* 折叠按钮 */}
        <SidebarToggleButton
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
        />
      </Sider>

        {/* 主内容区域 */}
        <Layout>
          <div
            className={`main-content-with-sidebar ${collapsed ? 'collapsed' : ''}`}
            style={{
              flex: 1,
              transition: 'all 0.2s',
              background: '#f5f5f5',
              minHeight: 'calc(100vh - 64px)',
              marginLeft: collapsed ? 48 : 240,
            }}
          >
            {children}
          </div>
        </Layout>
      </Layout>


    </Layout>
  );
};

export default SideNavigation;
