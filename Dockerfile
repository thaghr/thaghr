FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

COPY --from=builder /install /usr/local

# Non-root, standard practice for anything that'll eventually run as a Deployment
RUN useradd --create-home --uid 1000 thaghr
USER thaghr
WORKDIR /home/thaghr

EXPOSE 9090

ENTRYPOINT ["thaghr"]
CMD ["--help"]