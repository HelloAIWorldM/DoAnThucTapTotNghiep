---
title: Movie Chat AI
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Movie Chat AI - Trợ Lý Khám Phá Điện Ảnh Thông Minh

> **Đề tài Thực tập tốt nghiệp**: Ứng dụng Trí tuệ Nhân tạo trong Tư vấn và Khám phá Điện ảnh Đa chiều.  
> **Công nghệ chính**: Chainlit - Groq LLM (Qwen 3.8 / Llama) - TMDB API - Python 3.10+

---

## 1. Giới thiệu Đề tài

**Movie Chat AI** là hệ thống chatbot hỗ trợ người dùng tìm kiếm, tra cứu và nhận gợi ý phim ảnh theo nhu cầu, sở thích hoặc tâm trạng.

Ứng dụng kết hợp giữa mô hình ngôn ngữ lớn và cơ sở dữ liệu phim ảnh trực tuyến:

1. **Lớp Hiểu Ngôn Ngữ và Ngữ Cảnh (LLM - Groq)**: Phân tích ý định tìm kiếm đa chiều (diễn viên, đạo diễn, thể loại, quốc gia, năm phát hành) và duy trì bộ nhớ ngữ cảnh hội thoại đa lượt (Multi-turn Conversation).
2. **Lớp Dữ Liệu Thời Gian Thực (The Movie Database - TMDB)**: Truy vấn dữ liệu thực tế về điểm đánh giá, thời lượng, tóm tắt nội dung, poster chất lượng cao và trailer video chính thức từ YouTube.

---

## 2. Các Tính Năng Chính

- **Trò chuyện Ngữ cảnh (Multi-turn Memory)**: Ghi nhớ các câu hỏi và bộ phim đã trao đổi trước đó để trả lời câu hỏi tiếp nối tự nhiên.
- **Tìm kiếm Đa chiều**:
  - Tìm theo diễn viên: _"Phim của Tom Cruise"_
  - Tìm theo đạo diễn: _"Các phim do Christopher Nolan đạo diễn"_
  - Tìm theo thể loại và quốc gia: _"Phim hoạt hình anime Nhật Bản", "Phim kinh dị Hàn Quốc"_
  - Tìm phim tương tự: _"Phim có phong cách giống Interstellar"_
- **Xem Trailer YouTube Trực Tiếp**: Tích hợp video player ngay trong khung chat.
- **Gợi ý Phim Tương Tự**: Nút thao tác nhanh giúp tiếp tục khám phá các tác phẩm tương đồng.
- **Gợi ý Ngẫu Nhiên**: Đề xuất một tác phẩm điện ảnh điểm cao khi người dùng chưa có lựa chọn cụ thể.
- **Tải dữ liệu Bất đồng bộ (Async Parallel Loading)**: Hiển thị nhanh chóng danh sách thẻ phim.

---

## 3. Hướng Dẫn Cài Đặt và Chạy Dự Án

### Yêu cầu tiên quyết

- Python 3.10 trở lên.
- API Key từ:
  - [Groq Console](https://console.groq.com/keys)
  - [The Movie Database (TMDB)](https://www.themoviedb.org/settings/api)

### Bước 1: Truy cập thư mục dự án

```bash
cd "Thực tập tốt nghiệp"
```

### Bước 2: Tạo môi trường ảo (khuyến nghị)

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows:
venv\Scripts\activate

# Kích hoạt trên macOS/Linux:
source venv/bin/activate
```

### Bước 3: Cài đặt các thư viện cần thiết

```bash
pip install -r requirements.txt
```

### Bước 4: Cấu hình API Key

Tạo file `.env` từ file mẫu `.env.example` hoặc chỉnh sửa trực tiếp:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
TMDB_API_KEY=your_tmdb_api_key_here
```

### Bước 5: Khởi chạy ứng dụng

```bash
chainlit run app.py -w
```

Ứng dụng sẽ mở tại địa chỉ: `http://localhost:8000`

---

## 4. Cấu Trúc Thư Mục Dự Án

```
├── .chainlit/           # Cấu hình Chainlit (theme, translations)
├── public/              # File tĩnh (CSS tùy chỉnh, theme.json)
│   ├── custom.css       # CSS giao diện, thẻ phim, nút bấm
│   └── theme.json       # Bảng màu chủ đạo của ứng dụng
├── .env                 # File chứa API Key (bảo mật, không commit)
├── .env.example         # File mẫu cấu hình API
├── .gitignore           # Bỏ qua file bảo mật, cache
├── app.py               # Giao diện Chainlit, quản lý session và render UI
├── chatbot.py           # Logic AI Groq, trích xuất Intent và kết nối TMDB API
├── chainlit.md          # Trang chào mừng giới thiệu đồ án
├── requirements.txt     # Danh sách thư viện Python phụ thuộc
└── README.md            # Tài liệu hướng dẫn sử dụng và báo cáo
```
