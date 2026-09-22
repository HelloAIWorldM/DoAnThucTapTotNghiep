import sys
import json
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
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

def create_pooled_session():
    """Tạo requests.Session dùng chung với Connection Pool để tái sử dụng TCP/TLS connection"""
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

class MovieChatbot:
    def __init__(self, groq_api_key=None, tmdb_api_key=None, gemini_api_key=None):
        self.tmdb_key = tmdb_api_key
        self.groq_key = groq_api_key
        self.gemini_key = gemini_api_key
        self.model = "qwen/qwen3.8-27b"
        self.gemini_model = "gemini-3.5-flash-lite"
        self.is_active = False
        self.client = None

        # Khởi tạo HTTP Session dùng chung với Connection Pool
        self.session = create_pooled_session()

        # Bộ nhớ đệm In-Memory Caches để tăng tốc độ phản hồi 0ms
        self._cache_search = {}
        self._cache_recommendations = {}
        self._cache_studios = {}
        self._cache_person = {}
        self._cache_discover = {}
        self._cache_trailer = {}
        self._cache_mal = {}

        if self.gemini_key and self.gemini_key.strip():
            self.is_active = True
            print(f"[INFO] Google Gemini client enabled as primary model: {self.gemini_model}")

        if Groq is not None and groq_api_key and groq_api_key.strip():
            try:
                self.client = Groq(api_key=groq_api_key)
                self.is_active = True
                print(f"[INFO] Groq client initialized successfully with model: {self.model} (Fallback)")
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

        # Bản đồ hãng phim / vũ trụ điện ảnh sang TMDB Company ID
        self.studios_map = {
            # Marvel Cinematic Universe (MCU)
            'marvel': 420,
            'mcu': 420,
            'vũ trụ marvel': 420,
            'vu tru marvel': 420,
            'marvel studios': 420,
            'marvel cinematic universe': 420,
            # DC Universe
            'dc': 128064,
            'dceu': 128064,
            'vũ trụ dc': 128064,
            'vu tru dc': 128064,
            'dc studios': 128064,
            'dc comics': 9993,
            # Disney & Pixar
            'disney': 2,
            'walt disney': 2,
            'disney animation': 6125,
            'pixar': 3,
            # Anime & Studio hoạt hình danh tiếng
            'ghibli': 10342,
            'studio ghibli': 10342,
            'dreamworks': 521,
            'illumination': 3341,
            # Các hãng phim lớn khác
            'warner bros': 174,
            'warner': 174,
            'universal': 33,
            'universal pictures': 33,
            'sony': 5,
            'sony pictures': 5,
            'paramount': 4,
            'paramount pictures': 4,
            '20th century': 127928,
            'lucasfilm': 1,
            'a24': 41077,
            'netflix': 178464,
        }

        # Bản đồ từ khóa chủ đề sang TMDB Keyword ID
        self.keywords_map = {
            'siêu anh hùng': 9715,
            'sieu anh hung': 9715,
            'superhero': 9715,
            'zombie': 12377,
            'xác sống': 12377,
            'xac song': 12377,
            'quái vật': 1299,
            'quai vat': 1299,
            'vũ trụ': 9882,
            'space': 9882,
            'người ngoài hành tinh': 9951,
            'alien': 9951,
            'du hành thời gian': 4379,
            'time travel': 4379,
            'trí tuệ nhân tạo': 310,
            'ai': 310,
            'robot': 14544,
            'sát thủ': 10714,
            'assassin': 10714,
            'ma cà rồng': 3133,
            'vampire': 3133,
            'phép thuật': 2343,
            'magic': 2343,
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
        """Tìm phim theo tiêu đề trên TMDB, ưu tiên khớp chính xác và độ phổ biến (có cache)"""
        try:
            clean_query = title.strip().lower()
            if clean_query in self._cache_search:
                return self._cache_search[clean_query]

            url = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_key}&query={title}&language=vi-VN"
            res = self.session.get(url, timeout=5).json()
            results = res.get('results', [])
            if not results:
                # Fallback search tiếng Anh nếu tiếng Việt không có
                url_en = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_key}&query={title}&language=en-US"
                results = self.session.get(url_en, timeout=5).json().get('results', [])

            if results:
                # Ưu tiên: 1. Khớp chính xác tiêu đề tiếng Việt hoặc tiếng Anh -> 2. Có ảnh poster -> 3. Số lượt bình chọn vote_count
                def rank_movie(m):
                    t = (m.get('title') or '').strip().lower()
                    ot = (m.get('original_title') or '').strip().lower()
                    is_exact = 1 if (t == clean_query or ot == clean_query) else 0
                    has_poster = 1 if m.get('poster_path') else 0
                    vote_cnt = m.get('vote_count', 0)
                    pop = m.get('popularity', 0)
                    return (is_exact, has_poster, vote_cnt, pop)

                results.sort(key=rank_movie, reverse=True)

            if len(self._cache_search) < 200:
                self._cache_search[clean_query] = results
            return results
        except Exception as e:
            print(f"[TMDB] search_movie error: {e}")
            return []

    def get_movie_recommendations(self, movie_title):
        """Lấy danh sách phim tương tự từ một tên phim (có cache)"""
        try:
            clean_title = movie_title.strip().lower()
            if clean_title in self._cache_recommendations:
                return self._cache_recommendations[clean_title]

            results = self.search_movie(movie_title)
            if not results:
                return [], None
            target = results[0]
            target_id = target['id']
            target_name = target.get('title') or target.get('original_title')
            orig_title = target.get('original_title')
            display_target = f"{target_name} ({orig_title})" if orig_title and orig_title.lower() != target_name.lower() else target_name

            # Thử lấy recommendations
            rec_url = f"https://api.themoviedb.org/3/movie/{target_id}/recommendations?api_key={self.tmdb_key}&language=vi-VN"
            rec_res = self.session.get(rec_url, timeout=5).json().get('results', [])

            # Nếu ít hơn 3 phim, lấy thêm từ endpoint similar
            if len(rec_res) < 3:
                sim_url = f"https://api.themoviedb.org/3/movie/{target_id}/similar?api_key={self.tmdb_key}&language=vi-VN"
                rec_res += self.session.get(sim_url, timeout=5).json().get('results', [])

            filtered = [m for m in rec_res if m.get('poster_path') and m.get('vote_average', 0) > 4.5]
            titles = [m['title'] for m in filtered[:5]]
            res_tuple = (titles, display_target)
            if len(self._cache_recommendations) < 200:
                self._cache_recommendations[clean_title] = res_tuple
            return res_tuple
        except Exception as e:
            print(f"[TMDB] get_movie_recommendations error: {e}")
            return [], None

    def get_movies_by_person(self, person_name):
        """Tìm phim theo diễn viên hoặc đạo diễn (có cache)"""
        try:
            clean_person = person_name.strip().lower()
            if clean_person in self._cache_person:
                return self._cache_person[clean_person]

            search_url = f"https://api.themoviedb.org/3/search/person?api_key={self.tmdb_key}&query={person_name}&language=vi-VN"
            res = self.session.get(search_url, timeout=5).json()
            results = res.get('results', [])
            if not results:
                return [], None

            person = results[0]
            person_id = person['id']
            person_official_name = person.get('name', person_name)

            # Lấy credits phim của nhân vật đó
            credits_url = f"https://api.themoviedb.org/3/person/{person_id}/movie_credits?api_key={self.tmdb_key}&language=vi-VN"
            cred_res = self.session.get(credits_url, timeout=5).json()

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
            res_tuple = (titles, person_official_name)
            if len(self._cache_person) < 200:
                self._cache_person[clean_person] = res_tuple
            return res_tuple
        except Exception as e:
            print(f"[TMDB] get_movies_by_person error: {e}")
            return [], None

    def get_movies_by_studio(self, studio_name):
        """Lấy danh sách tác phẩm kinh điển, điểm cao của một hãng phim / vũ trụ điện ảnh (có cache)"""
        try:
            clean_name = studio_name.lower().strip()
            if clean_name in self._cache_studios:
                return self._cache_studios[clean_name]

            company_id = self.studios_map.get(clean_name)
            official_name = studio_name

            if not company_id:
                # Tìm kiếm công ty trên TMDB nếu chưa có trong map
                search_url = f"https://api.themoviedb.org/3/search/company?api_key={self.tmdb_key}&query={studio_name}"
                c_res = self.session.get(search_url, timeout=5).json().get('results', [])
                if c_res:
                    company_id = c_res[0]['id']
                    official_name = c_res[0].get('name', studio_name)

            if not company_id:
                return [], studio_name

            # Ưu tiên lấy theo vote_count.desc để ra các phim kinh điển, nổi tiếng nhất (như Iron Man, Avengers, The Dark Knight)
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={self.tmdb_key}&with_companies={company_id}&sort_by=vote_count.desc&vote_count.gte=100&language=vi-VN"
            res = self.session.get(url, timeout=5).json().get('results', [])

            if not res or len(res) < 3:
                # Fallback nếu vote_count quá cao ít kết quả
                url_pop = f"https://api.themoviedb.org/3/discover/movie?api_key={self.tmdb_key}&with_companies={company_id}&sort_by=popularity.desc&vote_count.gte=30&language=vi-VN"
                res += self.session.get(url_pop, timeout=5).json().get('results', [])

            seen_ids = set()
            filtered = []
            for m in res:
                mid = m.get('id')
                if mid and mid not in seen_ids and m.get('poster_path') and m.get('vote_average', 0) > 5.0:
                    seen_ids.add(mid)
                    filtered.append(m)

            titles = [(m.get('title') or m.get('original_title')) for m in filtered[:6]]
            clean_res = [t for t in titles if t]
            res_tuple = (clean_res, official_name)
            if len(self._cache_studios) < 200:
                self._cache_studios[clean_name] = res_tuple
            return res_tuple
        except Exception as e:
            print(f"[TMDB] get_movies_by_studio error: {e}")
            return [], studio_name

    def discover_movies(self, genre_keyword=None, year=None, country=None):
        """Khám phá phim theo thể loại, năm hoặc quốc gia (có cache)"""
        try:
            cache_key = f"{genre_keyword}_{year}_{country}".lower()
            if cache_key in self._cache_discover:
                return self._cache_discover[cache_key]

            params = {
                'api_key': self.tmdb_key,
                'sort_by': 'popularity.desc',
                'vote_count.gte': 50,
                'language': 'vi-VN',
                'page': 1
            }

            if genre_keyword:
                clean_g = genre_keyword.lower().strip()
                # 1. Kiểm tra nếu là studio / vũ trụ điện ảnh
                if clean_g in self.studios_map:
                    studio_movies, _ = self.get_movies_by_studio(clean_g)
                    if studio_movies:
                        return studio_movies

                # 2. Kiểm tra nếu là thể loại chuẩn
                gid = self.genres_map.get(clean_g)
                if gid:
                    params['with_genres'] = gid
                # 3. Kiểm tra nếu là từ khóa chủ đề (siêu anh hùng, zombie...)
                elif clean_g in self.keywords_map:
                    params['with_keywords'] = self.keywords_map[clean_g]
                else:
                    # Nếu từ khóa không nằm trong bất kỳ danh mục nào, tìm trực tiếp qua search_movie
                    search_res = self.search_movie(genre_keyword)
                    if search_res:
                        return [m['title'] for m in search_res[:5] if m.get('poster_path')]
                    return []

            if year and str(year).isdigit():
                params['primary_release_year'] = int(year)

            if country:
                lang_code = self.languages_map.get(country.lower().strip())
                if lang_code:
                    params['with_original_language'] = lang_code

            url = "https://api.themoviedb.org/3/discover/movie"
            res = self.session.get(url, params=params, timeout=5).json()
            results = res.get('results', [])

            filtered = [m for m in results if m.get('poster_path') and m.get('vote_average', 0) > 5.0]
            titles = [(m.get('title') or m.get('original_title')) for m in filtered[:8]]
            clean_res = [t for t in titles if t]
            if len(self._cache_discover) < 200:
                self._cache_discover[cache_key] = clean_res
            return clean_res
        except Exception as e:
            print(f"[TMDB] discover_movies error: {e}")
            return []

    def get_random_movie(self):
        """Bốc ngẫu nhiên một phim đánh giá cao (Hôm nay xem gì)"""
        try:
            # Lấy ngẫu nhiên từ top_rated hoặc trending
            page = random.randint(1, 5)
            url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={self.tmdb_key}&language=vi-VN&page={page}"
            res = self.session.get(url, timeout=5).json()
            results = res.get('results', [])
            valid_movies = [m for m in results if m.get('poster_path') and m.get('overview')]
            if valid_movies:
                chosen = random.choice(valid_movies[:10])
                return [chosen['title']]
        except Exception as e:
            print(f"[TMDB] get_random_movie error: {e}")
        return ["Inception"]

    def get_movie_trailer(self, movie_id):
        """Lấy key YouTube Trailer của phim từ TMDB (có cache)"""
        try:
            if movie_id in self._cache_trailer:
                return self._cache_trailer[movie_id]

            # Thử lấy trailer tiếng Việt
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.tmdb_key}&language=vi-VN"
            res = self.session.get(url, timeout=5).json().get('results', [])

            # Nếu không có video tiếng Việt, thử tiếng Anh (phần lớn trailer lưu ở en-US)
            if not res:
                url_en = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.tmdb_key}&language=en-US"
                res = self.session.get(url_en, timeout=5).json().get('results', [])

            youtube_videos = [v for v in res if v.get('site') == 'YouTube']
            # Ưu tiên type='Trailer', sau đó 'Teaser'
            trailers = [v for v in youtube_videos if v.get('type') == 'Trailer']
            trailer_key = None
            if trailers:
                # Ưu tiên trailer chính thức (official=True)
                official = [v for v in trailers if v.get('official') is True]
                trailer_key = official[0]['key'] if official else trailers[0]['key']
            elif youtube_videos:
                trailer_key = youtube_videos[0]['key']

            if trailer_key and len(self._cache_trailer) < 300:
                self._cache_trailer[movie_id] = trailer_key
            return trailer_key
        except Exception as e:
            print(f"[TMDB] get_movie_trailer error: {e}")
        return None

    # ================= VIDLINK / STREAMING SERVICES =================
    def get_mal_id(self, anime_title):
        """Tìm kiếm ID trên MyAnimeList (MAL) từ tên Anime (có cache)"""
        try:
            clean_title = str(anime_title).strip()
            cache_key = clean_title.lower()
            if cache_key in self._cache_mal:
                return self._cache_mal[cache_key]

            # Sử dụng MyAnimeList prefix search API nhanh và chính xác
            url = f"https://myanimelist.net/search/prefix.json?type=anime&keyword={clean_title}&v=1"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            res = self.session.get(url, headers=headers, timeout=5).json()
            items = res.get('categories', [{}])[0].get('items', [])
            if items:
                res_tuple = (items[0]['id'], items[0].get('name', clean_title))
                if len(self._cache_mal) < 300:
                    self._cache_mal[cache_key] = res_tuple
                return res_tuple
        except Exception as e:
            print(f"[MAL] get_mal_id error for '{anime_title}': {e}")
        return None, None

    def get_vidlink_anime_url(self, anime_title_or_mal_id, episode=1, sub_or_dub="sub"):
        """Tạo đường dẫn nhúng iframe Anime Vidlink: https://vidlink.pro/anime/{MALid}/{number}/{subOrDub}?fallback=true&autoplay=false"""
        try:
            mal_id = None
            if str(anime_title_or_mal_id).isdigit():
                mal_id = str(anime_title_or_mal_id)
            else:
                found_id, _ = self.get_mal_id(str(anime_title_or_mal_id))
                if found_id:
                    mal_id = str(found_id)

            if mal_id:
                return f"https://vidlink.pro/anime/{mal_id}/{episode}/{sub_or_dub}?fallback=true&autoplay=false"
        except Exception as e:
            print(f"[VIDLINK] get_vidlink_anime_url error: {e}")
        return None

    def get_vidlink_movie_url(self, tmdb_id):
        """Tạo đường dẫn nhúng iframe Phim Vidlink với autoplay=false: https://vidlink.pro/movie/{tmdbId}?autoplay=false"""
        if tmdb_id:
            return f"https://vidlink.pro/movie/{tmdb_id}?autoplay=false"
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
  "intent_type": "studio" | "person" | "similar" | "genre" | "random" | "search_movie" | "chat",
  "studio": "hãng phim hoặc vũ trụ điện ảnh (ví dụ: Marvel, MCU, DC, Disney, Pixar, Ghibli, Warner Bros...) hoặc null",
  "movie_title": "tên phim hoặc nhân vật chính (ví dụ: Iron Man, Batman, Thanos, Zootopia) hoặc null",
  "person": "tên diễn viên hoặc đạo diễn hoặc null",
  "genre": "thể loại phim hoặc chủ đề (ví dụ: hành động, siêu anh hùng, lãng mạn, kinh dị, hoạt hình, viễn tưởng...) hoặc null",
  "year": "năm hoặc null",
  "country": "quốc gia (ví dụ: hàn quốc, nhật bản, việt nam, mỹ, trung quốc...) hoặc null"
}}

