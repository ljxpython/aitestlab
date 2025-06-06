import React, { useState } from 'react';
import {
  Drawer,
  Switch,
  Slider,
  Select,
  Typography,
  Space,
  Button,
  Card,
  Radio
} from 'antd';
import {
  SettingOutlined,
  MoonOutlined,
  SunOutlined,
  GlobalOutlined,
  CaretRightOutlined,
  ExperimentOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

interface SettingsPanelProps {
  visible: boolean;
  onClose: () => void;
}

const SettingsPanel: React.FC<SettingsPanelProps> = ({ visible, onClose }) => {
  const [settings, setSettings] = useState({
    theme: 'light', // light, dark, auto
    language: 'zh-CN',
    fontSize: 14,
    autoSend: false,
    soundEnabled: true,
    streamResponse: true,
    temperature: 0.7,
    maxTokens: 2048
  });

  const handleSettingChange = (key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const resetSettings = () => {
    setSettings({
      theme: 'light',
      language: 'zh-CN',
      fontSize: 14,
      autoSend: false,
      soundEnabled: true,
      streamResponse: true,
      temperature: 0.7,
      maxTokens: 2048
    });
  };

  return (
    <Drawer
      title={
        <Space>
          <SettingOutlined />
          <span>设置</span>
        </Space>
      }
      placement="right"
      onClose={onClose}
      open={visible}
      width={360}
    >
      <div style={{ padding: '0 4px' }}>
        {/* 外观设置 */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Title level={5} style={{ margin: '0 0 16px 0' }}>
            <SunOutlined style={{ marginRight: 8 }} />
            外观
          </Title>

          <div style={{ marginBottom: 16 }}>
            <Text style={{ display: 'block', marginBottom: 8 }}>主题</Text>
            <Radio.Group
              value={settings.theme}
              onChange={(e) => handleSettingChange('theme', e.target.value)}
              style={{ width: '100%' }}
            >
              <Radio.Button value="light" style={{ flex: 1, textAlign: 'center' }}>
                <SunOutlined /> 浅色
              </Radio.Button>
              <Radio.Button value="dark" style={{ flex: 1, textAlign: 'center' }}>
                <MoonOutlined /> 深色
              </Radio.Button>
              <Radio.Button value="auto" style={{ flex: 1, textAlign: 'center' }}>
                自动
              </Radio.Button>
            </Radio.Group>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text style={{ display: 'block', marginBottom: 8 }}>
              字体大小: {settings.fontSize}px
            </Text>
            <Slider
              min={12}
              max={20}
              value={settings.fontSize}
              onChange={(value) => handleSettingChange('fontSize', value)}
              marks={{
                12: '小',
                16: '中',
                20: '大'
              }}
            />
          </div>
        </Card>

        {/* 语言设置 */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Title level={5} style={{ margin: '0 0 16px 0' }}>
            <GlobalOutlined style={{ marginRight: 8 }} />
            语言
          </Title>

          <Select
            value={settings.language}
            onChange={(value) => handleSettingChange('language', value)}
            style={{ width: '100%' }}
          >
            <Option value="zh-CN">简体中文</Option>
            <Option value="zh-TW">繁體中文</Option>
            <Option value="en-US">English</Option>
            <Option value="ja-JP">日本語</Option>
            <Option value="ko-KR">한국어</Option>
          </Select>
        </Card>

        {/* 交互设置 */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Title level={5} style={{ margin: '0 0 16px 0' }}>
            交互
          </Title>

          <div style={{ marginBottom: 16 }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8
            }}>
              <Text>流式响应</Text>
              <Switch
                checked={settings.streamResponse}
                onChange={(checked) => handleSettingChange('streamResponse', checked)}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              实时显示 AI 回复内容
            </Text>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8
            }}>
              <Text>Enter 键发送</Text>
              <Switch
                checked={settings.autoSend}
                onChange={(checked) => handleSettingChange('autoSend', checked)}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              按 Enter 键直接发送消息
            </Text>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8
            }}>
              <Space>
                <CaretRightOutlined />
                <Text>声音提示</Text>
              </Space>
              <Switch
                checked={settings.soundEnabled}
                onChange={(checked) => handleSettingChange('soundEnabled', checked)}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              消息发送和接收时播放提示音
            </Text>
          </div>
        </Card>

        {/* 高级设置 */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Title level={5} style={{ margin: '0 0 16px 0' }}>
            <ExperimentOutlined style={{ marginRight: 8 }} />
            高级设置
          </Title>

          <div style={{ marginBottom: 16 }}>
            <Text style={{ display: 'block', marginBottom: 8 }}>
              创造性: {settings.temperature}
            </Text>
            <Slider
              min={0}
              max={1}
              step={0.1}
              value={settings.temperature}
              onChange={(value) => handleSettingChange('temperature', value)}
              marks={{
                0: '保守',
                0.5: '平衡',
                1: '创新'
              }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              控制 AI 回复的创造性和随机性
            </Text>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text style={{ display: 'block', marginBottom: 8 }}>
              最大回复长度: {settings.maxTokens}
            </Text>
            <Slider
              min={512}
              max={4096}
              step={256}
              value={settings.maxTokens}
              onChange={(value) => handleSettingChange('maxTokens', value)}
              marks={{
                512: '短',
                2048: '中',
                4096: '长'
              }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              限制 AI 单次回复的最大长度
            </Text>
          </div>
        </Card>

        {/* 操作按钮 */}
        <div style={{
          display: 'flex',
          gap: 8,
          marginTop: 24
        }}>
          <Button
            block
            onClick={resetSettings}
          >
            重置设置
          </Button>
          <Button
            type="primary"
            block
            onClick={onClose}
          >
            保存设置
          </Button>
        </div>

        {/* 版本信息 */}
        <div style={{
          textAlign: 'center',
          marginTop: 32,
          padding: 16,
          backgroundColor: '#f9fafb',
          borderRadius: 8
        }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            自动化测试平台 AI 模块 v1.0.0
          </Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            基于 AutoGen 0.5.7 构建
          </Text>
        </div>
      </div>
    </Drawer>
  );
};

export default SettingsPanel;
