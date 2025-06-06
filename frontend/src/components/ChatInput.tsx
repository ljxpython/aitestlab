import React, { useState, useRef } from 'react';
import { Input, Button, Tooltip, Upload } from 'antd';
import {
  SendOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  CameraOutlined,
  AudioOutlined
} from '@ant-design/icons';

const { TextArea } = Input;

interface ChatInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
  placeholder?: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  loading = false,
  placeholder = '输入您的问题...',
}) => {
  const [message, setMessage] = useState('');
  const textAreaRef = useRef<any>(null);

  const handleSend = () => {
    if (message.trim() && !loading) {
      onSend(message.trim());
      setMessage('');
      // 重置文本框高度
      if (textAreaRef.current) {
        textAreaRef.current.resizableTextArea.textArea.style.height = 'auto';
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{
      padding: '20px 24px',
      backgroundColor: 'transparent'
    }}>
      {/* Gemini 风格的输入框 */}
      <div style={{
        position: 'relative',
        backgroundColor: 'white',
        borderRadius: '24px',
        border: '1px solid #e5e7eb',
        boxShadow: '0 2px 12px rgba(0, 0, 0, 0.08)',
        transition: 'all 0.2s ease',
        ':focus-within': {
          borderColor: '#667eea',
          boxShadow: '0 4px 20px rgba(102, 126, 234, 0.15)'
        }
      }}>
        {/* 附件按钮 */}
        <div style={{
          position: 'absolute',
          left: 12,
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          gap: 4,
          zIndex: 1
        }}>
          <Tooltip title="上传文件">
            <Upload showUploadList={false}>
              <Button
                type="text"
                size="small"
                icon={<PaperClipOutlined />}
                style={{
                  color: '#6b7280',
                  border: 'none',
                  width: 32,
                  height: 32,
                  borderRadius: '50%'
                }}
              />
            </Upload>
          </Tooltip>

          <Tooltip title="拍照">
            <Button
              type="text"
              size="small"
              icon={<CameraOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                width: 32,
                height: 32,
                borderRadius: '50%'
              }}
            />
          </Tooltip>
        </div>

        {/* 输入框 */}
        <TextArea
          ref={textAreaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={loading}
          style={{
            border: 'none',
            outline: 'none',
            resize: 'none',
            fontSize: '16px',
            lineHeight: '1.5',
            padding: '12px 120px 12px 80px',
            backgroundColor: 'transparent',
            borderRadius: '24px'
          }}
        />

        {/* 发送按钮区域 */}
        <div style={{
          position: 'absolute',
          right: 8,
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <Tooltip title="语音输入">
            <Button
              type="text"
              size="small"
              icon={<AudioOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                width: 32,
                height: 32,
                borderRadius: '50%'
              }}
            />
          </Tooltip>

          <Tooltip title={loading ? '发送中...' : '发送消息'}>
            <Button
              type="primary"
              shape="circle"
              size="large"
              icon={loading ? <LoadingOutlined /> : <SendOutlined />}
              onClick={handleSend}
              disabled={!message.trim() || loading}
              style={{
                background: message.trim() && !loading
                  ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                  : '#e5e7eb',
                border: 'none',
                width: 40,
                height: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: message.trim() && !loading
                  ? '0 4px 12px rgba(102, 126, 234, 0.3)'
                  : 'none',
                transition: 'all 0.2s ease'
              }}
            />
          </Tooltip>
        </div>
      </div>

      {/* 提示文字 */}
      <div style={{
        marginTop: 12,
        fontSize: '13px',
        color: '#9ca3af',
        textAlign: 'center'
      }}>
        AI 测试助手可能会显示不准确的信息，请结合实际情况验证测试方案的可行性。
      </div>
    </div>
  );
};

export default ChatInput;
