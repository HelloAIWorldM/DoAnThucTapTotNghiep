import sys
import os
import re
import html
import urllib.parse
import asyncio
import requests
import chainlit as cl
from dotenv import load_dotenv
from chatbot import MovieChatbot

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# === NẠP CẤU HÌNH BIẾN MÔI TRƯỜNG ===
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = MovieChatbot(GROQ_API_KEY, TMDB_API_KEY, GEMINI_API_KEY)

# Bộ nhớ đệm In-Memory Cache lưu thông tin phim đã tra cứu (0ms latency cho các lượt xem lại)
MOVIE_INFO_CACHE = {}

def fetch_single_movie_info(title):
    """Lấy chi tiết một bộ phim từ TMDB với batching append_to_response và bộ nhớ đệm"""
    clean_key = title.strip().lower()
    if clean_key in MOVIE_INFO_CACHE:
        return MOVIE_INFO_CACHE[clean_key]

    try:
        session = bot.session
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}&language=vi-VN"
        response = session.get(search_url, timeout=5)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if not results:
                # Fallback search tiếng Anh
                search_url_en = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}&language=en-US"
                results = session.get(search_url_en, timeout=5).json().get('results', [])

            if results:
                # Ưu tiên khớp chính xác tên phim và phim có nhiều lượt đánh giá nhất (tránh nhầm các phần phim placeholder)
                clean_query = clean_key
                def rank_movie(m):
                    t = (m.get('title') or '').strip().lower()
                    ot = (m.get('original_title') or '').strip().lower()
                    is_exact = 1 if (t == clean_query or ot == clean_query) else 0
                    has_poster = 1 if m.get('poster_path') else 0
                    vote_cnt = m.get('vote_count', 0)
                    pop = m.get('popularity', 0)
                    return (is_exact, has_poster, vote_cnt, pop)

                results.sort(key=rank_movie, reverse=True)
                data = results[0]

                movie_id = data.get('id')
                poster_path = data.get('poster_path')
                # Tối ưu kích thước poster sang w342 (sắc nét Retina cho khung 160px, giảm 50% dung lượng tải)
                poster_url = f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else "https://placehold.co/342x513/1e293b/ffffff?text=No+Poster"
                year = data.get('release_date', 'N/A')[:4]
                rating = round(data.get('vote_average', 0), 1)

                # Gom chi tiết (thời lượng, thể loại, tóm tắt) và video trailer trong 1 request duy nhất với append_to_response!
                detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=vi-VN&append_to_response=videos&include_video_language=vi,en"
                detail_res = session.get(detail_url, timeout=5).json()

                genres = [g['name'] for g in detail_res.get('genres', [])[:3]]
                runtime = detail_res.get('runtime')
                runtime_str = f"{runtime} phút" if runtime else None

                overview = detail_res.get('overview') or data.get('overview')
                if not overview:
                    # Fallback overview tiếng Anh nếu tiếng Việt rỗng
                    detail_en = session.get(f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US", timeout=5).json()
                    overview = detail_en.get('overview', 'Chưa có mô tả nội dung.')

                # Trích xuất trailer key YouTube trực tiếp từ kết quả append_to_response (không cần thêm request ngoài)
                trailer_key = None
                videos_res = detail_res.get('videos', {}).get('results', [])
                if videos_res:
                    yt_videos = [v for v in videos_res if v.get('site') == 'YouTube']
                    trailers = [v for v in yt_videos if v.get('type') == 'Trailer']
                    if trailers:
                        official = [v for v in trailers if v.get('official') is True]
                        trailer_key = official[0]['key'] if official else trailers[0]['key']
                    elif yt_videos:
                        trailer_key = yt_videos[0]['key']

                # Nếu chưa tìm thấy trailer, dùng hàm dự phòng từ bot
                if not trailer_key and movie_id:
                    trailer_key = bot.get_movie_trailer(movie_id)

                link_tmdb = f"https://www.themoviedb.org/movie/{movie_id}"
                movie_name = data.get('title') or title
                link_search = f"https://www.google.com/search?q=xem+phim+{urllib.parse.quote_plus(movie_name)}+vietsub"

                movie_info = {
                    "id": movie_id,
                    "title": movie_name,
                    "poster": poster_url,
                    "overview": overview,
                    "year": year,
                    "rating": rating,
                    "runtime": runtime_str,
                    "genres": genres,
                    "trailer_key": trailer_key,
                    "link_tmdb": link_tmdb,
                    "link_search": link_search
                }

                # Lưu vào cache in-memory
                if len(MOVIE_INFO_CACHE) < 300:
                    MOVIE_INFO_CACHE[clean_key] = movie_info
                    if movie_name:
                        MOVIE_INFO_CACHE[movie_name.strip().lower()] = movie_info

                return movie_info
    except Exception as e:
        print(f"[ERROR] Failed to fetch movie '{title}': {e}")
    return None

async def get_all_movies_details(movie_titles):
    """Lấy song song thông tin của nhiều phim để tăng tốc độ tải"""
    tasks = [asyncio.to_thread(fetch_single_movie_info, title) for title in movie_titles]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]

