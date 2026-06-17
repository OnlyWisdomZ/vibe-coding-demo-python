from flask import Flask, request, jsonify, redirect, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import math
import html
import traceback
from threading import Lock, Thread
app = Flask(__name__)
# 配置 CORS，允许前端访问
CORS(app)
# 获取前端项目目录
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
@app.route('/frontend/<path:filename>')
def serve_frontend(filename):
    return send_from_directory(static_dir, filename)
@app.route('/favicon.ico')
def favicon():
    return '', 204
@app.route('/')
def read_root():
    # 根路径自动重定向到登录页
    return redirect('/frontend/login.html')
# --- 数据加载模块 ---
# 我们在应用启动时一次性加载数据到内存中，提升接口响应速度
DATA_FILE = os.path.join(os.path.dirname(__file__), 'hotel_comments_cleaned.xlsx')

# 中文列名到英文变量名的映射（用于兼容中文列名的Excel文件）
COLUMN_NAME_MAPPING_CN_TO_EN = {
    "评论ID": "commentId",
    "酒店ID": "hotelID",
    "酒店名称": "hotelName",
    "城市": "ip",
    "酒店图片URL": "hotelImageUrl",
    "房型名称": "roomTypeName",
    "评分": "averageScore",
    "入住日期": "checkInDate",
    "入住时间描述": "checkInDesc",
    "退房日期": "checkOutDate",
    "评论来源": "commentSource",
    "用户头像": "headImg",
    "会员ID": "memberId",
    "会员姓名": "memberName",
    "会员等级": "memberLevel",
    "会员等级名称": "memberLevelName",
    "CEO直达标记": "isCEO",
    "优质评论": "isHighQuality",
    "华住渠道": "isHuazhu",
    "订单号": "orderId",
    "评价内容": "postsContent",
    "评价人名称": "postsName",
    "评价时间": "postsTime",
    "审核原因": "verifyReason",
    "审核状态码": "verifyStatus",
    "审核状态描述": "verifyStatusDesc",
    "点赞数": "likeCount",
    "文件数量": "fileCount",
    "评价标签": "tags",
    "酒店回复": "reply"
}

try:
    # 尝试打印相对工作目录的路径，使控制台输出更简洁
    display_path = os.path.relpath(DATA_FILE, os.getcwd())
except Exception:
    display_path = DATA_FILE
print(f"正在加载数据，文件路径: {display_path}")
try:
    df = pd.read_excel(DATA_FILE)
    # 如果列名是中文，则映射为英文变量名
    df = df.rename(columns=COLUMN_NAME_MAPPING_CN_TO_EN)
    # 将所有的 NaN 或 NaT 替换为 None，防止 JSON 序列化失败
    df = df.replace({np.nan: None})
    comments_data = df.to_dict(orient='records')
    print(f"数据加载成功！总记录数：{len(comments_data)}")
except Exception as e:
    print(f"数据加载失败：{e}")
    comments_data = []
    df = pd.DataFrame()
# --- 接口路由 ---
import uuid
import json
import hashlib
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        import secrets
        csrf_token = secrets.token_hex(16)
        try:
            with open(os.path.join(static_dir, 'register.html'), 'r', encoding='utf-8') as f:
                html_content = f.read()
            html_content = html_content.replace('{{ csrf_token }}', csrf_token)
            return html_content
        except FileNotFoundError:
            return "register.html not found", 404
    if request.method == 'POST':
        req = request.get_json()
        if not req:
            return jsonify({"code": 400, "message": "无效的请求数据"})
        username = req.get("username", "").strip()
        password = req.get("password", "")
        if not username or len(username) < 3 or len(username) > 20:
            return jsonify({"code": 400, "message": "用户名长度必须在3-20个字符之间"})
        if not password:
            return jsonify({"code": 400, "message": "密码不能为空"})
        users = load_users()
        if username in users:
            return jsonify({"code": 400, "message": "用户名已存在"})
        # SHA-256 哈希
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        users[username] = {
            "password_hash": hashed_password
        }
        save_users(users)
        return jsonify({"code": 200, "message": "注册成功"})

@app.route('/api/login', methods=['POST'])
def login():
    req = request.get_json()
    if not req:
        return jsonify({"code": 401, "message": "请求无效"})
    username = req.get("username")
    password = req.get("password")
    if username == "admin" and password == "123456":
        real_token = str(uuid.uuid4())
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "token": real_token,
                "username": username
            }
        })
    users = load_users()
    if username in users:
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        if users[username].get("password_hash") == hashed_password:
            real_token = str(uuid.uuid4())
            return jsonify({
                "code": 200,
                "message": "success",
                "data": {
                    "token": real_token,
                    "username": username
                }
            })
    return jsonify({
        "code": 401,
        "message": "用户名或密码错误！"
    })

