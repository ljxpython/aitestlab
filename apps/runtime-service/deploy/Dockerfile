FROM langchain/langgraph-api:3.13@sha256:61ad2a5beb30020eecf05a5a8108bcaba7ed44cbebb570e565611e760f1e4a40

# Generated from ../langgraph.json with `langgraph dockerfile`; regenerate this
# file after production config changes. The pinned base image is intentional.

# -- Adding local package ./ --
ADD ./ /deps/runtime-service
# -- End of local package ./ --

# -- Installing all local dependencies --
RUN for dep in /deps/*; do \
        echo "Installing $dep"; \
        if [ -d "$dep" ]; then \
            (cd "$dep" && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .); \
        fi; \
    done
# -- End of local dependencies install --

ENV LANGGRAPH_AUTH='{"path": "/deps/runtime-service/src/runtime_service/auth/platform.py:auth", "openapi": {"securitySchemes": {"RuntimeBearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}, "security": [{"RuntimeBearer": []}]}}'
ENV LANGGRAPH_HTTP='{"app": "/deps/runtime-service/src/runtime_service/webapp.py:app"}'
ENV LANGSERVE_GRAPHS='{"reference_agent": {"path": "/deps/runtime-service/src/runtime_service/graphs/reference_agent.py:get_agent", "description": "R2 Runtime-aware create_agent reference service with explicit model resolution."}}'

# Keep env-file loading in compose/runtime config. This image only sets the
# graph/http registry and installs the app package.

# -- Ensure user deps didn't inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api
# -- End of ensuring user deps didn't inadvertently overwrite langgraph-api --

# -- Removing build deps from the final image --
RUN pip uninstall -y pip setuptools wheel
RUN rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/lib/python*/site-packages/setuptools* /usr/local/lib/python*/site-packages/wheel* \
    && find /usr/local/bin -name "pip*" -delete || true
RUN rm -rf /usr/lib/python*/site-packages/pip* /usr/lib/python*/site-packages/setuptools* /usr/lib/python*/site-packages/wheel* \
    && find /usr/bin -name "pip*" -delete || true
RUN uv pip uninstall --system pip setuptools wheel && rm /usr/bin/uv /usr/bin/uvx
