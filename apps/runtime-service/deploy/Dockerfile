FROM python:3.13-slim@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir "uv==0.9.9" \
    && uv pip install --system --no-cache-dir /app --no-deps \
    && uv pip install --system --no-cache-dir \
       "graphharbor==0.13.0.post20" \
       "graphharbor-runtime==0.13.0.post20" \
       "langchain[openai]>=1.2.10" \
       "langchain-community>=0.4.1" \
       "langchain-mcp-adapters>=0.2.1" \
       "langgraph==1.2.11" \
       "langgraph-sdk==0.4.3" \
       "deepagents>=0.4.4" \
       "langchain-deepseek>=1.0.1" \
       "fastapi>=0.133.1" \
       "uvicorn[standard]>=0.41.0" \
       "requests>=2.32.5" \
       "python-dotenv>=1.2.1" \
       "langchain-openai>=1.1.10" \
       "langfuse>=4.14,<5" \
       "langchain-pymupdf4llm>=0.5.0" \
       "pillow>=10.0.0" \
       "pymupdf4llm>=0.1.0,<0.2.0" \
       "pyjwt[crypto]>=2.10.1" \
       "opentelemetry-exporter-otlp-proto-http>=1.42.1,<2" \
    && rm -rf /root/.cache \
    && python -c "import importlib.metadata as m; assert m.version('graphharbor') == '0.13.0.post20'; assert m.version('graphharbor-runtime') == '0.13.0.post20'"

ENTRYPOINT ["graphharbor"]