@app.route('/api/comments', methods=['GET'])
def get_comments():
    # 可以根据条件进行筛选
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    hotel_id = request.args.get('hotel_id')
    filtered_data = comments_data
    if hotel_id:
        filtered_data = [item for item in filtered_data if str(item.get("hotelID")) == str(hotel_id)]
    total = len(filtered_data)
    # 分页逻辑
    start = (page - 1) * page_size
    end = start + page_size
    paginated_data = filtered_data[start:end]
    return jsonify({
        "code": 200,
        "message": "success",
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": paginated_data
        }
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # 返回给前端图表展示用的一些统计数据
    if df.empty:
        return jsonify({"code": 500, "message": "No data available."})
    # 1. 去掉无意义的评分分布，改为评论内容长度分布
    if 'postsContent' in df.columns:
        lengths = df['postsContent'].astype(str).str.len()
        len_dist = {
            "0-20字": int((lengths <= 20).sum()),
            "21-50字": int(((lengths > 20) & (lengths <= 50)).sum()),
            "51-100字": int(((lengths > 50) & (lengths <= 100)).sum()),
            "100字以上": int((lengths > 100).sum())
        }
        length_distribution = [{"range": k, "count": v} for k, v in len_dist.items()]
    else:
        length_distribution = []
    # 2. 各酒店评论数分布
    hotel_counts = df['hotelName'].value_counts().to_dict()
    hotel_distribution = [{"hotelName": str(k) if k else "Unknown", "count": int(v)} for k, v in hotel_counts.items()]
    # 3. 回复比例
    reply_counts = df['reply'].value_counts().to_dict()
    return jsonify({
        "code": 200,
        "message": "success",
        "data": {
            "length_distribution": length_distribution,
            "hotel_distribution": hotel_distribution,
            "reply_counts": {
                "replied": int(reply_counts.get(1, 0)),
                "unreplied": int(reply_counts.get(0, 0))
            },
            "total_comments": len(df)
        }
    })

import jieba
import jieba.analyse
from snownlp import SnowNLP
from snownlp import sentiment
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import re
import logging
import time
# 屏蔽 jieba 默认的英文控制台输出
jieba.setLogLevel(logging.WARNING)
print("正在初始化自然语言分词模型...")
start_time = time.time()
jieba.initialize()
# 添加自定义词汇，确保特定复合词不被错误切分
custom_words = [
    "性价比", "隔音差", "热水不稳定", "前台态度", "卫生差", "地理位置", "交通便利", "自助早餐",
    "很赞", "很好", "太棒了", "推荐", "很差", "太差了", "极差", "不推荐", "避坑"
]
for word in custom_words:
    jieba.add_word(word)
print(f"分词模型加载并添加自定义词汇成功，耗时 {round(time.time() - start_time, 3)} 秒。")
# 缓存分析结果，避免每次请求重复计算耗时操作
analysis_cache = {}
analysis_tasks = {}
analysis_task_lock = Lock()
LDA_MAX_FEATURES = 3000
LDA_TOPIC_RANGE = tuple(range(1, 9))
DEFAULT_LDA_TOPIC_COUNT = 4
LDA_TYPE_LABELS = {
    "pos": "积极评论",
    "neg": "消极评论",
    "all": "全部评论"
}
STOP_WORDS_FILE = os.path.join(os.path.dirname(__file__), '停用词.txt')
POS_CLOUD_STOP_WORDS_FILE = os.path.join(os.path.dirname(__file__), '积极词云停用词.txt')
NEG_CLOUD_STOP_WORDS_FILE = os.path.join(os.path.dirname(__file__), '消极词云停用词.txt')
def load_word_set(file_path, fallback_words=None):
    fallback_words = fallback_words or set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            words = {line.strip() for line in f if line.strip() and not line.strip().startswith('#')}
        return fallback_words.union(words)
    except FileNotFoundError:
        return set(fallback_words)
def load_stop_words():
    base_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "酒店", "房间", "入住", "评论", "华住会"
    }
    return load_word_set(STOP_WORDS_FILE, base_words)
# 停用词表
STOP_WORDS = load_stop_words()
POS_CLOUD_STOP_WORDS = STOP_WORDS.union(load_word_set(POS_CLOUD_STOP_WORDS_FILE))
NEG_CLOUD_STOP_WORDS = STOP_WORDS.union(load_word_set(NEG_CLOUD_STOP_WORDS_FILE))
def invalidate_lda_cache():
    keys_to_remove = [key for key in analysis_cache if key.startswith("lda_")]
    for key in keys_to_remove:
        analysis_cache.pop(key, None)
def get_recommended_topic_count():
    summary = analysis_cache.get("lda_summary", {}).get("data", {})
    topic_count = summary.get("recommended_topic_count", DEFAULT_LDA_TOPIC_COUNT)
    return topic_count if topic_count in LDA_TOPIC_RANGE else DEFAULT_LDA_TOPIC_COUNT
def normalize_topic_count(value, default_topic_count=DEFAULT_LDA_TOPIC_COUNT):
    fallback_topic_count = default_topic_count if default_topic_count in LDA_TOPIC_RANGE else DEFAULT_LDA_TOPIC_COUNT
    try:
        topic_count = int(value)
    except (TypeError, ValueError):
        topic_count = fallback_topic_count
    return topic_count if topic_count in LDA_TOPIC_RANGE else fallback_topic_count
def get_task_status(task_key):
    with analysis_task_lock:
        task = analysis_tasks.get(task_key, {}).copy()
    return task
def update_task_status(task_key, *, status=None, stage=None, message=None, current=None, total=None, error=None, finished=False):
    with analysis_task_lock:
        task = analysis_tasks.get(task_key, {})
        if not task:
            task = {
                "status": "queued",
                "stage": "queued",
                "message": "任务已创建",
                "created_at": time.time()
            }
        if status is not None:
            task["status"] = status
        if stage is not None:
            task["stage"] = stage
        if message is not None:
            task["message"] = message
        if current is not None or total is not None:
            current_value = task.get("current", 0) if current is None else int(current)
            total_value = task.get("total", 0) if total is None else int(total)
            task["current"] = current_value
            task["total"] = total_value
            task["percent"] = round((current_value / total_value) * 100, 1) if total_value else 0.0
        if error is not None:
            task["error"] = error
        task["updated_at"] = time.time()
        if finished:
            task["finished_at"] = time.time()
        analysis_tasks[task_key] = task
        return task.copy()

def start_background_task(task_key, runner, start_message):
    with analysis_task_lock:
        existing = analysis_tasks.get(task_key)
        if existing and existing.get("status") in ("queued", "running"):
            return False
        analysis_tasks[task_key] = {
            "status": "queued",
            "stage": "queued",
            "message": start_message,
            "current": 0,
            "total": 0,
            "percent": 0.0,
            "created_at": time.time(),
            "updated_at": time.time()
        }
    def task_wrapper():
        try:
            update_task_status(task_key, status="running", stage="starting", message=start_message)
            runner()
            final_task = get_task_status(task_key)
            if final_task.get("status") not in ("completed", "failed"):
                update_task_status(
                    task_key,
                    status="completed",
                    stage="done",
                    message="任务执行完成。",
                    current=1,
                    total=1,
                    finished=True
                )
        except Exception as exc:
            traceback.print_exc()
            update_task_status(
                task_key,
                status="failed",
                stage="failed",
                message="任务执行失败，请稍后重试。",
                error=str(exc),
                finished=True
            )
    Thread(target=task_wrapper, daemon=True).start()
    return True