Ví dụ:
- "Phim marvel" hoặc "Marvel" hoặc "Vũ trụ Marvel" -> {{"intent_type": "studio", "studio": "Marvel", "movie_title": null, "person": null, "genre": null, "year": null, "country": null}}
- "Phim của hãng Pixar" hoặc "Phim hoạt hình Ghibli" -> {{"intent_type": "studio", "studio": "Pixar", "movie_title": null, "person": null, "genre": "hoạt hình", "year": null, "country": null}}
- "Phim của Tom Cruise" -> {{"intent_type": "person", "studio": null, "movie_title": null, "person": "Tom Cruise", "genre": null, "year": null, "country": null}}
- "Có phim nào giống Interstellar không" -> {{"intent_type": "similar", "studio": null, "movie_title": "Interstellar", "person": null, "genre": null, "year": null, "country": null}}
- "Gợi ý phim hoạt hình anime Nhật Bản" -> {{"intent_type": "genre", "studio": null, "movie_title": null, "person": null, "genre": "hoạt hình", "year": null, "country": "nhật bản"}}
- "Phim siêu anh hùng hay nhất" -> {{"intent_type": "genre", "studio": null, "movie_title": null, "person": null, "genre": "siêu anh hùng", "year": null, "country": null}}
- "Có phim nào liên quan đến Thanos không" -> {{"intent_type": "search_movie", "studio": "Marvel", "movie_title": "Thanos", "person": null, "genre": "siêu anh hùng", "year": null, "country": null}}
- "Hôm nay xem gì" hoặc "Chọn ngẫu nhiên cho tôi" -> {{"intent_type": "random", "studio": null, "movie_title": null, "person": null, "genre": null, "year": null, "country": null}}
- "Chào bạn" hoặc "Bạn là ai" -> {{"intent_type": "chat", "studio": null, "movie_title": null, "person": null, "genre": null, "year": null, "country": null}}
"""

            raw_response = None

            # 1. Ưu tiên phân tích qua Gemini
            if self.gemini_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
                    payload = {
                        "contents": [{"parts": [{"text": analysis_prompt}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200}
                    }
                    res = self.session.post(url, json=payload, timeout=8)
                    if res.status_code == 200:
                        res.encoding = 'utf-8'
                        data_json = res.json()
                        raw_response = data_json['candidates'][0]['content']['parts'][0]['text'].strip()
                except Exception as g_err:
                    print(f"[INTENT] Gemini intent error, fallback to Groq: {g_err}")

            # 2. Fallback sang Groq nếu Gemini không phản hồi
            if not raw_response and self.client:
                response = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": analysis_prompt}],
                    model=self.model,
                    temperature=0.1,
                    max_tokens=150
                ).choices[0].message.content.strip()
                raw_response = response

            if raw_response:
                cleaned_json = re.sub(r'^```json\s*', '', raw_response)
                cleaned_json = re.sub(r'\s*```$', '', cleaned_json).strip()
                data = json.loads(cleaned_json)
                return data
        except Exception as e:
            print(f"[INTENT] Intent extraction error: {e}")
            # Fallback đơn giản bằng từ khóa
            lower_text = user_input.lower()
            if any(w in lower_text for w in ["ngẫu nhiên", "xem gì", "surprise", "hôm nay xem"]):
                return {"intent_type": "random"}
            for s in self.studios_map.keys():
                if s in lower_text:
                    return {"intent_type": "studio", "studio": s}
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

            if intent_type == "studio" or intent.get("studio"):
                studio_kw = intent.get("studio") or user_input
                rec_movies, real_name = self.get_movies_by_studio(studio_kw)
                if rec_movies:
                    context = f"Dữ liệu TMDB xác nhận: Các siêu phẩm kinh điển và nổi tiếng nhất của {real_name}: {', '.join(rec_movies)}."

            elif intent_type == "person" and intent.get("person"):
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
                    if genre_kw: desc_parts.append(f"chủ đề {genre_kw}")
                    if country: desc_parts.append(f"quốc gia {country}")
                    if year: desc_parts.append(f"năm {year}")
                    desc = ", ".join(desc_parts) if desc_parts else "phổ biến"
                    context = f"Dữ liệu TMDB xác nhận: Phim {desc} được đánh giá cao: {', '.join(rec_movies)}."

            elif intent_type == "random":
                rec_movies = self.get_random_movie()
                if rec_movies:
                    context = f"Dữ liệu TMDB gợi ý ngẫu nhiên bộ phim xuất sắc: {', '.join(rec_movies)}."

            elif intent_type == "search_movie" and intent.get("movie_title"):
                movie_query = intent["movie_title"]
                # Nếu truy vấn tìm kiếm trùng với tên một studio (ví dụ 'marvel'), ưu tiên tìm theo studio
                if movie_query.lower().strip() in self.studios_map:
                    rec_movies, real_name = self.get_movies_by_studio(movie_query)
                    if rec_movies:
                        context = f"Dữ liệu TMDB xác nhận: Các siêu phẩm của {real_name}: {', '.join(rec_movies)}."
                else:
                    search_res = self.search_movie(movie_query)
                    # Lọc các kết quả có độ tin cậy cao
                    valid_res = [m for m in search_res if m.get('vote_count', 0) >= 20 or m.get('vote_average', 0) >= 5.0]
                    if valid_res:
                        rec_movies = [m['title'] for m in valid_res[:4]]
                        details_summary = [f"{m['title']} (tên gốc: {m.get('original_title', '')}, năm {m.get('release_date', 'N/A')[:4]})" for m in valid_res[:4]]
                        context = f"Dữ liệu TMDB xác nhận phim liên quan trong hệ thống: {'; '.join(details_summary)}."
                    elif intent.get("studio"):
                        # Nếu tìm nhân vật/từ khóa chưa ra phim riêng nhưng có studio liên kết (ví dụ: Thanos thuộc Marvel)
                        rec_movies, real_name = self.get_movies_by_studio(intent["studio"])
                        if rec_movies:
                            context = f"Dữ liệu TMDB xác nhận: Các tác phẩm nổi bật của {real_name} liên quan: {', '.join(rec_movies)}."

        except Exception as e:
            print(f"[CHAT] Context processing error: {e}")

        # Chuẩn bị system message với hướng dẫn chi tiết
        sys_msg = f"""Bạn là Movie Chat AI - Trợ lý tư vấn và khám phá điện ảnh thông minh, thân thiện và am hiểu phim ảnh sâu sắc.
{context}

