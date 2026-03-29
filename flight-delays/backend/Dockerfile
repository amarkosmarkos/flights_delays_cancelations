FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/models /app/data/bts
COPY . .
# Strip Windows CRLF so Linux can exec the script; invoke via sh to avoid shebang issues.
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh
CMD ["sh", "/app/entrypoint.sh"]