# 1. 消费者会员等级分布与消费特征分析
@app.route('/api/analysis/b1_member', methods=['GET'])
def get_b1_member():
    if df.empty or 'memberLevelName' not in df.columns:
        return jsonify({"code": 200, "message": "success", "data": {}})
    # 会员等级人数占比
    counts = df['memberLevelName'].value_counts().to_dict()
    level_dist = [{"name": str(k), "value": int(v)} for k, v in counts.items() if k and str(k) != 'nan']
    # 消费特征：各等级的平均带图率和平均字数
    valid_df = df.dropna(subset=['memberLevelName']).copy()
    if 'fileCount' in valid_df.columns:
        valid_df['hasFile'] = valid_df['fileCount'].apply(lambda x: 1 if pd.notnull(x) and float(x) > 0 else 0)
    else:
        valid_df['hasFile'] = 0
    if 'postsContent' in valid_df.columns:
        valid_df['contentLen'] = valid_df['postsContent'].astype(str).str.len()
    else:
        valid_df['contentLen'] = 0
    grouped = valid_df.groupby('memberLevelName')
    file_rates = (grouped['hasFile'].mean() * 100).round(1).to_dict()
    len_avgs = grouped['contentLen'].mean().round(0).to_dict()
    features = []
    for k in counts.keys():
        if k and str(k) != 'nan':
            features.append({
                "name": str(k),
                "file_rate": file_rates.get(k, 0),
                "avg_len": int(len_avgs.get(k, 0))
            })
    return jsonify({"code": 200, "message": "success", "data": {"distribution": level_dist, "features": features}})
# 2. 酒店房型入住频次与偏好分析
@app.route('/api/analysis/b2_room', methods=['GET'])
def get_b2_room():
    if df.empty or 'roomTypeName' not in df.columns:
        return jsonify({"code": 200, "message": "success", "data": []})
    top_rooms = df['roomTypeName'].value_counts().head(15).index
    room_data = df[df['roomTypeName'].isin(top_rooms)].copy()
    # 判断是否为长评（字数大于50），代表偏好深度分享
    if 'postsContent' in room_data.columns:
        room_data['isLong'] = room_data['postsContent'].astype(str).str.len().apply(lambda x: 1 if x > 50 else 0)
    else:
        room_data['isLong'] = 0
    counts = room_data['roomTypeName'].value_counts().to_dict()
    long_counts = room_data.groupby('roomTypeName')['isLong'].sum().to_dict()
    data = []
    for room in top_rooms:
        r_str = str(room)
        if r_str and r_str != 'nan':
            data.append({
                "roomType": r_str,
                "count": int(counts.get(room, 0)),
                "long_count": int(long_counts.get(room, 0))
            })
    return jsonify({"code": 200, "message": "success", "data": data})

# 3. 消费者满意度统计分析
@app.route('/api/analysis/b3_satisfaction', methods=['GET'])
def get_b3_satisfaction():
    if df.empty:
        return jsonify({"code": 200, "message": "success", "data": {}})
    # 定义常见差评词根（纯字符串匹配，不用NLP）
    bad_keywords = ["差", "吵", "旧", "脏", "异味", "不舒服", "慢", "坏", "蚊", "失望", "不行"]
    good_keywords = ["好", "干净", "舒适", "新", "热情", "方便", "棒", "安静"]
    satisfaction = {"very_good": 0, "good": 0, "bad": 0, "neutral": 0}
    for idx, row in df.iterrows():
        tag_str = str(row.get('tags', ''))
        content_str = str(row.get('postsContent', ''))
        # 优先看 tags，如果 tags 有明显的差评字眼，算差
        is_bad = any(b in tag_str for b in bad_keywords)
        is_good = any(g in tag_str for g in good_keywords)
        # 如果 tags 没填，退一步在正文找。为了防止误判，仅做粗略匹配
        if tag_str == 'nan' or not tag_str.strip():
            is_bad = any(b in content_str for b in bad_keywords)
            is_good = any(g in content_str for g in good_keywords)
        if is_bad:
            satisfaction["bad"] += 1
        elif is_good:
            # 区分非常满意和满意（例如同时被标为高质量评价 isHighQuality）
            hq = str(row.get('isHighQuality', '0'))
            if hq == '1' or hq == 'True':
                satisfaction["very_good"] += 1
            else:
                satisfaction["good"] += 1
        else:
            satisfaction["neutral"] += 1
    # 高质量评价整体占比
    hq_count = 0
    if 'isHighQuality' in df.columns:
        hq_count = int(df['isHighQuality'].apply(lambda x: 1 if str(x) in ['1', 'True'] else 0).sum())
    data = {
        "distribution": [
            {"name": "非常满意(好评+优质)", "value": satisfaction["very_good"]},
            {"name": "满意(好评)", "value": satisfaction["good"]},
            {"name": "中性/未知", "value": satisfaction["neutral"]},
            {"name": "不满意(含吐槽词)", "value": satisfaction["bad"]}
        ],
        "total": len(df),
        "hq_count": hq_count
    }
    return jsonify({"code": 200, "message": "success", "data": data})

# 4. 评论发布时间与入住时段特征分析
@app.route('/api/analysis/b4_time', methods=['GET'])
def get_b4_time():
    if df.empty:
        return jsonify({"code": 200, "message": "success", "data": {}})
    valid_df = df.copy()
    # 1. 评论发布时间按月趋势
    if 'postsTime' in valid_df.columns:
        valid_df['postMonth'] = valid_df['postsTime'].astype(str).str.slice(0, 7)
        post_trend = valid_df['postMonth'].value_counts().sort_index().to_dict()
        post_trend_data = [{"time": k, "count": v} for k, v in post_trend.items() if k and k != 'nan']
    else:
        post_trend_data = []
    # 2. 入住时段特征 (提取 checkInDesc 中的年月，例如 "2026年03月入住" -> "2026-03")
    if 'checkInDesc' in valid_df.columns:
        # 正则提取 4位年份和2位月份
        extracted = valid_df['checkInDesc'].astype(str).str.extract(r'(\d{4})年(\d{2})月')
        # 将年和月用横线拼接，遇到缺失值会变成 NaN
        valid_df['checkInMonth'] = extracted[0] + "-" + extracted[1]
        checkin_trend = valid_df['checkInMonth'].dropna().value_counts().sort_index().to_dict()
        checkin_trend_data = [{"month": str(k), "count": int(v)} for k, v in checkin_trend.items() if k and str(k) != 'nan']
    else:
        checkin_trend_data = []
    return jsonify({
        "code": 200, 
        "message": "success", 
        "data": {
            "post_trend": post_trend_data,
            "checkin_trend": checkin_trend_data
        }
    })

