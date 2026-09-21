---
title: Movie Chat AI
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Movie Chat AI - Trợ Lý Khám Phá Điện Ảnh Thông Minh

> **Đề tài Thực tập tốt nghiệp**: Ứng dụng Trí tuệ Nhân tạo trong Tư vấn và Khám phá Điện ảnh Đa chiều.  
> **Trực tuyến (Live Demo)**: [https://moviechatai.onrender.com](https://moviechatai.onrender.com)  
> **Công nghệ cốt lõi**: Chainlit - Dual-Engine AI (Google Gemini & Groq) - TMDB API - Docker

---

## 1. Giới thiệu Đề tài

**Movie Chat AI** là hệ thống chatbot tư vấn điện ảnh thông minh, giúp người dùng dễ dàng tìm kiếm, khám phá các tác phẩm điện ảnh theo nhu cầu, sở thích, thể loại hoặc tâm trạng cá nhân.

Hệ thống được thiết kế theo kiến trúc phân lớp chuyên biệt:

1. **Lớp Xử lý Ngôn ngữ Tự nhiên Kép (Dual-Engine AI)**:
   - **Google Gemini (Primary Engine)**: Sử dụng mô hình `gemini-3.5-flash-lite` với khả năng thấu hiểu tiếng Việt vượt trội, ngữ điệu tự nhiên, phân tích ý định tìm kiếm chuẩn xác và tuân thủ các quy tắc hiển thị.
   - **Groq (Fallback Engine)**: Sử dụng mô hình `qwen/qwen3.8-27b` chạy trên chip LPU tốc độ cao làm nguồn dự phòng tự động khi đường truyền gặp sự cố.
2. **Lớp Dữ liệu Thực tế Thời gian thực (The Movie Database - TMDB API)**:
   - Tích hợp thuật toán xếp hạng đa tầng (`rank_movie`): ưu tiên khớp chính xác tên phim, có ảnh poster, lượt đánh giá (`vote_count`) và độ phổ biến (`popularity`).
   - Cung cấp đầy đủ thông tin: poster chất lượng cao, điểm đánh giá, năm ra mắt, thời lượng, thể loại, mô tả tóm tắt và key Trailer YouTube chính thức.
3. **Lớp Giao diện Người dùng (Chainlit UI & Custom CSS)**:
   - Hỗ trợ đầy đủ **Light / Dark Mode**.
   - Trình phát video YouTube Trailer trực tiếp trong khung chat.
   - Các nút thao tác nhanh 1-click (Xem trailer, Tìm phim tương tự, Gợi ý ngẫu nhiên).
   - Cơ chế bảo mật lọc chuỗi chống tấn công XSS (`html.escape`).

---

## 2. Các Tính Năng Nổi Bật

- **Bộ nhớ hội thoại đa lượt (Multi-turn Context Memory)**: Ghi nhớ các câu hỏi và bộ phim đã trao đổi trước đó để trả lời câu hỏi tiếp nối tự nhiên.
- **Phân tích Ý định Tìm kiếm Đa chiều (Multi-dimensional Intent Extraction)**:
  - Tìm theo diễn viên: _"Phim của Tom Cruise"_
  - Tìm theo đạo diễn: _"Các tác phẩm của Christopher Nolan"_
  - Tìm theo thể loại & quốc gia: _"Hoạt hình Trung Quốc", "Phim kinh dị Hàn Quốc"_
  - Tìm phim tương tự: _"Phim có phong cách giống Interstellar"_
  - Tìm kiếm phần phim tiếp theo: _"Zootopia 2 đâu", "Avatar 3 khi nào chiếu"_
- **Xem Trailer YouTube Trực Tiếp**: Tích hợp video player phát trailer trực tiếp ngay trong đoạn chat hoặc mở liên kết YouTube nhanh.
- **Thuật toán Xếp hạng Chống Nhầm lẫn TMDB**: Loại bỏ hoàn toàn tình trạng chọn nhầm các bản ghi giữ chỗ (placeholder) hoặc nhầm phần phim chưa phát hành.
- **Cơ chế Dự phòng Thẻ phim Thông minh (Smart Fallback)**: Tự động trích xuất các tên phim in đậm để render thẻ phim ngay cả khi AI bỏ sót thẻ cú pháp.
- **Tải dữ liệu Bất đồng bộ (Async Parallel Loading)**: Gọi song song nhiều API bằng `asyncio.gather` giúp tốc độ phản hồi cực nhanh.

---

## 3. Hướng Dẫn Cài Đặt và Chạy Dự Án

### Yêu cầu tiên quyết

- Python 3.10 trở lên.
- Các API Key miễn phí:
  - **Google Gemini API**: [Google AI Studio](https://aistudio.google.com)
  - **TMDB API**: [The Movie Database](https://www.themoviedb.org/settings/api)
  - **Groq API** *(tùy chọn dự phòng)*: [Groq Console](https://console.groq.com/keys)

### Bước 1: Clone kho lưu trữ và truy cập thư mục

```bash
git clone https://github.com/HelloAIWorldM/DoAnThucTapTotNghiep.git
cd DoAnThucTapTotNghiep
```

### Bước 2: Tạo và kích hoạt môi trường ảo

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows:
venv\Scripts\activate

# Kích hoạt trên macOS/Linux:
source venv/bin/activate
```

### Bước 3: Cài đặt các thư viện phụ thuộc

```bash
pip install -r requirements.txt
```

### Bước 4: Cấu hình biến môi trường

Tạo file `.env` tại thư mục gốc với nội dung:

```env
# Google Gemini API Key (Động cơ AI chính)
GEMINI_API_KEY=your_gemini_api_key_here

# Groq API Key (Động cơ AI dự phòng)
GROQ_API_KEY=your_groq_api_key_here

# TMDB API Key (Cơ sở dữ liệu phim)
TMDB_API_KEY=your_tmdb_api_key_here
```

### Bước 5: Khởi chạy ứng dụng

```bash
chainlit run app.py -w
```

Mở trình duyệt và truy cập: `http://localhost:8000`

---

## 4. Triển Khai Lên Cloud (Docker / Render)

Dự án đã được đóng gói sẵn trong file `Dockerfile` hỗ trợ chuẩn UTF-8 toàn diện:

```bash
# Build Docker image
docker build -t movie-chat-ai .

# Chạy Docker container
docker run -p 8000:8000 --env-file .env movie-chat-ai
```

Trên **Render.com**:
- Tạo một **Web Service** kết nối với GitHub repository.
- Chọn Runtime: **Docker**.
- Thêm các biến môi trường trong mục **Environment**: `GEMINI_API_KEY`, `GROQ_API_KEY`, `TMDB_API_KEY`.

---

## 5. Cấu Trúc Thư Mục

```
├── .chainlit/           # Cấu hình Chainlit (theme, translations, meta)
├── public/              # Tài nguyên tĩnh
│   ├── custom.css       # CSS tùy biến, thẻ card phim, giao diện Dark/Light
│   └── theme.json       # Bảng màu chủ đạo của ứng dụng
├── .env                 # File chứa API Key (bảo mật, được gitignore)
├── .env.example         # File mẫu cấu hình biến môi trường
├── .gitignore           # Danh sách bỏ qua git
├── Dockerfile           # Đóng gói container Docker với locale UTF-8
├── app.py               # Giao diện Chainlit, xử lý session và render HTML
├── chatbot.py           # Logic AI (Gemini & Groq), intent extraction, TMDB API
├── chainlit.md          # Banner giới thiệu khi mở ứng dụng
├── requirements.txt     # Danh sách thư viện Python phụ thuộc
└── README.md            # Tài liệu hướng dẫn và báo cáo đồ án
```
