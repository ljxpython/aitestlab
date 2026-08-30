FROM langchain/langgraph-api:3.13

# Repo-managed Dockerfile for runtime-service container delivery.
# This file is based on the current LangGraph dockerfile generation pattern,
# but is checked into the repo so end users can build without local CLI setup.

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

ENV LANGSERVE_GRAPHS='{"reference_agent": {"path": "/deps/runtime-service/src/runtime_service/graphs/reference_agent.py:get_agent", "description": "R0 reference create_agent service using a deterministic fake model."}}'

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