# 5. 酒店好评/差评标签高频词统计分析
@app.route('/api/analysis/b5_tags', methods=['GET'])
def get_b5_tags():
    if df.empty or 'tags' not in df.columns:
        return jsonify({"code": 200, "message": "success", "data": {}})
    all_tags = []
    # 遍历 tags 列，按逗号切分
    for tag_str in df['tags'].dropna().astype(str):
        if tag_str.strip():
            # 可能是中文逗号或英文逗号，甚至空格，我们统一替换一下
            clean_str = tag_str.replace('，', ',').replace(' ', ',')
            parts = [p.strip() for p in clean_str.split(',') if p.strip()]
            all_tags.extend(parts)
    # 统计词频
    from collections import Counter
    tag_counts = Counter(all_tags)
    # 简单分好评和差评池
    bad_roots = ["差", "吵", "旧", "脏", "慢", "坏", "小", "异味", "不好", "不干净", "不隔音", "破", "乱", "漏", "无"]
    good_tags = []
    bad_tags = []
    for tag, count in tag_counts.items():
        # "不错" 是好评词，不能因为含有"不"就被算作差评
        if "不错" in tag:
            good_tags.append({"name": tag, "value": count})
            continue
        # “无”字要小心，比如“无异味”是好评，但“无窗”算中性/负面
        if "无异味" in tag:
            good_tags.append({"name": tag, "value": count})
            continue
        is_bad = any(b in tag for b in bad_roots)
        if is_bad:
            bad_tags.append({"name": tag, "value": count})
        else:
            good_tags.append({"name": tag, "value": count})
    # 排序
    good_tags.sort(key=lambda x: x["value"], reverse=True)
    bad_tags.sort(key=lambda x: x["value"], reverse=True)
    return jsonify({
        "code": 200,
        "message": "success",
        "data": {
            "good_tags": good_tags[:16],
            "bad_tags": bad_tags[:16]
        }
    })

# 6. 消费者评论图片/点赞互动行为分析
@app.route('/api/analysis/b6_interaction', methods=['GET'])
def get_b6_interaction():
    if df.empty:
        return jsonify({"code": 200, "message": "success", "data": {}})
    # 图片分布
    has_pic = 0
    no_pic = 0
    if 'fileCount' in df.columns:
        has_pic = int(df['fileCount'].apply(lambda x: 1 if pd.notnull(x) and float(x) > 0 else 0).sum())
        no_pic = len(df) - has_pic
    # 点赞分布 (是否获得点赞)
    has_like = 0
    no_like = 0
    if 'likeCount' in df.columns:
        likes = df['likeCount'].fillna(0).astype(float)
        no_like = int((likes == 0).sum())
        has_like = int((likes > 0).sum())
    # 商家互动 (reply)
    has_reply = 0
    no_reply = 0
    if 'reply' in df.columns:
        has_reply = int(df['reply'].fillna(0).astype(float).sum())
        no_reply = len(df) - has_reply
    data = {
        "pic_dist": [{"name": "带图评论", "value": has_pic}, {"name": "无图评论", "value": no_pic}],
        "like_dist": [{"name": "未获得点赞", "value": no_like}, {"name": "已获得点赞", "value": has_like}],
        "reply_dist": [{"name": "商家已回复", "value": has_reply}, {"name": "商家未回复", "value": no_reply}]
    }
    return jsonify({"code": 200, "message": "success", "data": data})

# 7. 同一省份酒店多维对比分析
@app.route('/api/analysis/b7_city', methods=['GET'])
def get_b7_province():
    province = request.args.get('province')
    if df.empty or 'hotelName' not in df.columns:
        return jsonify({"code": 200, "message": "success", "data": {}})
    prov_map = {
        '台儿庄': '山东', '青岛': '山东',
        '南京': '江苏', '无锡': '江苏', '苏州': '江苏', '扬州': '江苏',
        '长兴': '浙江', '上虞': '浙江', '杭州': '浙江', '宁波': '浙江', '绍兴': '浙江',
        '丽江': '云南', '成都': '四川', '阆中': '四川', '巴中': '四川', '恩阳': '四川',
        '北京': '北京', '广州': '广东', '深圳': '广东', '武汉': '湖北', '西安': '陕西',
        '重庆': '重庆', '长沙': '湖南', '天津': '天津', '郑州': '河南', '大连': '辽宁', '上海': '上海'
    }
    valid_df = df.copy()
    valid_df['province'] = '其他'
    for k, v in prov_map.items():
        valid_df.loc[valid_df['hotelName'].astype(str).str.contains(k), 'province'] = v
    # 获取所有的省份列表，按拥有酒店数量排序
    prov_hotel_counts = valid_df[valid_df['province'] != '其他'].groupby('province')['hotelName'].nunique()
    if prov_hotel_counts.empty:
        return jsonify({"code": 200, "message": "未匹配到省份数据", "data": {}})
    # 用户只要江苏、浙江、四川这三个省份的数据
    allowed_provs = ["江苏", "浙江", "四川"]
    available_provs = []
    # 过滤出当前数据里确实存在、并且在 allowed_provs 里的省份
    for p in prov_hotel_counts.sort_values(ascending=False).index.tolist():
        if p in allowed_provs:
            available_provs.append(p)
    if not available_provs:
        return jsonify({"code": 200, "message": "没有找到江浙川三个省份的数据", "data": {}})
    # 确定要分析的省份
    if province and province in available_provs:
        target_prov = province
    else:
        # 默认使用第一个
        target_prov = available_provs[0]
    prov_df = valid_df[valid_df['province'] == target_prov].copy()
    if 'fileCount' in prov_df.columns:
        prov_df['hasFile'] = prov_df['fileCount'].apply(lambda x: 1 if pd.notnull(x) and float(x) > 0 else 0)
    else:
        prov_df['hasFile'] = 0
    if 'reply' in prov_df.columns:
        prov_df['isReplied'] = prov_df['reply'].fillna(0)
    else:
        prov_df['isReplied'] = 0
    if 'isHighQuality' in prov_df.columns:
        prov_df['isHq'] = prov_df['isHighQuality'].apply(lambda x: 1 if str(x) in ['1', 'True'] else 0)
    else:
        prov_df['isHq'] = 0
    hotel_counts = prov_df['hotelName'].value_counts().to_dict()
    file_counts = prov_df.groupby('hotelName')['hasFile'].sum().to_dict()
    reply_counts = prov_df.groupby('hotelName')['isReplied'].sum().to_dict()
    hq_counts = prov_df.groupby('hotelName')['isHq'].sum().to_dict()
    avg_lens = prov_df.groupby('hotelName')['postsContent'].apply(lambda x: x.astype(str).str.len().mean()).to_dict()
    chart_data = []
    for h, c in hotel_counts.items():
        if c == 0: continue
        chart_data.append({
            "hotel": str(h).replace('花间堂·', '').replace('花间堂', ''),
            "count": int(c),
            "file_rate": round(file_counts.get(h, 0) / c * 100, 1),
            "reply_rate": round(reply_counts.get(h, 0) / c * 100, 1),
            "hq_rate": round(hq_counts.get(h, 0) / c * 100, 1),
            "avg_len": round(avg_lens.get(h, 0), 0) if pd.notnull(avg_lens.get(h)) else 0
        })
    return jsonify({
        "code": 200, 
        "message": "success", 
        "data": {
            "province_name": target_prov,
            "available_provinces": available_provs,
            "hotels": chart_data
        }
    })
