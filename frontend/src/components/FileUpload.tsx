import React, { useState } from 'react';
import { Upload, Button, message, Card, Typography, Space, Tag } from 'antd';
import { InboxOutlined, FileTextOutlined, PictureOutlined, DeleteOutlined } from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';

const { Dragger } = Upload;
const { Text } = Typography;

interface FileUploadProps {
  onFilesChange: (files: UploadFile[]) => void;
  maxFiles?: number;
  maxSize?: number; // MB
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFilesChange,
  maxFiles = 5,
  maxSize = 10
}) => {
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    fileList,
    beforeUpload: (file) => {
      // 检查文件大小
      const isLtMaxSize = file.size / 1024 / 1024 < maxSize;
      if (!isLtMaxSize) {
        message.error(`文件大小不能超过 ${maxSize}MB!`);
        return false;
      }

      // 检查文件数量
      if (fileList.length >= maxFiles) {
        message.error(`最多只能上传 ${maxFiles} 个文件!`);
        return false;
      }

      return false; // 阻止自动上传
    },
    onChange: (info) => {
      let newFileList = [...info.fileList];

      // 限制文件数量
      newFileList = newFileList.slice(-maxFiles);

      setFileList(newFileList);
      onFilesChange(newFileList);
    },
    onDrop: (e) => {
      console.log('Dropped files', e.dataTransfer.files);
    },
    showUploadList: false, // 使用自定义的文件列表
  };

  const removeFile = (file: UploadFile) => {
    const newFileList = fileList.filter(item => item.uid !== file.uid);
    setFileList(newFileList);
    onFilesChange(newFileList);
  };

  const getFileIcon = (file: UploadFile) => {
    const fileType = file.type || '';
    if (fileType.startsWith('image/')) {
      return <PictureOutlined style={{ color: '#52c41a' }} />;
    } else if (fileType.startsWith('text/') || fileType.includes('document')) {
      return <FileTextOutlined style={{ color: '#1890ff' }} />;
    }
    return <FileTextOutlined style={{ color: '#666' }} />;
  };

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="file-upload-container">
      <Dragger {...uploadProps} style={{ marginBottom: 16 }}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text" style={{ fontSize: 16, fontWeight: 500 }}>
          点击或拖拽文件到此区域上传
        </p>
        <p className="ant-upload-hint" style={{ color: '#666' }}>
          支持单个或批量上传。最多 {maxFiles} 个文件，每个文件不超过 {maxSize}MB
        </p>
      </Dragger>

      {fileList.length > 0 && (
        <Card
          title={`已选择文件 (${fileList.length}/${maxFiles})`}
          size="small"
          style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            border: 'none',
            borderRadius: 12
          }}
          headStyle={{
            color: 'white',
            borderBottom: '1px solid rgba(255,255,255,0.2)'
          }}
          bodyStyle={{
            background: 'rgba(255,255,255,0.95)',
            borderRadius: '0 0 12px 12px'
          }}
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            {fileList.map((file) => (
              <div
                key={file.uid}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'white',
                  borderRadius: 8,
                  border: '1px solid #f0f0f0',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                  {getFileIcon(file)}
                  <div style={{ marginLeft: 8, flex: 1 }}>
                    <Text strong style={{ display: 'block', fontSize: 14 }}>
                      {file.name}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatFileSize(file.size || 0)}
                    </Text>
                  </div>
                  <Tag color="blue" style={{ marginLeft: 8 }}>
                    {file.type?.split('/')[0] || 'unknown'}
                  </Tag>
                </div>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => removeFile(file)}
                  style={{ marginLeft: 8 }}
                />
              </div>
            ))}
          </Space>
        </Card>
      )}

      <style jsx>{`
        .file-upload-container .ant-upload-drag {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border: 2px dashed rgba(255,255,255,0.3);
          border-radius: 12px;
          transition: all 0.3s ease;
        }

        .file-upload-container .ant-upload-drag:hover {
          border-color: rgba(255,255,255,0.6);
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
        }

        .file-upload-container .ant-upload-drag .ant-upload-text {
          color: white;
          margin-top: 16px;
        }

        .file-upload-container .ant-upload-drag .ant-upload-hint {
          color: rgba(255,255,255,0.8);
        }

        .file-upload-container .ant-upload-drag-icon {
          margin-bottom: 8px;
        }

        .file-upload-container .ant-upload-drag-icon .anticon {
          color: rgba(255,255,255,0.9) !important;
        }
      `}</style>
    </div>
  );
};

export default FileUpload;
