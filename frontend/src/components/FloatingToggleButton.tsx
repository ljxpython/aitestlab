import React from 'react';
import { Button } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';

interface SidebarToggleButtonProps {
  collapsed: boolean;
  onToggle: () => void;
}

const SidebarToggleButton: React.FC<SidebarToggleButtonProps> = ({
  collapsed,
  onToggle
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: '50%',
        right: -12,
        transform: 'translateY(-50%)',
        zIndex: 1001,
      }}
    >
      <Button
        type="text"
        size="small"
        icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        onClick={onToggle}
        style={{
          width: 24,
          height: 24,
          background: '#ffffff',
          border: '1px solid #d9d9d9',
          borderRadius: '50%',
          color: '#8c8c8c',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          transition: 'all 0.3s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#f5f5f5';
          e.currentTarget.style.borderColor = '#bfbfbf';
          e.currentTarget.style.color = '#595959';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#ffffff';
          e.currentTarget.style.borderColor = '#d9d9d9';
          e.currentTarget.style.color = '#8c8c8c';
        }}
      />
    </div>
  );
};

export default SidebarToggleButton;