# --- 深度文本分析接口 ---
def get_all_texts():
    if df.empty or 'postsContent' not in df.columns:
        return []
    # 提取所有非空文本进行全表扫描
    texts = df['postsContent'].dropna().astype(str).tolist()
    return texts
@app.route('/api/analysis/tfidf', methods=['GET'])
def get_tfidf_analysis():
    if "tfidf" in analysis_cache:
        return jsonify({"code": 200, "message": "success", "data": analysis_cache["tfidf"]})
    texts = get_all_texts()
    if not texts:
        return jsonify({"code": 200, "message": "success", "data": []})
    # 合并所有文本，全表扫描
    full_text = "。".join(texts)
    # 提取TF-IDF前50名
    tags = jieba.analyse.extract_tags(full_text, topK=50, withWeight=True)
    data = []
    for word, weight in tags:
        if word not in STOP_WORDS and len(word) > 1:
            data.append({"word": word, "weight": round(weight, 3)}) # 保留3位小数
        if len(data) >= 30:
            break
    analysis_cache["tfidf"] = data
    return jsonify({"code": 200, "message": "success", "data": data})

@app.route('/api/analysis/sentiment', methods=['GET'])
def get_sentiment_analysis():
    data = compute_sentiment_cache()
    return jsonify({"code": 200, "message": "success", "data": data})
def compute_sentiment_cache(progress_task_key=None):
    if "sentiment" in analysis_cache:
        return analysis_cache["sentiment"]
    texts = get_all_texts() 
    if not texts:
        analysis_cache["pos_texts"] = []
        analysis_cache["neg_texts"] = []
        analysis_cache["sentiment"] = {}
        return analysis_cache["sentiment"]
    pos, neu, neg = 0, 0, 0
    scores = []
    pos_texts = []
    neg_texts = []
    # 记录所有的原始分数以及它们被判定的类别，用于画箱线图/分布图
    all_scores_detail = []
    total_texts = len(texts)
    if progress_task_key:
        update_task_status(
            progress_task_key,
            status="running",
            stage="sentiment",
            message=f"正在进行全表情感分析（0/{total_texts}）",
            current=0,
            total=total_texts
        )
    for idx, text in enumerate(texts, start=1):
        try:
            # 清理特殊字符
            clean_text = re.sub(r'[^\w\s\u4e00-\u9fa5]', '', text)
            if not clean_text.strip():
                continue
            s = SnowNLP(clean_text)
            score = s.sentiments
            scores.append(score)
            category = "neutral"
            if score > 0.65:
                pos += 1
                pos_texts.append(clean_text)
                category = "pos"
            elif score < 0.35:
                neg += 1
                neg_texts.append(clean_text)
                category = "neg"
            else:
                neu += 1
            all_scores_detail.append({
                "score": score,
                "category": category,
                "text": text # 保存原始文本以供详情页展示
            })
        except:
            pass
        if progress_task_key and (idx % 200 == 0 or idx == total_texts):
            update_task_status(
                progress_task_key,
                status="running",
                stage="sentiment",
                message=f"正在进行全表情感分析（{idx}/{total_texts}）",
                current=idx,
                total=total_texts
            )

    dist = [0, 0, 0, 0, 0] # (0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0)
    for score in scores:
        idx = min(int(score / 0.2), 4)
        dist[idx] += 1
    def extract_words(doc_list, is_negative=False):
        full_str = "。".join(doc_list)
        # 增加提取词汇量，以满足至少80个词的需求
        top_k = 300 if is_negative else 200
        tags = jieba.analyse.extract_tags(full_str, topK=top_k, withWeight=True)
        res = []
        current_stops = NEG_CLOUD_STOP_WORDS if is_negative else POS_CLOUD_STOP_WORDS
        for w, weight in tags:
            if w not in current_stops and len(w) > 1:
                res.append({"name": w, "value": round(weight * 1000, 2)})
            if len(res) >= 80:
                break
        return res
    pos_words = extract_words(pos_texts, is_negative=False)
    neg_words = extract_words(neg_texts, is_negative=True)
    data = {
        "positive": pos,
        "neutral": neu,
        "negative": neg,
        "distribution": dist,
        "pos_words": pos_words,
        "neg_words": neg_words,
        "all_scores": all_scores_detail
    }
    invalidate_lda_cache()
    analysis_cache["pos_texts"] = pos_texts
    analysis_cache["neg_texts"] = neg_texts
    analysis_cache["sentiment"] = data
    return data

import io
import csv
import jieba.posseg as pseg

