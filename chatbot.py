import sys
import json
import re
import requests
import random

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from groq import Groq
except ImportError:
    Groq = None

class MovieChatbot:
    def __init__(self, groq_api_key, tmdb_api_key):
        self.tmdb_key = tmdb_api_key
        self.groq_key = groq_api_key
        self.model = "qwen/qwen3.8-27b"
        self.is_active = False

        if Groq is None:
            print("[WARNING] Thu vien 'groq' chua duoc cai dat. Vui long chay: pip install -r requirements.txt")
            return

        try:
            if groq_api_key and groq_api_key.strip():
                self.client = Groq(api_key=groq_api_key)
                self.model = "qwen/qwen3.8-27b"
                self.is_active = True
                print(f"[INFO] Groq client initialized successfully with model: {self.model}")
        except Exception as e:
            print(f"[ERROR] Groq client init failed: {e}")

        # Bản đồ thể loại tiếng Việt sang TMDB Genre ID
        self.genres_map = {
            'hành động': 28, 'hanh dong': 28,
            'phiêu lưu': 12, 'phieu luu': 12,
            'hoạt hình': 16, 'hoat hinh': 16, 'anime': 16,
            'hài': 35, 'hài hước': 35, 'hai huoc': 35,
            'tội phạm': 80, 'toi pham': 80,
            'tài liệu': 99, 'tai lieu': 99,
            'chính kịch': 18, 'chinh kich': 18, 'tâm lý': 18,
            'gia đình': 10751, 'gia dinh': 10751,
            'giả tưởng': 14, 'viễn tưởng': 14, 'fantasy': 14,
            'lịch sử': 36, 'lich su': 36,
            'kinh dị': 27, 'kinh di': 27, 'ma': 27,
            'nhạc': 10402, 'ca nhạc': 10402, 'âm nhạc': 10402,
            'bí ẩn': 9648, 'bi an': 9648, 'trinh thám': 9648,
            'lãng mạn': 10749, 'tình cảm': 10749, 'lang man': 10749, 'tinh cam': 10749,
            'khoa học viễn tưởng': 878, 'sci-fi': 878, 'khoa hoc vien tuong': 878,
            'gay cấn': 53, 'giật gân': 53, 'thriller': 53, 'hồi hộp': 53,
            'chiến tranh': 10752, 'chien tranh': 10752,
            'miền tây': 37, 'western': 37
        }

        # Bản đồ ngôn ngữ / quốc gia
        self.languages_map = {
            'hàn quốc': 'ko', 'hàn': 'ko', 'korea': 'ko',
            'nhật bản': 'ja', 'nhật': 'ja', 'japan': 'ja',
            'việt nam': 'vi', 'việt': 'vi', 'vietnam': 'vi',
            'trung quốc': 'zh', 'trung': 'zh', 'hồng kông': 'zh', 'hongkong': 'zh',
            'thái lan': 'th', 'thái': 'th',
            'mỹ': 'en', 'hollywood': 'en', 'anh': 'en', 'âu mỹ': 'en',
            'pháp': 'fr', 'tây ban nha': 'es'
        }

    # ================= TMDB API SERVICES =================
    def search_movie(self, title):
        """Tìm phim theo tiêu đề trên TMDB"""
        try:
            url = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_key}&query={title}&language=vi-VN"
            res = requests.get(url, timeout=5).json()
            results = res.get('results', [])
            if not results:
                # Fallback search tiếng Anh nếu tiếng Việt không có
                url_en = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_key}&query={title}&language=en-US"
                results = requests.get(url_en, timeout=5).json().get('results', [])
            return results
        except Exception as e:
            print(f"[TMDB] search_movie error: {e}")
            return []

    def get_movie_recommendations(self, movie_title):
        """Lấy danh sách phim tương tự từ một tên phim"""
        try:
            results = self.search_movie(movie_title)
            if not results:
                return [], None
            target = results[0]
            target_id = target['id']
            target_name = target.get('title') or target.get('original_title')

            # Thử lấy recommendations
            rec_url = f"https://api.themoviedb.org/3/movie/{target_id}/recommendations?api_key={self.tmdb_key}&language=vi-VN"
            rec_res = requests.get(rec_url, timeout=5).json().get('results', [])

            # Nếu ít hơn 3 phim, lấy thêm từ endpoint similar
            if len(rec_res) < 3:
                sim_url = f"https://api.themoviedb.org/3/movie/{target_id}/similar?api_key={self.tmdb_key}&language=vi-VN"
                rec_res += requests.get(sim_url, timeout=5).json().get('results', [])

            filtered = [m for m in rec_res if m.get('poster_path') and m.get('vote_average', 0) > 4.5]
            titles = [m['title'] for m in filtered[:5]]
            return titles, target_name
        except Exception as e:
            print(f"[TMDB] get_movie_recommendations error: {e}")
            return [], None

    def get_movies_by_person(self, person_name):
        """Tìm phim theo diễn viên hoặc đạo diễn"""
        try:
            search_url = f"https://api.themoviedb.org/3/search/person?api_key={self.tmdb_key}&query={person_name}&language=vi-VN"
            res = requests.get(search_url, timeout=5).json()
            results = res.get('results', [])
            if not results:
                return [], None

            person = results[0]
            person_id = person['id']
            person_official_name = person.get('name', person_name)

            # Lấy credits phim của nhân vật đó
            credits_url = f"https://api.themoviedb.org/3/person/{person_id}/movie_credits?api_key={self.tmdb_key}&language=vi-VN"
            cred_res = requests.get(credits_url, timeout=5).json()

            # Kết hợp cast và crew (nếu là đạo diễn)
            movies = cred_res.get('cast', []) + [c for c in cred_res.get('crew', []) if c.get('job') == 'Director']

            # Sắp xếp theo độ nổi tiếng & số lượt đánh giá
            movies.sort(key=lambda x: (x.get('vote_count', 0), x.get('popularity', 0)), reverse=True)

            # Lọc bỏ trùng lặp và phim thiếu poster
            seen_ids = set()
            filtered = []
            for m in movies:
                mid = m.get('id')
                if mid and mid not in seen_ids and m.get('poster_path') and m.get('vote_average', 0) > 5.0:
                    seen_ids.add(mid)
                    filtered.append(m)

            titles = [m.get('title') or m.get('original_title') for m in filtered[:5]]
            return titles, person_official_name
        except Exception as e:
            print(f"[TMDB] get_movies_by_person error: {e}")
            return [], None

    def discover_movies(self, genre_keyword=None, year=None, country=None):
        """Khám phá phim theo thể loại, năm hoặc quốc gia"""
        try:
            params = {
                'api_key': self.tmdb_key,
                'sort_by': 'popularity.desc',
                'vote_count.gte': 50,
                'language': 'vi-VN',
                'page': 1
            }

            if genre_keyword:
                gid = self.genres_map.get(genre_keyword.lower().strip())
                if gid:
                    params['with_genres'] = gid

            if year and str(year).isdigit():
                params['primary_release_year'] = int(year)

            if country:
                lang_code = self.languages_map.get(country.lower().strip())
                if lang_code:
                    params['with_original_language'] = lang_code

            url = "https://api.themoviedb.org/3/discover/movie"
            res = requests.get(url, params=params, timeout=5).json()
            results = res.get('results', [])

            filtered = [m for m in results if m.get('poster_path') and m.get('vote_average', 0) > 5.0]
            titles = [m['title'] for m in filtered[:5]]
            return titles
        except Exception as e:
            print(f"[TMDB] discover_movies error: {e}")
            return []

    def get_random_movie(self):
        """Bốc ngẫu nhiên một phim đánh giá cao (Hôm nay xem gì)"""
        try:
            # Lấy ngẫu nhiên từ top_rated hoặc trending
            page = random.randint(1, 5)
            url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={self.tmdb_key}&language=vi-VN&page={page}"
            res = requests.get(url, timeout=5).json()
            results = res.get('results', [])
            valid_movies = [m for m in results if m.get('poster_path') and m.get('overview')]
            if valid_movies:
                chosen = random.choice(valid_movies[:10])
                return [chosen['title']]
        except Exception as e:
            print(f"[TMDB] get_random_movie error: {e}")
        return ["Inception"]

    def get_movie_trailer(self, movie_id):
        """Lấy key YouTube Trailer của phim từ TMDB"""
        try:
            # Thử lấy trailer tiếng Việt
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.tmdb_key}&language=vi-VN"
            res = requests.get(url, timeout=5).json().get('results', [])

            # Nếu không có video tiếng Việt, thử tiếng Anh (phần lớn trailer lưu ở en-US)
            if not res:
                url_en = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.tmdb_key}&language=en-US"
                res = requests.get(url_en, timeout=5).json().get('results', [])

            youtube_videos = [v for v in res if v.get('site') == 'YouTube']
            # Ưu tiên type='Trailer', sau đó 'Teaser'
            trailers = [v for v in youtube_videos if v.get('type') == 'Trailer']
            if trailers:
                # Ưu tiên trailer chính thức (official=True)
                official = [v for v in trailers if v.get('official') is True]
                return official[0]['key'] if official else trailers[0]['key']
            elif youtube_videos:
                return youtube_videos[0]['key']
        except Exception as e:
            print(f"[TMDB] get_movie_trailer error: {e}")
        return None

    # ================= INTENT EXTRACTION =================
    def extract_intent(self, user_input, history=None):
        """Sử dụng Groq LLM để phân tích ý định tìm kiếm đa chiều"""
        try:
            # Trích xuất ngắn gọn ngữ cảnh hội thoại gần nhất nếu có
            recent_context = ""
            if history and len(history) > 1:
                last_turns = history[-3:]
                recent_context = "Ngữ cảnh gần nhất:\n" + "\n".join(
                    [f"{msg['role']}: {msg['content'][:120]}" for msg in last_turns if msg.get('content')]
                )

            analysis_prompt = f"""Bạn là bộ trích xuất ý định tìm kiếm phim ảnh.
Hãy phân tích yêu cầu của người dùng và trả về DUY NHẤT một JSON hợp lệ (không kèm markdown ```json, không thêm bất kỳ chữ nào khác).

{recent_context}

Yêu cầu hiện tại: "{user_input}"

Cấu trúc JSON bắt buộc:
{{
  "intent_type": "person" | "similar" | "genre" | "random" | "search_movie" | "chat",
  "movie_title": "tên phim được nhắc tới hoặc null",
  "person": "tên diễn viên hoặc đạo diễn hoặc null",
  "genre": "thể loại phim (ví dụ: hành động, lãng mạn, kinh dị, hoạt hình, viễn tưởng...) hoặc null",
  "year": "năm hoặc null",
  "country": "quốc gia (ví dụ: hàn quốc, nhật bản, việt nam, mỹ, trung quốc...) hoặc null"
}}

Ví dụ:
- "Phim của Tom Cruise" -> {{"intent_type": "person", "movie_title": null, "person": "Tom Cruise", "genre": null, "year": null, "country": null}}
- "Có phim nào giống Interstellar không" -> {{"intent_type": "similar", "movie_title": "Interstellar", "person": null, "genre": null, "year": null, "country": null}}
- "Gợi ý phim hoạt hình anime Nhật Bản" -> {{"intent_type": "genre", "movie_title": null, "person": null, "genre": "hoạt hình", "year": null, "country": "nhật bản"}}
- "Hôm nay xem gì" hoặc "Chọn ngẫu nhiên cho tôi" -> {{"intent_type": "random", "movie_title": null, "person": null, "genre": null, "year": null, "country": null}}
- "Chào bạn" hoặc "Bạn là ai" -> {{"intent_type": "chat", "movie_title": null, "person": null, "genre": null, "year": null, "country": null}}
"""

            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": analysis_prompt}],
                model=self.model,
                temperature=0.1,
                max_tokens=150
            ).choices[0].message.content.strip()

            # Làm sạch chuỗi JSON nếu có bao quanh bởi markdown
            cleaned_json = re.sub(r'^```json\s*', '', response)
            cleaned_json = re.sub(r'\s*```$', '', cleaned_json).strip()
            data = json.loads(cleaned_json)
            return data
        except Exception as e:
            print(f"[INTENT] Intent extraction error: {e}")
            # Fallback đơn giản bằng từ khóa
            lower_text = user_input.lower()
            if any(w in lower_text for w in ["ngẫu nhiên", "xem gì", "surprise", "hôm nay xem"]):
                return {"intent_type": "random"}
            for g in self.genres_map.keys():
                if g in lower_text:
                    return {"intent_type": "genre", "genre": g}
            return {"intent_type": "chat"}

    # ================= CHAT STREAM =================
    def chat_stream(self, user_input, history=None):
        """Xử lý chat và stream câu trả lời kèm dữ liệu phim được xác thực từ TMDB"""
        if not self.is_active:
            yield "Không thể kết nối với Groq API. Vui lòng kiểm tra lại GROQ_API_KEY trong file `.env`."
            return

        rec_movies = []
        context = ""

        try:
            intent = self.extract_intent(user_input, history)
            intent_type = intent.get("intent_type", "chat")

            if intent_type == "person" and intent.get("person"):
                person_name = intent["person"]
                rec_movies, real_name = self.get_movies_by_person(person_name)
                if rec_movies:
                    context = f"Dữ liệu TMDB xác nhận: Các phim tiêu biểu của {real_name}: {', '.join(rec_movies)}."

            elif intent_type == "similar" and intent.get("movie_title"):
                target_title = intent["movie_title"]
                rec_movies, real_name = self.get_movie_recommendations(target_title)
                if rec_movies:
                    context = f"Dữ liệu TMDB xác nhận: Các phim tương tự như '{real_name}': {', '.join(rec_movies)}."

            elif intent_type == "genre":
                genre_kw = intent.get("genre")
                year = intent.get("year")
                country = intent.get("country")
                rec_movies = self.discover_movies(genre_kw, year, country)
                if rec_movies:
                    desc_parts = []
                    if genre_kw: desc_parts.append(f"thể loại {genre_kw}")
                    if country: desc_parts.append(f"quốc gia {country}")
                    if year: desc_parts.append(f"năm {year}")
                    desc = ", ".join(desc_parts) if desc_parts else "phổ biến"
                    context = f"Dữ liệu TMDB xác nhận: Phim {desc} được đánh giá cao: {', '.join(rec_movies)}."

            elif intent_type == "random":
                rec_movies = self.get_random_movie()
                if rec_movies:
                    context = f"Dữ liệu TMDB gợi ý ngẫu nhiên bộ phim xuất sắc: {', '.join(rec_movies)}."

            elif intent_type == "search_movie" and intent.get("movie_title"):
                search_res = self.search_movie(intent["movie_title"])
                if search_res:
                    rec_movies = [m['title'] for m in search_res[:3]]
                    context = f"Dữ liệu TMDB tìm thấy phim liên quan: {', '.join(rec_movies)}."

        except Exception as e:
            print(f"[CHAT] Context processing error: {e}")

        # Chuẩn bị system message với hướng dẫn chi tiết
        sys_msg = f"""Bạn là Movie Chat AI - Trợ lý tư vấn và khám phá điện ảnh thông minh, thân thiện và am hiểu phim ảnh sâu sắc.
{context}

QUY TẮC PHẢN HỒI QUAN TRỌNG:
1. Giao tiếp tự nhiên, hấp dẫn, ngắn gọn và có điểm nhấn (giới thiệu điểm cuốn hút của từng phim nếu có).
2. Trong các đoạn văn và danh sách giới thiệu, viết tên phim bằng chữ in đậm thông thường (ví dụ **Inception**, **Phi Vụ Động Trời**). KHÔNG dùng dấu ngoặc nhọn < > trong các đoạn văn giới thiệu.
3. BẮT BUỘC liệt kê danh sách tên các bộ phim được đề xuất vào MỘT thẻ duy nhất ở DÒNG CUỐI CÙNG của câu trả lời theo định dạng: <Phim 1, Phim 2, Phim 3>
4. Ưu tiên sử dụng danh sách phim đã được kiểm chứng từ TMDB ở trên (nếu có) để đảm bảo thông tin chính xác 100%, không tự bịa tên phim.
5. Nếu người dùng chỉ chào hỏi hoặc trò chuyện thông thường, hãy phản hồi nhiệt tình và không thêm thẻ <...> nếu không gợi ý phim."""

        # Chuẩn bị danh sách tin nhắn bao gồm lịch sử hội thoại
        messages = [{"role": "system", "content": sys_msg}]

        if history:
            # Thêm tối đa 6 lượt hội thoại gần nhất
            for h in history[-6:]:
                if h.get("role") in ["user", "assistant"] and h.get("content"):
                    # Lọc bỏ phần tag <...> khỏi lịch sử để không làm nhiễu prompt
                    clean_content = re.sub(r'<.*?>', '', h["content"]).strip()
                    messages.append({"role": h["role"], "content": clean_content})

        # Thêm câu hỏi hiện tại
        messages.append({"role": "user", "content": user_input})

        try:
            stream = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                stream=True,
                temperature=0.6,
                max_tokens=700
            )

            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            yield f"\n\n[Lỗi tạo nội dung từ AI]: {str(e)}"