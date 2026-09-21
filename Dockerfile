FROM python:3.11-slim

# Tạo người dùng non-root (UID 1000)
RUN useradd -m -u 1000 user

WORKDIR /app

# Cài đặt curl và dọn dẹp cache apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn
COPY . .

# Tạo sẵn thư mục .files và phân quyền toàn bộ thư mục /app cho user
RUN mkdir -p /app/.files && chown -R user:user /app /home/user

# Chuyển sang quyền user
USER user

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Expose các cổng thông dụng (Render dùng 10000, HF Spaces dùng 7860, Chainlit mặc định 8000)
EXPOSE 8000 7860 10000

# Khởi chạy Chainlit, tự động nhận cổng $PORT của Render (hoặc mặc định 8000)
CMD ["sh", "-c", "chainlit run app.py --host 0.0.0.0 --port ${PORT:-8000} --headless"]