@app.route('/api/analysis/download_word_csv', methods=['GET'])
def download_word_csv():
    texts = get_all_texts()
    if not texts:
        return jsonify({"code": 500, "message": "没有找到评论数据"})
    word_counts = {}
    for text in texts:
        # 清理特殊字符，减少不必要的标点
        clean_text = re.sub(r'[^\w\s\u4e00-\u9fa5]', '', text)
        if not clean_text.strip():
            continue
        words = pseg.cut(clean_text)
        for w, flag in words:
            w_strip = w.strip()
            # 过滤停用词、单字词和标点符号（flag='x'）
            if w_strip and w_strip not in STOP_WORDS and len(w_strip) > 1 and flag != 'x':
                key = (w_strip, flag)
                word_counts[key] = word_counts.get(key, 0) + 1
    # 按照词频倒序排序
    sorted_words = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    # 将结果保存为本地 word.csv 文件
    save_path = os.path.join(os.path.dirname(__file__), 'word.csv')
    with open(save_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['词语', '词性', '频次'])
        for (word, flag), count in sorted_words:
            writer.writerow([word, flag, count])
    # 同时提供下载功能
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['词语', '词性', '频次'])
    for (word, flag), count in sorted_words:
        writer.writerow([word, flag, count])
    output.seek(0)
    mem = io.BytesIO()
    # 使用 utf-8-sig 防止 Excel 打开乱码
    mem.write(output.getvalue().encode('utf-8-sig'))
    mem.seek(0)
    from flask import send_file
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name='word.csv'
    )