# ================= CHAINLIT EVENTS =================

@cl.on_chat_start
async def start():
    """Khởi động phiên trò chuyện, thiết lập session và gửi menu chào mừng"""
    # Khởi tạo bộ nhớ hội thoại
    cl.user_session.set("chat_history", [])

    welcome_html = """
    <div style="
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #db2777 100%); 
        padding: 28px 24px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(124, 58, 237, 0.35);">
        <h1 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">Movie Chat AI</h1>
        <p style="margin: 8px 0 0; font-size: 15px; opacity: 0.95; font-weight: 400;">
            Trợ lý tư vấn điện ảnh thông minh - Khám phá phim hay - Xem trailer trực tiếp
        </p>
    </div>
    """
    await cl.Message(content=welcome_html).send()

    # Danh mục gợi ý bắt đầu nhanh
    starter_actions = [
        cl.Action(name="quick_reply", payload={"value": "Gợi ý những bộ phim hành động gay cấn kịch tính nhất"}, label="Phim Hành Động"),
        cl.Action(name="quick_reply", payload={"value": "Gợi ý những phim tình cảm lãng mạn nhẹ nhàng sâu lắng"}, label="Phim Tình Cảm"),
        cl.Action(name="quick_reply", payload={"value": "Gợi ý những kiệt tác khoa học viễn tưởng hay nhất mọi thời đại"}, label="Khoa Học Viễn Tưởng"),
        cl.Action(name="quick_reply", payload={"value": "Gợi ý các bộ phim điện ảnh từng đoạt giải Oscar danh giá"}, label="Phim Đoạt Giải Oscar"),
        cl.Action(name="random_pick", payload={}, label="Gợi ý phim ngẫu nhiên"),
    ]

    await cl.Message(
        content="**Chào bạn! Hãy chọn nhanh một chủ đề bên dưới hoặc nhập trực tiếp tên phim, diễn viên, đạo diễn bạn muốn tìm:**",
        actions=starter_actions
    ).send()

# ================= ACTION CALLBACKS =================

@cl.action_callback("quick_reply")
async def on_quick_reply(action: cl.Action):
    """Xử lý khi người dùng chọn một nút gợi ý nhanh"""
    await main(cl.Message(content=action.payload["value"]))

@cl.action_callback("random_pick")
async def on_random_pick(action: cl.Action):
    """Xử lý khi người dùng bấm nút bốc phim ngẫu nhiên"""
    prompt = "Hôm nay tôi chưa biết xem gì, hãy chọn ngẫu nhiên cho tôi một bộ phim điện ảnh thật xuất sắc và giải thích lý do nên xem nhé!"
    await main(cl.Message(content=prompt))

@cl.action_callback("play_trailer")
async def on_play_trailer(action: cl.Action):
    """Phát video Trailer YouTube trực tiếp trong khung chat Chainlit"""
    trailer_key = action.payload.get("trailer_key")
    title = action.payload.get("title")

    if trailer_key:
        video_url = f"https://www.youtube.com/watch?v={trailer_key}"
        await cl.Message(
            content=f"**Trailer chính thức: {title}**\n*(Bạn có thể xem trực tiếp bên dưới hoặc mở toàn màn hình)*",
            elements=[
                cl.Video(url=video_url, name=f"Trailer - {title}", display="inline")
            ]
        ).send()
    else:
        # Fallback tìm kiếm trailer trên YouTube nếu TMDB không có video
        yt_search = f"https://www.youtube.com/results?search_query=trailer+phim+{urllib.parse.quote_plus(title)}"
        await cl.Message(
            content=f"Chưa tìm thấy trailer trực tiếp trên TMDB cho phim **{title}**.\n[Bấm vào đây để xem Trailer trên YouTube]({yt_search})"
        ).send()