THÔNG TIN QUAN TRỌNG VỀ VŨ TRỤ ĐIỆN ẢNH VÀ NHÂN VẬT:
- Với Vũ trụ Điện ảnh Marvel (MCU), các siêu anh hùng và biểu tượng kinh điển gồm: Iron Man (Người Sắt - Tony Stark), Captain America, Thor, Hulk (Người Khổng Lồ Xanh), Spider-Man (Người Nhện), Black Panther, Doctor Strange, Black Widow, và đại phản diện Thanos cùng biệt đội Avengers (Avengers: Infinity War, Avengers: Endgame...). Khi người dùng hỏi về Marvel, hãy luôn tập trung vào các siêu phẩm bom tấn cốt lõi của Marvel Cinematic Universe.
- Khi người dùng hỏi về một nhân vật siêu anh hùng hoặc phản diện (như Thanos, Hulk, Iron Man, Joker, Batman...), hãy giải thích ngắn gọn nhân vật đó xuất hiện trong những tác phẩm kinh điển nào và nhiệt tình giới thiệu các bộ phim đó.
- "Phi Vụ Động Trời" là tên tiếng Việt chính thức của phim hoạt hình Disney "Zootopia" (Judy Hopps và Nick Wilde), KHÔNG PHẢI là phim heist hay cướp ngân hàng.