@app.route('/api/analysis/download_sentiment', methods=['GET'])
def download_sentiment():
    sentiment_type = request.args.get('type', 'pos')
    if "sentiment" not in analysis_cache:
        compute_sentiment_cache()
    all_scores = analysis_cache["sentiment"].get("all_scores", [])
    filtered_data = [item for item in all_scores if item["category"] == sentiment_type]
    df_download = pd.DataFrame([{
        "内容": item.get("text", ""),
        "情感类型": item.get("category", "").upper(),
        "情感分数": round(item.get("score", 0), 2)
    } for item in filtered_data])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_download.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    from flask import send_file
    filename = '积极评论.xlsx' if sentiment_type == 'pos' else '消极评论.xlsx'
    return send_file(
        output, 
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

import pyLDAvis
import pyLDAvis.lda_model

def get_lda_source_texts(topic_type):
    pos_texts = analysis_cache.get("pos_texts", [])
    neg_texts = analysis_cache.get("neg_texts", [])
    if topic_type == 'pos':
        return pos_texts
    if topic_type == 'neg':
        return neg_texts
    return pos_texts + neg_texts

def build_lda_corpus(topic_type, progress_task_key=None, progress_prefix=None):
    cache_key = f"lda_corpus_{topic_type}"
    if cache_key in analysis_cache:
        return analysis_cache[cache_key]
    if topic_type == "all":
        pos_cache = analysis_cache.get("lda_corpus_pos")
        neg_cache = analysis_cache.get("lda_corpus_neg")
        if pos_cache is not None and neg_cache is not None:
            analysis_cache[cache_key] = pos_cache + neg_cache
            return analysis_cache[cache_key]
    texts = get_lda_source_texts(topic_type)
    if not texts:
        return []
    total_texts = len(texts)
    prefix = progress_prefix or f"正在整理 {LDA_TYPE_LABELS.get(topic_type, topic_type)} 的 LDA 语料"
    if progress_task_key:
        update_task_status(
            progress_task_key,
            status="running",
            stage="tokenize",
            message=f"{prefix}（0/{total_texts}）",
            current=0,
            total=total_texts
        )
    corpus = []
    for idx, doc in enumerate(texts, start=1):
        words = [w for w in jieba.lcut(doc) if w not in STOP_WORDS and len(w) > 1]
        if words:
            corpus.append(" ".join(words))
        if progress_task_key and (idx % 200 == 0 or idx == total_texts):
            update_task_status(
                progress_task_key,
                status="running",
                stage="tokenize",
                message=f"{prefix}（{idx}/{total_texts}）",
                current=idx,
                total=total_texts
            )
    analysis_cache[cache_key] = corpus
    return corpus

def build_lda_matrix(corpus):
    vectorizer = CountVectorizer(max_df=0.9, min_df=2, max_features=LDA_MAX_FEATURES)
    dtm = vectorizer.fit_transform(corpus)
    if dtm.shape[0] == 0 or dtm.shape[1] == 0:
        raise ValueError("LDA 语料在停用词过滤后没有足够的有效词项。")
    return vectorizer, dtm

def create_lda_model(n_components):
    return LatentDirichletAllocation(
        n_components=n_components,
        random_state=42,
        max_iter=2,
        learning_method='online',
        batch_size=512,
        evaluate_every=0,
        n_jobs=-1
    )

def compute_topic_umass_coherence(binary_dtm, topic_word_indices):
    if not topic_word_indices:
        return 0.0
    sub_matrix = binary_dtm[:, topic_word_indices].astype(np.float64)
    co_matrix = (sub_matrix.T @ sub_matrix).toarray()
    doc_freq = np.diag(co_matrix)
    scores = []
    for m in range(1, len(topic_word_indices)):
        for l in range(m):
            denominator = doc_freq[l]
            if denominator <= 0:
                continue
            ratio = (co_matrix[m, l] + 1.0) / denominator
            if ratio <= 0:
                continue
            scores.append(math.log(ratio))
    return float(np.mean(scores)) if scores else 0.0

def normalize_umass_score(score):
    if math.isnan(score):
        return 0.0
    return round(float(max(0.0, min(1.0, (score + 15.0) / 15.0))), 3)

def build_lda_summary_cache():
    task_key = "lda_summary_task"
    if "sentiment" not in analysis_cache:
        compute_sentiment_cache(progress_task_key=task_key)
    else:
        update_task_status(
            task_key,
            status="running",
            stage="sentiment",
            message="情感缓存已就绪，开始准备 LDA 汇总。",
            current=1,
            total=1
        )
    corpus = build_lda_corpus(
        "all",
        progress_task_key=task_key,
        progress_prefix="正在对全量积极/消极评论分词"
    )
    if not corpus:
        raise ValueError("情感分析完成后没有可用于 LDA 的文本。")
    update_task_status(
        task_key,
        status="running",
        stage="vectorize",
        message=f"正在构建词袋矩阵（{len(corpus)} 条有效文本）"
    )
    vectorizer, dtm = build_lda_matrix(corpus)
    feature_names = vectorizer.get_feature_names_out()
    binary_dtm = (dtm > 0).astype(np.float64).tocsr()
    from sklearn.metrics.pairwise import cosine_similarity
    topic_numbers = list(LDA_TOPIC_RANGE)
    coherence = []
    perplexity = []
    similarity = []
    topics_by_count = {}
    total_models = len(topic_numbers)
    for model_idx, n in enumerate(topic_numbers, start=1):
        update_task_status(
            task_key,
            status="running",
            stage="train",
            message=f"正在训练 LDA 模型（{model_idx}/{total_models}，主题数={n}）",
            current=model_idx,
            total=total_models
        )
        lda = create_lda_model(n)
        lda.fit(dtm)
        comp = lda.components_ / lda.components_.sum(axis=1)[:, np.newaxis]
        if n == 1:
            sim = 1.0
        else:
            sim_matrix = cosine_similarity(comp)
            upper_tri = sim_matrix[np.triu_indices(n, k=1)]
            sim = float(np.mean(upper_tri))
        similarity.append(round(sim, 3))
        perplexity_value = float(lda.perplexity(dtm))
        if not np.isfinite(perplexity_value):
            perplexity_value = float("inf")
        perplexity.append(round(perplexity_value, 3))
        topic_words = []
        topic_word_indices = []
        topic_word_weights = []
        for topic in lda.components_:
            top_words_idx = topic.argsort()[:-11:-1]
            topic_word_indices.append(top_words_idx.tolist())
            topic_words.append([feature_names[i] for i in top_words_idx])
            # 计算每个词的权重（归一化）
            topic_sum = topic.sum()
            weights = [round(topic[i] / topic_sum, 3) for i in top_words_idx]
            topic_word_weights.append(weights)
        topic_scores = [compute_topic_umass_coherence(binary_dtm, indices) for indices in topic_word_indices]
        coherence.append(normalize_umass_score(float(np.mean(topic_scores)) if topic_scores else 0.0))
        topics_by_count[str(n)] = [
            {
                "topic_id": idx,
                "keywords": " ".join(words),
                "keywords_with_weights": [{"word": w, "weight": wt} for w, wt in zip(words, topic_word_weights[idx])]
            }
            for idx, words in enumerate(topic_words)
        ]
    best_coherence_topic_count = topic_numbers[max(range(len(topic_numbers)), key=lambda idx: (coherence[idx], -topic_numbers[idx]))]
    best_perplexity_topic_count = topic_numbers[min(range(len(topic_numbers)), key=lambda idx: (perplexity[idx], topic_numbers[idx]))]
    recommended_topic_count = topic_numbers[
        min(
            range(len(topic_numbers)),
            key=lambda idx: (-coherence[idx], perplexity[idx], topic_numbers[idx])
        )
    ]
    data = {
        "code": 200,
        "message": "success",
        "data": {
            "topic_numbers": topic_numbers,
            "coherence": coherence,
            "perplexity": perplexity,
            "similarity": similarity,
            "topics": topics_by_count.get(str(DEFAULT_LDA_TOPIC_COUNT), []),
            "topics_by_count": topics_by_count,
            "best_topic_count_by_coherence": best_coherence_topic_count,
            "best_topic_count_by_perplexity": best_perplexity_topic_count,
            "recommended_topic_count": recommended_topic_count,
            "recommendation_rule": "推荐主题数按一致性优先、困惑度辅助确定。",
            "meta": {
                "documents": int(dtm.shape[0]),
                "vocabulary_size": int(dtm.shape[1])
            }
        }
    }
    analysis_cache["lda_summary"] = data
    update_task_status(
        task_key,
        status="completed",
        stage="done",
        message=f"LDA 汇总已生成，使用 {dtm.shape[0]} 条文本、{dtm.shape[1]} 个词项。",
        current=1,
        total=1,
        finished=True
    )

def build_lda_pyldavis_cache(topic_type, topic_count):
    task_key = f"lda_pyldavis_task_{topic_type}_{topic_count}"
    cache_key = f"lda_pyldavis_{topic_type}_{topic_count}"
    topics_cache_key = f"lda_topics_{topic_type}_{topic_count}"
    label = LDA_TYPE_LABELS.get(topic_type, topic_type)
    if "sentiment" not in analysis_cache:
        compute_sentiment_cache(progress_task_key=task_key)
    else:
        update_task_status(
            task_key,
            status="running",
            stage="sentiment",
            message=f"{label}的情感缓存已就绪，开始准备可视化。",
            current=1,
            total=1
        )
    corpus = build_lda_corpus(
        topic_type,
        progress_task_key=task_key,
        progress_prefix=f"正在对{label}分词"
    )
    if not corpus:
        raise ValueError(f"{label}没有可用于 LDA 的文本。")
    update_task_status(
        task_key,
        status="running",
        stage="vectorize",
        message=f"正在构建{label}词袋矩阵（{len(corpus)} 条有效文本）"
    )
    vectorizer, dtm = build_lda_matrix(corpus)
    update_task_status(
        task_key,
        status="running",
        stage="train",
        message=f"正在训练{label}LDA 模型（{topic_count} 个主题）"
    )
    lda = create_lda_model(topic_count)
    lda.fit(dtm)
    # 保存该类型的主题关键词及权重
    feature_names = vectorizer.get_feature_names_out()
    topic_words = []
    topic_word_weights = []
    for topic in lda.components_:
        top_words_idx = topic.argsort()[:-11:-1]
        topic_words.append([feature_names[i] for i in top_words_idx])
        topic_sum = topic.sum()
        weights = [round(topic[i] / topic_sum, 3) for i in top_words_idx]
        topic_word_weights.append(weights)
    analysis_cache[topics_cache_key] = [
        {
            "topic_id": idx,
            "keywords": " ".join(words),
            "keywords_with_weights": [{"word": w, "weight": wt} for w, wt in zip(words, topic_word_weights[idx])]
        }
        for idx, words in enumerate(topic_words)
    ]
    update_task_status(
        task_key,
        status="running",
        stage="prepare",
        message=f"正在生成{label}交互式可视化"
    )
    vis_data = pyLDAvis.lda_model.prepare(lda, dtm, vectorizer)
    analysis_cache[cache_key] = pyLDAvis.prepared_data_to_html(vis_data)
    update_task_status(
        task_key,
        status="completed",
        stage="done",
        message=f"{label}交互式主题图已生成。",
        current=1,
        total=1,
        finished=True
    )

@app.route('/api/analysis/lda_topics', methods=['GET'])
def get_lda_topics():
    """获取特定类型的LDA主题关键词及权重"""
    topic_type = request.args.get('type', 'all')
    topic_count = normalize_topic_count(request.args.get('topics'), DEFAULT_LDA_TOPIC_COUNT)
    topics_cache_key = f"lda_topics_{topic_type}_{topic_count}"
    if topics_cache_key in analysis_cache:
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "topics": analysis_cache[topics_cache_key],
                "topic_count": topic_count,
                "type": topic_type
            }
        })
    # 如果缓存不存在，检查是否正在生成
    task_key = f"lda_pyldavis_task_{topic_type}_{topic_count}"
    task = get_task_status(task_key)
    if task.get("status") in ("queued", "running"):
        return jsonify({
            "code": 202,
            "message": task.get("message", "正在生成LDA主题数据，请稍候..."),
            "data": task
        }), 202
    # 启动生成任务
    start_background_task(
        task_key,
        lambda: build_lda_pyldavis_cache(topic_type, topic_count),
        f"正在启动 {LDA_TYPE_LABELS.get(topic_type, topic_type)} 的LDA主题生成任务..."
    )
    return jsonify({
        "code": 202,
        "message": "正在生成LDA主题数据，请稍候...",
        "data": get_task_status(task_key)
    }), 202

