import React from 'react';

interface PageLayoutProps {
  children: React.ReactNode;
  background?: string;
  padding?: string;
}

const PageLayout: React.FC<PageLayoutProps> = ({
  children,
  background = '#f5f5f5',
  padding = '24px'
}) => {
  return (
    <div style={{
      minHeight: 'calc(100vh - 64px)',
      background,
      padding
    }}>
      {children}
    </div>
  );
};

export default PageLayout;
