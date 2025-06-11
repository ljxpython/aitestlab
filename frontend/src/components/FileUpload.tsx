import React, { useState } from 'react';
import { Upload, Button, message, Card, Typography, Space, Tag, Progress } from 'antd';
import { InboxOutlined, FileTextOutlined, PictureOutlined, DeleteOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';

const { Dragger } = Upload;
const { Text } = Typography;

interface FileUploadProps {
  onFilesChange: (files: UploadFile[]) => void;
  maxFiles?: number;
  maxSize?: number; // MB
}

// 扩展 UploadFile 类型，添加上传结果信息
interface ExtendedUploadFile extends UploadFile {
  uploadResult?: {
    conversation_id: string;
    filename: string;
    content_type: string;
    size: number;
  };
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFilesChange,
  maxFiles = 5,
  maxSize = 10
}) => {
  const [fileList, setFileList] = useState<ExtendedUploadFile[]>([]);
  const [uploading, setUploading] = useState<boolean>(false);

  // 处理文件选择（不自动上传，只选择文件）
  const handleFileSelect = (options: any) => {
    const { file, onSuccess, onError } = options;

    console.log('🔍 开始处理文件选择:', file.name, file);

    // 检查文件大小
    const isLtMaxSize = file.size / 1024 / 1024 < maxSize;
    if (!isLtMaxSize) {
      message.error(`文件大小不能超过 ${maxSize}MB!`);
      onError(new Error('文件大小超限'));
      return;
    }

    // 检查文件数量
    if (fileList.length >= maxFiles) {
      message.error(`最多只能上传 ${maxFiles} 个文件!`);
      onError(new Error('文件数量超限'));
      return;
    }

    // 检查是否已存在相同文件
    const existingFile = fileList.find(f => f.name === file.name && f.size === file.size);
    if (existingFile) {
      message.warning(`文件 ${file.name} 已存在`);
      onError(new Error('文件已存在'));
      return;
    }

    console.log('✅ 文件验证通过，添加到列表:', file.name);

    // 创建文件对象（不上传，只选择）
    const selectedFile: ExtendedUploadFile = {
      uid: file.uid || `${Date.now()}-${Math.random()}`,
      name: file.name,
      size: file.size,
      type: file.type,
      status: 'done', // 标记为完成（实际上是选择完成）
      percent: 100,
      originFileObj: file, // 保存原始文件对象，供后续上传使用
    };

    // 更新文件列表
    const newFileList = [...fileList, selectedFile];
    setFileList(newFileList);
    onFilesChange(newFileList);

    message.success(`文件 ${file.name} 选择成功！`);
    onSuccess('ok');
  };

  const uploadProps: UploadProps = {
    name: 'files',
    multiple: true,
    fileList,
    customRequest: handleFileSelect, // 改为文件选择处理
    showUploadList: false, // 使用自定义的文件列表
  };

  const removeFile = (file: ExtendedUploadFile) => {
    const newFileList = fileList.filter(item => item.uid !== file.uid);
    setFileList(newFileList);
    onFilesChange(newFileList);
  };

  // 获取文件状态图标
  const getFileStatusIcon = (file: ExtendedUploadFile) => {
    switch (file.status) {
      case 'uploading':
        return <Progress type="circle" size={16} percent={file.percent || 0} />;
      case 'done':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  const getFileIcon = (file: ExtendedUploadFile) => {
    const fileType = file.type || '';
    const fileName = file.name || '';
    const fileExt = fileName.split('.').pop()?.toLowerCase() || '';

    // 图片文件
    if (fileType.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt)) {
      return <PictureOutlined style={{ color: '#52c41a' }} />;
    }

    // 文档文件
    if (fileType.startsWith('text/') ||
        fileType.includes('document') ||
        ['txt', 'md', 'markdown', 'doc', 'docx', 'pdf', 'rtf'].includes(fileExt)) {
      return <FileTextOutlined style={{ color: '#1890ff' }} />;
    }

    return <FileTextOutlined style={{ color: '#666' }} />;
  };

  // 获取文件类型标签
  const getFileTypeTag = (file: ExtendedUploadFile) => {
    const fileType = file.type || '';
    const fileName = file.name || '';
    const fileExt = fileName.split('.').pop()?.toLowerCase() || '';

    // 根据扩展名确定类型
    if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt)) {
      return 'image';
    }
    if (['txt', 'md', 'markdown'].includes(fileExt)) {
      return 'text';
    }
    if (['doc', 'docx'].includes(fileExt)) {
      return 'word';
    }
    if (['pdf'].includes(fileExt)) {
      return 'pdf';
    }
    if (['json', 'xml', 'yaml', 'yml'].includes(fileExt)) {
      return 'data';
    }

    // 根据MIME类型确定
    if (fileType.startsWith('image/')) {
      return 'image';
    }
    if (fileType.startsWith('text/')) {
      return 'text';
    }
    if (fileType.includes('document')) {
      return 'document';
    }

    return fileExt || 'file';
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
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          点击或拖拽文件到此区域上传
        </p>
        <p className="ant-upload-hint">
          支持单个或批量上传。最多 {maxFiles} 个文件，每个文件不超过 {maxSize}MB
        </p>
        <p className="ant-upload-hint" style={{ marginTop: 8, fontSize: 12 }}>
          支持 .txt, .md, .doc, .pdf 等文档格式
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
                    {file.status === 'uploading' && (
                      <Text type="secondary" style={{ fontSize: 12, color: '#1890ff' }}>
                        正在处理...
                      </Text>
                    )}
                    {file.status === 'done' && (
                      <Text type="secondary" style={{ fontSize: 12, color: '#52c41a' }}>
                        已选择
                      </Text>
                    )}
                    {file.status === 'error' && (
                      <Text type="secondary" style={{ fontSize: 12, color: '#ff4d4f' }}>
                        选择失败
                      </Text>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {getFileStatusIcon(file)}
                    <Tag color="blue">
                      {getFileTypeTag(file)}
                    </Tag>
                  </div>
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

      <style>{`
        .file-upload-container .ant-upload-drag {
          background: linear-gradient(135deg, #fafbff 0%, #f0f4ff 50%, #e6f0ff 100%) !important;
          border: 2px dashed #b3d4fc !important;
          border-radius: 16px !important;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
          position: relative !important;
          overflow: hidden !important;
          min-height: 160px !important;
          display: flex !important;
          flex-direction: column !important;
          justify-content: center !important;
          align-items: center !important;
        }

        .file-upload-container .ant-upload-drag::before {
          content: '' !important;
          position: absolute !important;
          top: 0 !important;
          left: 0 !important;
          right: 0 !important;
          bottom: 0 !important;
          background: linear-gradient(135deg, rgba(64, 169, 255, 0.08) 0%, rgba(24, 144, 255, 0.12) 100%) !important;
          opacity: 0 !important;
          transition: opacity 0.4s ease !important;
        }

        .file-upload-container .ant-upload-drag:hover {
          border-color: #40a9ff !important;
          transform: translateY(-3px) !important;
          box-shadow: 0 12px 32px rgba(64, 169, 255, 0.15), 0 4px 16px rgba(24, 144, 255, 0.1) !important;
          background: linear-gradient(135deg, #f0f8ff 0%, #e6f4ff 50%, #d6efff 100%) !important;
        }

        .file-upload-container .ant-upload-drag:hover::before {
          opacity: 1 !important;
        }

        .file-upload-container .ant-upload-drag .ant-upload-text {
          color: #1f2937 !important;
          margin-top: 20px !important;
          font-size: 18px !important;
          font-weight: 600 !important;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
        }

        .file-upload-container .ant-upload-drag .ant-upload-hint {
          color: #6b7280 !important;
          font-size: 14px !important;
          margin-top: 12px !important;
          line-height: 1.5 !important;
          max-width: 320px !important;
          text-align: center !important;
        }

        .file-upload-container .ant-upload-drag-icon {
          margin-bottom: 8px !important;
          position: relative !important;
          z-index: 1 !important;
        }

        .file-upload-container .ant-upload-drag-icon .anticon {
          color: #3b82f6 !important;
          font-size: 56px !important;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
          filter: drop-shadow(0 2px 8px rgba(59, 130, 246, 0.2)) !important;
        }

        .file-upload-container .ant-upload-drag:hover .ant-upload-drag-icon .anticon {
          color: #2563eb !important;
          transform: scale(1.15) rotate(5deg) !important;
          filter: drop-shadow(0 4px 12px rgba(37, 99, 235, 0.3)) !important;
        }

        .file-upload-container .ant-upload-drag.ant-upload-drag-hover {
          border-color: #2563eb !important;
          background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 50%, #bfdbfe 100%) !important;
        }

        .file-upload-container .ant-upload-drag:active {
          transform: translateY(-1px) !important;
        }
      `}</style>
    </div>
  );
};

export default FileUpload;