def build_lda_loading_html(topic_type, topic_count, task):
    label = LDA_TYPE_LABELS.get(topic_type, topic_type)
    title = f"{label} LDA 主题分析（{topic_count}个主题）"
    message = html.escape(task.get("message", "正在准备数据，请稍候..."))
    progress_text = ""
    hint_text = "页面会自动刷新，生成完成后会自动展示结果。"
    if task.get("total"):
        progress_text = f'{task.get("current", 0)}/{task.get("total", 0)} ({task.get("percent", 0)}%)'
    error_text = ""
    auto_refresh_script = ""
    if task.get("status") == "failed":
        hint_text = "任务执行失败，请刷新页面重试，或查看后端日志。"
        if task.get("error"):
            error_text = f'<div class="error">错误信息：{html.escape(task.get("error"))}</div>'
    else:
        auto_refresh_script = """
        <script>
            const nextUrl = new URL(window.location.href);
            nextUrl.searchParams.set('_ts', Date.now());
            setTimeout(() => window.location.replace(nextUrl.toString()), 2500);
        </script>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f0f2f5;
            color: #333;
        }}
        .wrap {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            box-sizing: border-box;
        }}
        .card {{
            width: min(720px, 100%);
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 10px 35px rgba(0, 0, 0, 0.08);
            padding: 32px;
            line-height: 1.7;
        }}
        h2 {{
            margin: 0 0 12px;
            font-size: 22px;
        }}
        .muted {{
            color: #666;
        }}
        .progress {{
            margin-top: 12px;
            font-weight: bold;
            color: #409eff;
        }}
        .hint {{
            margin-top: 16px;
            color: #888;
            font-size: 14px;
        }}
        .error {{
            margin-top: 16px;
            padding: 12px 14px;
            border-radius: 8px;
            background: #fff2f0;
            color: #cf1322;
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h2>{title}</h2>
            <div>{message}</div>
            <div class="progress">{progress_text}</div>
            <div class="hint">{hint_text}</div>
            {error_text}
        </div>
    </div>
    {auto_refresh_script}
</body>
</html>"""

@app.route('/api/analysis/lda_summary', methods=['GET'])
def get_lda_summary():
    if "lda_summary" in analysis_cache:
        return jsonify(analysis_cache["lda_summary"])
    task_key = "lda_summary_task"
    task = get_task_status(task_key)
    if task.get("status") == "failed":
        start_background_task(task_key, build_lda_summary_cache, "检测到上次 LDA 汇总失败，正在重新启动任务...")
        task = get_task_status(task_key)
    if task.get("status") not in ("queued", "running"):
        start_background_task(task_key, build_lda_summary_cache, "正在启动 LDA 汇总任务...")
        task = get_task_status(task_key)
    return jsonify({
        "code": 202,
        "message": task.get("message", "正在生成 LDA 汇总，请稍候..."),
        "data": task
    }), 202

@app.route('/api/analysis/lda_pyldavis', methods=['GET'])
def get_lda_pyldavis():
    topic_type = request.args.get('type', 'pos') # pos 或 neg 或 all
    topic_count = normalize_topic_count(request.args.get('topics'), DEFAULT_LDA_TOPIC_COUNT)
    cache_key = f"lda_pyldavis_{topic_type}_{topic_count}"
    if cache_key in analysis_cache:
        return analysis_cache[cache_key]
    task_key = f"lda_pyldavis_task_{topic_type}_{topic_count}"
    task = get_task_status(task_key)
    if task.get("status") == "failed":
        start_background_task(
            task_key,
            lambda: build_lda_pyldavis_cache(topic_type, topic_count),
            f"检测到 {LDA_TYPE_LABELS.get(topic_type, topic_type)} 的交互式主题图上次生成失败，正在重新启动任务..."
        )
        task = get_task_status(task_key)
    if task.get("status") not in ("queued", "running"):
        start_background_task(
            task_key,
            lambda: build_lda_pyldavis_cache(topic_type, topic_count),
            f"正在启动 {LDA_TYPE_LABELS.get(topic_type, topic_type)} 的交互式主题图生成任务..."
        )
        task = get_task_status(task_key)
    status_code = 500 if task.get("status") == "failed" else 202
    return build_lda_loading_html(topic_type, topic_count, task), status_code

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
