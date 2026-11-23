FROM python:3.12-slim-bookworm

ENV UV_LINK_MODE=copy \
    MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git make pandoc latexmk \
       texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
       texlive-publishers texlive-bibtex-extra \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

WORKDIR /work
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# HiGHS is installed from the highspy wheel pinned by version and hash in uv.lock
RUN uv sync --frozen --extra dev
ENV PATH="/work/.venv/bin:${PATH}"

COPY . .
CMD ["make", "quick"]
