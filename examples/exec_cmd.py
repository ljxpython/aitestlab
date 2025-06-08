"""

autogen core 执行脚本的方式有三种:
1. 系统直接执行脚本
2. docker
3. 本地虚拟环境的方式

"""

import logging
import venv
from pathlib import Path

from autogen_core import EVENT_LOGGER_NAME, TRACE_LOGGER_NAME, CancellationToken
from autogen_core.code_executor import CodeBlock
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from loguru import logger

# import requests

work_dir = Path("coding")
logger.info(f"work_dir: {work_dir}")
script_path = Path("script")
work_dir.mkdir(exist_ok=True)


async def main(language: str = "python", code: str = "print('Hello, World!')"):

    async with DockerCommandLineCodeExecutor(work_dir=work_dir) as executor:  # type: ignore
        print(
            await executor.execute_code_blocks(
                code_blocks=[
                    CodeBlock(language=language, code=code),
                ],
                cancellation_token=CancellationToken(),
            )
        )


async def main2(language: str = "python", code: str = "print('Hello, World!')"):
    local_executor = LocalCommandLineCodeExecutor(work_dir=work_dir)
    print(
        await local_executor.execute_code_blocks(
            code_blocks=[
                CodeBlock(language=language, code=code),
            ],
            cancellation_token=CancellationToken(),
        )
    )


async def main3(language: str = "python", code: str = "print('Hello, World!')"):
    venv_dir = work_dir / ".venv"
    venv_builder = venv.EnvBuilder(with_pip=True)
    venv_builder.create(venv_dir)
    venv_context = venv_builder.ensure_directories(venv_dir)
    local_executor = LocalCommandLineCodeExecutor(
        work_dir=work_dir, virtual_env_context=venv_context
    )
    resp = await local_executor.execute_code_blocks(
        code_blocks=[
            CodeBlock(language=language, code=code),
        ],
        cancellation_token=CancellationToken(),
    )
    print(resp)


if __name__ == "__main__":
    import asyncio

    # asyncio.run(main(language="shell",code=f"pwd && ls"))
    # asyncio.run(main(language="shell",code=f"python test.py"))
    # asyncio.run(main(language="shell",code=f"python test_api.py"))
    # asyncio.run(main(language="shell",code=f"pip install requests && pip list | grep requests "))
    # asyncio.run(main(language="python",code=f"import requests;print(requests.get('https://www.baidu.com').text)"))
    # asyncio.run(main(language="shell",code=f"python --version"))
    # asyncio.run(main2(language="shell",code=f"python --version&&which python"))
    test_file = "test_script.py"
    url = "127.0.0.1:8001"
    pytest_cmd = f'python -m pytest "{test_file}" '
    # pytest_cmd = f'export  '
    pytest_cmd += "-v --html=report.html --json-report --json-report-file=report.json "
    pytest_cmd += "--alluredir=./allure-results"
    pytest_cmd += f' --base-url="{url}"'
    logger.info(pytest_cmd)
    # asyncio.run(main3(language="bash",code="pip list | wc -l"))
    # asyncio.run(main2(language="bash",code="pip list | wc -l"))