THÔNG TIN QUAN TRỌNG VỀ TÍNH NĂNG HỆ THỐNG:
- Giao diện người dùng của hệ thống ĐÃ TÍCH HỢP SẴN tính năng phát Trailer YouTube trực tiếp và nút xem Trailer YouTube cho từng bộ phim.
- Khi người dùng yêu cầu xem trailer, tìm trailer hoặc nhắc đến "trailer", "youtube trailer": Bạn TUYỆT ĐỐI KHÔNG được từ chối hoặc nói rằng mình "không có khả năng truy cập YouTube / không phát được trailer". Hãy luôn nhiệt tình giới thiệu các bộ phim được yêu cầu và hướng dẫn người dùng bấm vào nút "Trailer" ngay dưới thẻ phim để xem video trực tiếp!

QUY TẮC PHẢN HỒI BẮT BUỘC:
1. Khi người dùng yêu cầu danh sách phim hoặc hỏi trailer: Luôn nhiệt tình giới thiệu các bộ phim nổi bật; trình bày súc tích, cô đọng (1-2 câu điểm nhấn cho mỗi phim) để câu trả lời luôn trọn vẹn và không bao giờ bị cắt ngắn dòng cuối.
2. Trong các đoạn văn và danh sách giới thiệu, viết tên phim bằng chữ in đậm thông thường (ví dụ **Inception**, **Phi Vụ Động Trời**). KHÔNG dùng dấu ngoặc nhọn < > trong các đoạn văn giới thiệu.
3. BẮT BUỘC: Khi người dùng tìm kiếm, hỏi trailer, hỏi về phim/phần phim cụ thể (kể cả phim đang sản xuất hoặc sắp ra mắt đã có trên TMDB), hoặc khi bạn gợi ý phim, BẮT BUỘC liệt kê danh sách tên các bộ phim được đề xuất vào MỘT thẻ duy nhất ở DÒNG CUỐI CÙNG theo định dạng: <Phim 1, Phim 2, Phim 3> để hệ thống tự động tải dữ liệu và hiển thị thẻ phim kèm video trailer, nút bấm xem trailer trực tiếp cho người dùng.
4. Ưu tiên sử dụng danh sách phim đã được kiểm chứng từ TMDB ở trên (nếu có) để đảm bảo thông tin chính xác 100%, không tự bịa tên phim.
5. Chỉ khi người dùng thuần túy chào hỏi (ví dụ: "chào bạn", "hello") mà không có ý định tìm hay hỏi phim gì thì mới không thêm thẻ <...>."""

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

        gemini_success = False

        # 1. Ưu tiên stream từ Google Gemini
        if self.gemini_key:
            try:
                gemini_contents = []
                if history:
                    for h in history[-6:]:
                        if h.get("role") and h.get("content"):
                            clean_h = re.sub(r'<.*?>', '', h["content"]).strip()
                            role = "user" if h["role"] == "user" else "model"
                            gemini_contents.append({
                                "role": role,
                                "parts": [{"text": clean_h}]
                            })
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": user_input}]
                })

                payload = {
                    "systemInstruction": {
                        "parts": [{"text": sys_msg}]
                    },
                    "contents": gemini_contents,
                    "generationConfig": {
                        "temperature": 0.6,
                        "maxOutputTokens": 1200
                    }
                }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:streamGenerateContent?key={self.gemini_key}&alt=sse"
                res = self.session.post(url, json=payload, stream=True, timeout=15)

                if res.status_code == 200:
                    for raw_line in res.iter_lines():
                        if not raw_line:
                            continue
                        try:
                            line = raw_line.decode('utf-8')
                        except UnicodeDecodeError:
                            line = raw_line.decode('utf-8', errors='replace')

                        if line.startswith('data:'):
                            try:
                                json_part = line[5:].strip()
                                if not json_part:
                                    continue
                                chunk = json.loads(json_part)
                                text = chunk['candidates'][0]['content']['parts'][0]['text']
                                if text:
                                    gemini_success = True
                                    yield text
                            except Exception:
                                pass
                else:
                    print(f"[GEMINI] Status {res.status_code}, switching to Groq fallback...")
            except Exception as e:
                print(f"[GEMINI STREAM ERROR] {e}, switching to Groq fallback...")

        # 2. Fallback sang Groq nếu Gemini chưa stream hoặc gặp lỗi
        if not gemini_success and self.client:
            try:
                stream = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    stream=True,
                    temperature=0.6,
                    max_tokens=1200
                )

                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            except Exception as e:
                yield f"\n\n[Lỗi tạo nội dung từ AI]: {str(e)}"