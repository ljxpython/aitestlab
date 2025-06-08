"""
测试用例相关数据模型
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from tortoise import fields
from tortoise.models import Model


class TestCaseConversation(Model):
    """测试用例对话记录"""

    id = fields.UUIDField(pk=True)
    user_id = fields.IntField(null=True, description="用户ID")
    conversation_id = fields.CharField(
        max_length=255, unique=True, description="对话ID"
    )
    title = fields.CharField(max_length=500, null=True, description="对话标题")
    status = fields.CharField(
        max_length=50, default="active", description="状态: active, completed, failed"
    )
    round_number = fields.IntField(default=1, description="当前轮次")
    max_rounds = fields.IntField(default=3, description="最大轮次")

    # 输入内容
    text_content = fields.TextField(null=True, description="文本内容")
    files_info = fields.JSONField(null=True, description="文件信息")

    # 生成结果
    requirement_analysis = fields.TextField(null=True, description="需求分析结果")
    generated_testcases = fields.TextField(null=True, description="生成的测试用例")
    final_testcases = fields.TextField(null=True, description="最终测试用例")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    completed_at = fields.DatetimeField(null=True, description="完成时间")

    class Meta:
        table = "testcase_conversations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"TestCaseConversation({self.conversation_id})"

    @property
    def files_list(self) -> List[Dict[str, Any]]:
        """获取文件列表"""
        if self.files_info:
            return (
                json.loads(self.files_info)
                if isinstance(self.files_info, str)
                else self.files_info
            )
        return []

    def set_files_info(self, files: List[Dict[str, Any]]):
        """设置文件信息"""
        self.files_info = json.dumps(files, ensure_ascii=False) if files else None

    async def mark_completed(self):
        """标记为完成"""
        self.status = "completed"
        self.completed_at = datetime.now()
        await self.save()

    async def mark_failed(self):
        """标记为失败"""
        self.status = "failed"
        await self.save()


class TestCaseMessage(Model):
    """测试用例对话消息"""

    id = fields.UUIDField(pk=True)
    conversation = fields.ForeignKeyField(
        "models.TestCaseConversation", related_name="messages", description="所属对话"
    )

    # 消息内容
    content = fields.TextField(description="消息内容")
    agent_type = fields.CharField(max_length=50, description="智能体类型")
    agent_name = fields.CharField(max_length=100, description="智能体名称")
    round_number = fields.IntField(description="轮次")

    # 消息元数据
    message_type = fields.CharField(
        max_length=50, default="agent", description="消息类型: agent, user, system"
    )
    is_complete = fields.BooleanField(default=False, description="是否为完成消息")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "testcase_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"TestCaseMessage({self.agent_name}: {self.content[:50]}...)"


class TestCaseFeedback(Model):
    """用户反馈记录"""

    id = fields.UUIDField(pk=True)
    conversation = fields.ForeignKeyField(
        "models.TestCaseConversation", related_name="feedbacks", description="所属对话"
    )

    # 反馈内容
    feedback_content = fields.TextField(description="反馈内容")
    round_number = fields.IntField(description="反馈轮次")

    # 反馈前后的测试用例
    previous_testcases = fields.TextField(null=True, description="反馈前的测试用例")
    improved_testcases = fields.TextField(null=True, description="改进后的测试用例")

    # 反馈状态
    status = fields.CharField(
        max_length=50,
        default="processing",
        description="状态: processing, completed, failed",
    )

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "testcase_feedbacks"
        ordering = ["created_at"]

    def __str__(self):
        return f"TestCaseFeedback(Round {self.round_number}: {self.feedback_content[:50]}...)"


class TestCaseFile(Model):
    """上传的文件记录"""

    id = fields.UUIDField(pk=True)
    conversation = fields.ForeignKeyField(
        "models.TestCaseConversation", related_name="files", description="所属对话"
    )

    # 文件信息
    filename = fields.CharField(max_length=500, description="文件名")
    original_filename = fields.CharField(max_length=500, description="原始文件名")
    content_type = fields.CharField(max_length=200, description="文件类型")
    file_size = fields.BigIntField(description="文件大小")

    # 文件内容
    file_content = fields.TextField(null=True, description="文件内容(base64编码)")
    extracted_text = fields.TextField(null=True, description="提取的文本内容")

    # 文件状态
    status = fields.CharField(
        max_length=50,
        default="uploaded",
        description="状态: uploaded, processed, failed",
    )
    error_message = fields.TextField(null=True, description="错误信息")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "testcase_files"
        ordering = ["created_at"]

    def __str__(self):
        return f"TestCaseFile({self.filename})"

    async def mark_processed(self, extracted_text: str = None):
        """标记为已处理"""
        self.status = "processed"
        if extracted_text:
            self.extracted_text = extracted_text
        await self.save()

    async def mark_failed(self, error_message: str):
        """标记为失败"""
        self.status = "failed"
        self.error_message = error_message
        await self.save()


class TestCaseTemplate(Model):
    """测试用例模板"""

    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=200, description="模板名称")
    description = fields.TextField(null=True, description="模板描述")
    category = fields.CharField(max_length=100, description="模板分类")

    # 模板内容
    template_content = fields.TextField(description="模板内容")
    prompt_template = fields.TextField(null=True, description="提示词模板")

    # 模板配置
    is_active = fields.BooleanField(default=True, description="是否启用")
    is_default = fields.BooleanField(default=False, description="是否为默认模板")
    sort_order = fields.IntField(default=0, description="排序")

    # 使用统计
    usage_count = fields.IntField(default=0, description="使用次数")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "testcase_templates"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"TestCaseTemplate({self.name})"

    async def increment_usage(self):
        """增加使用次数"""
        self.usage_count += 1
        await self.save()


class TestCaseStatistics(Model):
    """测试用例生成统计"""

    id = fields.UUIDField(pk=True)
    date = fields.DateField(description="统计日期")

    # 生成统计
    total_conversations = fields.IntField(default=0, description="总对话数")
    completed_conversations = fields.IntField(default=0, description="完成的对话数")
    failed_conversations = fields.IntField(default=0, description="失败的对话数")

    # 文件统计
    total_files_uploaded = fields.IntField(default=0, description="上传文件总数")
    total_file_size = fields.BigIntField(default=0, description="文件总大小")

    # 反馈统计
    total_feedbacks = fields.IntField(default=0, description="反馈总数")
    avg_rounds = fields.FloatField(default=0.0, description="平均轮次")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "testcase_statistics"
        unique_together = ("date",)
        ordering = ["-date"]

    def __str__(self):
        return f"TestCaseStatistics({self.date})"
