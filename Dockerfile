FROM python:3.11-slim

# Tạo người dùng non-root theo tiêu chuẩn Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user

WORKDIR /home/user/app

# Cài đặt curl và dọn dẹp cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện phụ thuộc
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn vào container
COPY --chown=user:user . .

# Chuyển quyền thực thi sang user
USER user

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PORT=7860

# Hugging Face Spaces mặc định ánh xạ cổng 7860
EXPOSE 7860

# Khởi chạy Chainlit server
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "7860", "--headless"]
