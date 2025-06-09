from pathlib import Path

from openai import OpenAI


def extract_text_from_llm(file_path) -> str:
    """
    提取文件中的文本
    :param file_path:
    :return:
    """
    client = OpenAI(
        api_key="sk-H8YxdNKxE6AZfzofW9H67EMMu541pO5x3G4tpp4lEM4SoT3A",
        base_url="https://api.moonshot.cn/v1",
    )
    file_object = client.files.create(file=Path(file_path), purpose="file-extract")
    file_content = client.files.content(file_id=file_object.id).json()
    return file_content.get("content")
