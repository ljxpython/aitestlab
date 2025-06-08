import React from 'react';
import { Card, Typography, Space } from 'antd';
import PageLayout from '@/components/PageLayout';

const { Title, Paragraph } = Typography;

const ScrollTestPage: React.FC = () => {
  return (
    <PageLayout>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Title level={2}>滚动测试页面</Title>
          <Paragraph>
            这个页面用于测试侧边栏在页面滚动时是否保持固定。
            请向下滚动查看侧边栏是否始终保持在视窗中。
          </Paragraph>
        </Card>

        {/* 生成大量内容用于测试滚动 */}
        {Array.from({ length: 20 }, (_, index) => (
          <Card key={index} title={`测试卡片 ${index + 1}`}>
            <Paragraph>
              这是第 {index + 1} 个测试卡片。当您滚动页面时，侧边栏应该保持固定在左侧，
              不会随着页面内容一起滚动。这确保了用户在浏览长页面时始终可以访问导航功能。
            </Paragraph>
            <Paragraph>
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
              tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
              quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
            </Paragraph>
            <Paragraph>
              Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
              eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident,
              sunt in culpa qui officia deserunt mollit anim id est laborum.
            </Paragraph>
          </Card>
        ))}

        <Card>
          <Title level={3}>测试完成</Title>
          <Paragraph>
            如果您能看到这个卡片，说明页面可以正常滚动。
            同时，侧边栏应该始终保持在左侧固定位置，不随页面滚动。
          </Paragraph>
        </Card>
      </Space>
    </PageLayout>
  );
};

export default ScrollTestPage;
