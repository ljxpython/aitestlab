from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "username" VARCHAR(50) NOT NULL UNIQUE /* 用户名 */,
    "email" VARCHAR(100) UNIQUE /* 邮箱 */,
    "password_hash" VARCHAR(255) NOT NULL /* 密码哈希 */,
    "full_name" VARCHAR(100) /* 全名 */,
    "avatar_url" VARCHAR(255) /* 头像URL */,
    "is_active" INT NOT NULL DEFAULT 1 /* 是否激活 */,
    "is_superuser" INT NOT NULL DEFAULT 0 /* 是否超级用户 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */,
    "last_login" TIMESTAMP /* 最后登录时间 */
) /* 用户表 */;
CREATE TABLE IF NOT EXISTS "user_sessions" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "token" VARCHAR(255) NOT NULL UNIQUE /* 会话令牌 */,
    "expires_at" TIMESTAMP NOT NULL /* 过期时间 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "is_active" INT NOT NULL DEFAULT 1 /* 是否激活 */,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE /* 用户 */
) /* 用户会话表 */;
CREATE TABLE IF NOT EXISTS "testcase_conversations" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "user_id" INT /* 用户ID */,
    "conversation_id" VARCHAR(255) NOT NULL UNIQUE /* 对话ID */,
    "title" VARCHAR(500) /* 对话标题 */,
    "status" VARCHAR(50) NOT NULL DEFAULT 'active' /* 状态: active, completed, failed */,
    "round_number" INT NOT NULL DEFAULT 1 /* 当前轮次 */,
    "max_rounds" INT NOT NULL DEFAULT 3 /* 最大轮次 */,
    "text_content" TEXT /* 文本内容 */,
    "files_info" JSON /* 文件信息 */,
    "requirement_analysis" TEXT /* 需求分析结果 */,
    "generated_testcases" TEXT /* 生成的测试用例 */,
    "final_testcases" TEXT /* 最终测试用例 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */,
    "completed_at" TIMESTAMP /* 完成时间 */
) /* 测试用例对话记录 */;
CREATE TABLE IF NOT EXISTS "testcase_feedbacks" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "feedback_content" TEXT NOT NULL /* 反馈内容 */,
    "round_number" INT NOT NULL /* 反馈轮次 */,
    "previous_testcases" TEXT /* 反馈前的测试用例 */,
    "improved_testcases" TEXT /* 改进后的测试用例 */,
    "status" VARCHAR(50) NOT NULL DEFAULT 'processing' /* 状态: processing, completed, failed */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */,
    "conversation_id" CHAR(36) NOT NULL REFERENCES "testcase_conversations" ("id") ON DELETE CASCADE /* 所属对话 */
) /* 用户反馈记录 */;
CREATE TABLE IF NOT EXISTS "testcase_files" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "filename" VARCHAR(500) NOT NULL /* 文件名 */,
    "original_filename" VARCHAR(500) NOT NULL /* 原始文件名 */,
    "content_type" VARCHAR(200) NOT NULL /* 文件类型 */,
    "file_size" BIGINT NOT NULL /* 文件大小 */,
    "file_content" TEXT /* 文件内容(base64编码) */,
    "extracted_text" TEXT /* 提取的文本内容 */,
    "status" VARCHAR(50) NOT NULL DEFAULT 'uploaded' /* 状态: uploaded, processed, failed */,
    "error_message" TEXT /* 错误信息 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */,
    "conversation_id" CHAR(36) NOT NULL REFERENCES "testcase_conversations" ("id") ON DELETE CASCADE /* 所属对话 */
) /* 上传的文件记录 */;
CREATE TABLE IF NOT EXISTS "testcase_messages" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "content" TEXT NOT NULL /* 消息内容 */,
    "agent_type" VARCHAR(50) NOT NULL /* 智能体类型 */,
    "agent_name" VARCHAR(100) NOT NULL /* 智能体名称 */,
    "round_number" INT NOT NULL /* 轮次 */,
    "message_type" VARCHAR(50) NOT NULL DEFAULT 'agent' /* 消息类型: agent, user, system */,
    "is_complete" INT NOT NULL DEFAULT 0 /* 是否为完成消息 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "conversation_id" CHAR(36) NOT NULL REFERENCES "testcase_conversations" ("id") ON DELETE CASCADE /* 所属对话 */
) /* 测试用例对话消息 */;
CREATE TABLE IF NOT EXISTS "testcase_statistics" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "date" DATE NOT NULL /* 统计日期 */,
    "total_conversations" INT NOT NULL DEFAULT 0 /* 总对话数 */,
    "completed_conversations" INT NOT NULL DEFAULT 0 /* 完成的对话数 */,
    "failed_conversations" INT NOT NULL DEFAULT 0 /* 失败的对话数 */,
    "total_files_uploaded" INT NOT NULL DEFAULT 0 /* 上传文件总数 */,
    "total_file_size" BIGINT NOT NULL DEFAULT 0 /* 文件总大小 */,
    "total_feedbacks" INT NOT NULL DEFAULT 0 /* 反馈总数 */,
    "avg_rounds" REAL NOT NULL DEFAULT 0 /* 平均轮次 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */,
    CONSTRAINT "uid_testcase_st_date_bdcbc7" UNIQUE ("date")
) /* 测试用例生成统计 */;
CREATE TABLE IF NOT EXISTS "testcase_templates" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "name" VARCHAR(200) NOT NULL /* 模板名称 */,
    "description" TEXT /* 模板描述 */,
    "category" VARCHAR(100) NOT NULL /* 模板分类 */,
    "template_content" TEXT NOT NULL /* 模板内容 */,
    "prompt_template" TEXT /* 提示词模板 */,
    "is_active" INT NOT NULL DEFAULT 1 /* 是否启用 */,
    "is_default" INT NOT NULL DEFAULT 0 /* 是否为默认模板 */,
    "sort_order" INT NOT NULL DEFAULT 0 /* 排序 */,
    "usage_count" INT NOT NULL DEFAULT 0 /* 使用次数 */,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 创建时间 */,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP /* 更新时间 */
) /* 测试用例模板 */;
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