@cl.action_callback("find_similar")
async def on_find_similar(action: cl.Action):
    """Gợi ý các phim tương tự phim đã chọn"""
    title = action.payload.get("title")
    await main(cl.Message(content=f"Gợi ý cho tôi các bộ phim có phong cách hoặc cốt truyện tương tự như phim {title}"))

# ================= MAIN CHAT HANDLER =================

@cl.on_message
async def main(message: cl.Message):
    """Xử lý tin nhắn người dùng, duy trì lịch sử hội thoại và render thẻ phim"""
    user_input = message.content

    # Lấy lịch sử hội thoại từ user_session
    history = cl.user_session.get("chat_history", [])

    # Tạo tin nhắn streaming rỗng
    msg = cl.Message(content="")
    await msg.send()

    full_response = ""
    # Truyền history để bot nhớ ngữ cảnh các câu hỏi trước (Multi-turn chat)
    for token in bot.chat_stream(user_input, history=history):
        full_response += token
        await msg.stream_token(token)

    # Trích xuất danh sách tên phim từ định dạng <Phim 1, Phim 2, ...>
    movies = []
    matches = re.findall(r'<([^>]+)>', full_response)
    for m in matches:
        for item in m.split(','):
            raw_title = item.strip()
            # Bỏ qua các chuỗi quá dài hoặc chứa từ khóa chỉ dẫn
            if raw_title and len(raw_title) < 80 and not any(kw in raw_title.lower() for kw in ['lưu ý', 'chú ý', 'note', 'ví dụ', 'thể loại:']):
                movies.append(raw_title)

    # Dự phòng thông minh: Nếu AI không xuất thẻ <...>, trích xuất từ các tên phim in đậm **Tên Phim**
    if not movies:
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', full_response)
        ignore_kws = ['chào', 'lưu ý', 'chú ý', 'note', 'trailer', 'youtube', 'thể loại', 'movie chat ai', 'hướng dẫn', 'điểm', 'năm', 'đạo diễn', 'phim 1', 'phim 2']
        for bm in bold_matches:
            title_candidate = bm.strip()
            if 1 < len(title_candidate) < 60 and not any(kw in title_candidate.lower() for kw in ignore_kws):
                movies.append(title_candidate)

    # Làm sạch nội dung phản hồi:
    clean_text = full_response
    last_tags = list(re.finditer(r'<([^>]+)>', clean_text))
    if last_tags:
        last_m = last_tags[-1]
        # Bóc bỏ tag tổng hợp danh sách ở cuối (chứa dấu phẩy hoặc nằm sát cuối văn bản)
        if ',' in last_m.group(1) or last_m.end() >= len(clean_text.rstrip()) - 5:
            clean_text = clean_text[:last_m.start()] + clean_text[last_m.end():]

    # Nếu trong thân bài có thẻ ngoặc nhọn dạng **<Tên Phim>**, giữ lại Tên Phim và chỉ gỡ bỏ cặp ngoặc < > để tránh bị mất tên phim
    clean_text = re.sub(r'<([^>]+)>', r'\1', clean_text).strip()
    msg.content = clean_text or full_response
    await msg.update()

    # Cập nhật lịch sử hội thoại
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": clean_text})
    # Giới hạn bộ nhớ 10 lượt hội thoại gần nhất
    if len(history) > 10:
        history = history[-10:]
    cl.user_session.set("chat_history", history)

    # Nếu có gợi ý phim, tải dữ liệu song song và hiển thị thẻ phim
    if movies:
        # Lấy tối đa 8 phim để hiển thị tối ưu
        unique_titles = list(dict.fromkeys(movies))[:8]
        movie_infos = await get_all_movies_details(unique_titles)

        if movie_infos:
            html_cards = ""
            action_buttons = []

            for info in movie_infos:
                safe_title = html.escape(str(info.get('title', '')))
                safe_overview = html.escape(str(info.get('overview', '')))
                safe_year = html.escape(str(info.get('year', 'N/A')))
                safe_rating = html.escape(str(info.get('rating', '0.0')))
                safe_poster = html.escape(str(info.get('poster', '')), quote=True)
                safe_link_tmdb = html.escape(str(info.get('link_tmdb', '')), quote=True)
                safe_link_search = html.escape(str(info.get('link_search', '')), quote=True)

                # Tạo HTML tags thể loại
                genres_badges = "".join([
                    f'<span style="background: rgba(139, 92, 246, 0.12); color: #7c3aed; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;">{html.escape(str(g))}</span>'
                    for g in info.get('genres', [])
                ])

                # Thông tin thời lượng
                runtime_badge = f'<span class="movie-badge-neutral" style="padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 500;">{html.escape(str(info["runtime"]))}</span>' if info.get('runtime') else ""

                # Link hoặc nút trailer trên card
                trailer_html = ""
                if info.get('trailer_key'):
                    safe_trailer_url = html.escape(f"https://www.youtube.com/watch?v={info['trailer_key']}", quote=True)
                    trailer_html = f"""
                    <a href="{safe_trailer_url}" target="_blank" class="movie-btn movie-btn-trailer" style="
                        padding: 8px 16px; 
                        border-radius: 10px; 
                        font-size: 13px; 
                        font-weight: 600; 
                        text-decoration: none; 
                        display: inline-flex; align-items: center; gap: 6px;">
                        Trailer
                    </a>
                    """

                card = f"""
                <div class="movie-card" style="
                    display: flex; 
                    border-radius: 16px; 
                    overflow: hidden; 
                    margin-bottom: 20px; 
                    min-height: 230px;">
                    
                    <div style="
                        width: 160px; 
                        min-width: 160px; 
                        position: relative;
                        overflow: hidden;
                        background: #0f172a;
                        flex-shrink: 0;">
                        <img src="{safe_poster}" alt="{safe_title}" loading="lazy" decoding="async" style="
                            width: 100%;
                            height: 100%;
                            object-fit: cover;
                            display: block;" />
                    </div>
                    
                    <div style="flex: 1; padding: 18px 22px; display: flex; flex-direction: column; min-width: 0;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; gap: 8px;">
                            <h3 class="movie-title" style="font-size: 19px; font-weight: 700; margin: 0; line-height: 1.3;">
                                {safe_title}
                            </h3>
                            <span style="
                                background: #FEF3C7; 
                                color: #D97706; 
                                padding: 4px 8px; 
                                border-radius: 8px; 
                                font-size: 13px; 
                                font-weight: 700; 
                                display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
                                Điểm: {safe_rating}
                            </span>
                        </div>
                        
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px;">
                            <span class="movie-badge-neutral" style="padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 500;">Năm: {safe_year}</span>
                            {runtime_badge}
                            {genres_badges}
                        </div>
                        
                        <div class="movie-overview" style="
                            font-size: 14px; 
                            line-height: 1.55; 
                            margin-bottom: 16px; 
                            flex-grow: 1;
                            display: -webkit-box;
                            -webkit-line-clamp: 3;
                            -webkit-box-orient: vertical;
                            overflow: hidden;">
                            {safe_overview}
                        </div>
                        
                        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: auto; align-items: center;">
                            {trailer_html}
                            <a href="{safe_link_tmdb}" target="_blank" class="movie-btn movie-btn-secondary" style="
                                padding: 8px 16px; 
                                border-radius: 10px; 
                                font-size: 13px; 
                                font-weight: 600; 
                                text-decoration: none; 
                                display: inline-flex; align-items: center; gap: 6px;">
                                Chi tiết TMDB
                            </a>
                            <a href="{safe_link_search}" target="_blank" class="movie-btn" style="
                                padding: 8px 16px; 
                                border-radius: 10px; 
                                font-size: 13px; 
                                font-weight: 600; 
                                text-decoration: none; 
                                background: linear-gradient(135deg, #EC4899, #8B5CF6);
                                color: white; 
                                box-shadow: 0 4px 10px rgba(236, 72, 153, 0.25);
                                display: inline-flex; align-items: center; gap: 6px;">
                                Xem ngay
                            </a>
                        </div>
                    </div>
                </div>
                """
                html_cards += card

                # Thêm nút bấm xem Trailer trực tiếp trong Chat
                if info.get('trailer_key'):
                    action_buttons.append(
                        cl.Action(
                            name="play_trailer",
                            payload={"title": info['title'], "trailer_key": info['trailer_key']},
                            label=f"Trailer: {info['title'][:14]}"
                        )
                    )

                # Thêm nút bấm tìm phim tương tự 1-click
                action_buttons.append(
                    cl.Action(
                        name="find_similar",
                        payload={"title": info['title']},
                        label=f"Tương tự: {info['title'][:14]}"
                    )
                )

            final_html = f'<div class="movie-grid">{html_cards}</div>'
            final_html = re.sub(r'\n\s+', ' ', final_html)

            # Gửi thẻ phim và kèm theo các nút thao tác nhanh
            await cl.Message(
                content=final_html,
                actions=action_buttons[:10] # Giới hạn tối đa 10 actions để giao diện gọn gàng
            ).send()