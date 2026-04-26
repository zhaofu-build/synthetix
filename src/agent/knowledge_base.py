"""
项目级知识库 RAG 模块

轻量级实现：BM25 关键词检索 + 简单向量检索（无外部依赖）。
支持存储素材分析结果、用户文档，供 Agent 检索使用。
"""
import json
import math
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).parent.parent.parent / "src" / "db" / "knowledge"


def _ensure_dir():
    _KB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Document:
    """知识库文档"""
    id: str
    content: str
    source: str = ""
    tags: List[str] = field(default_factory=list)
    project_id: Optional[int] = None


class SimpleBM25:
    """轻量级 BM25 检索引擎"""

    def __init__(self):
        self.docs: List[Document] = []
        self.doc_freqs: Dict[str, int] = defaultdict(int)
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：按空格和标点分割，转小写"""
        import re
        tokens = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text.lower())
        return tokens

    def add_document(self, doc: Document):
        self.docs.append(doc)
        tokens = self._tokenize(doc.content)
        self.doc_lengths.append(len(tokens))
        seen = set()
        for t in tokens:
            if t not in seen:
                self.doc_freqs[t] += 1
                seen.add(t)
        self.avg_dl = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 1.0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        """BM25 检索"""
        if not self.docs:
            return []

        query_tokens = self._tokenize(query)
        scores = []
        n_docs = len(self.docs)
        k1, b = 1.5, 0.75

        for i, doc in enumerate(self.docs):
            score = 0.0
            dl = self.doc_lengths[i]
            doc_tokens = self._tokenize(doc.content)
            tf_map = defaultdict(int)
            for t in doc_tokens:
                tf_map[t] += 1

            for qt in query_tokens:
                if qt not in tf_map:
                    continue
                tf = tf_map[qt]
                df = self.doc_freqs.get(qt, 0)
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                tf_score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self.avg_dl))
                score += idf * tf_score

            if score > 0:
                scores.append((doc, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class SimpleVectorIndex:
    """轻量级向量检索（通过 core-nexus embedding API）"""

    def __init__(self):
        self.vectors: Dict[str, List[float]] = {}

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        try:
            from src.shared.utils.core_nexus_client import get_client
            client = get_client()
            resp = client._request("POST", "/embedding", json={"input": text[:512]})
            if resp and "data" in resp and resp["data"]:
                return resp["data"][0].get("embedding", [])
        except Exception as e:
            logger.debug(f"Embedding 获取失败: {e}")
        return None

    def add(self, doc_id: str, content: str):
        vec = self._get_embedding(content)
        if vec:
            self.vectors[doc_id] = vec

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        query_vec = self._get_embedding(query)
        if not query_vec or not self.vectors:
            return []
        scores = []
        for doc_id, doc_vec in self.vectors.items():
            sim = self._cosine_sim(query_vec, doc_vec)
            if sim > 0:
                scores.append((doc_id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


class KnowledgeBase:
    """项目级知识库（支持 BM25 / 向量 / 混合检索）"""

    MODE_BM25 = "bm25"
    MODE_VECTOR = "vector"
    MODE_HYBRID = "hybrid"

    def __init__(self, project_id: int, mode: str = "hybrid"):
        self.project_id = project_id
        self.engine = SimpleBM25()
        self.vector_index = SimpleVectorIndex()
        self._doc_counter = 0
        self._path = _KB_DIR / f"project_{project_id}.json"
        self.mode = mode
        self.load()

    def add(self, content: str, source: str = "", tags: List[str] = None):
        """添加文档到知识库"""
        self._doc_counter += 1
        doc = Document(
            id=f"doc_{self._doc_counter}",
            content=content,
            source=source,
            tags=tags or [],
            project_id=self.project_id,
        )
        self.engine.add_document(doc)
        self.vector_index.add(doc.id, content)
        self.save()

    def search(self, query: str, top_k: int = 5, mode: str = None) -> List[Dict]:
        """检索相关文档

        Args:
            query: 查询文本
            top_k: 返回数量
            mode: "bm25" / "vector" / "hybrid"（默认使用实例 mode）
        """
        search_mode = mode or self.mode

        if search_mode == self.MODE_BM25:
            return self._search_bm25(query, top_k)
        elif search_mode == self.MODE_VECTOR:
            return self._search_vector(query, top_k)
        else:
            return self._search_hybrid(query, top_k)

    def _search_bm25(self, query: str, top_k: int) -> List[Dict]:
        results = self.engine.search(query, top_k)
        return [{"id": doc.id, "content": doc.content, "source": doc.source, "score": round(score, 3)}
                for doc, score in results]

    def _search_vector(self, query: str, top_k: int) -> List[Dict]:
        vec_results = self.vector_index.search(query, top_k)
        doc_map = {doc.id: doc for doc in self.engine.docs}
        results = []
        for doc_id, score in vec_results:
            doc = doc_map.get(doc_id)
            if doc:
                results.append({"id": doc.id, "content": doc.content, "source": doc.source, "score": round(score, 3)})
        return results

    def _search_hybrid(self, query: str, top_k: int) -> List[Dict]:
        bm25_weight = 0.4
        vec_weight = 0.6

        bm25_results = self.engine.search(query, top_k * 2)
        vec_results = self.vector_index.search(query, top_k * 2)

        bm25_scores = {doc.id: score for doc, score in bm25_results}
        vec_scores = {doc_id: score for doc_id, score in vec_results}

        all_ids = set(bm25_scores.keys()) | set(vec_scores.keys())
        doc_map = {doc.id: doc for doc in self.engine.docs}

        max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0
        max_vec = max(vec_scores.values()) if vec_scores else 1.0

        combined = []
        for doc_id in all_ids:
            bm25_s = (bm25_scores.get(doc_id, 0) / max_bm25) if max_bm25 > 0 else 0
            vec_s = (vec_scores.get(doc_id, 0) / max_vec) if max_vec > 0 else 0
            final_score = bm25_weight * bm25_s + vec_weight * vec_s
            doc = doc_map.get(doc_id)
            if doc:
                combined.append({"id": doc.id, "content": doc.content, "source": doc.source, "score": round(final_score, 3)})

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    def save(self):
        """持久化到文件"""
        _ensure_dir()
        data = {
            "project_id": self.project_id,
            "counter": self._doc_counter,
            "documents": [
                {"id": doc.id, "content": doc.content, "source": doc.source, "tags": doc.tags}
                for doc in self.engine.docs
            ],
        }
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"知识库保存失败: {e}")

    def load(self):
        """从文件加载"""
        if not self._path.is_file():
            return
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._doc_counter = data.get("counter", 0)
            for doc_data in data.get("documents", []):
                doc = Document(
                    id=doc_data["id"],
                    content=doc_data["content"],
                    source=doc_data.get("source", ""),
                    tags=doc_data.get("tags", []),
                    project_id=self.project_id,
                )
                self.engine.add_document(doc)
        except Exception as e:
            logger.warning(f"知识库加载失败: {e}")

    def clear(self):
        """清空知识库"""
        self.engine = SimpleBM25()
        self._doc_counter = 0
        self.save()

    # ==================== 自动积累与分类 ====================

    CATEGORIES = {
        "analysis": ["分析", "场景", "画面", "描述", "视觉", "analyze"],
        "audio": ["音频", "转录", "语音", "ASR", "说话人", "transcri"],
        "editing": ["剪切", "合并", "剪辑", "裁剪", "cut", "merge"],
        "creative": ["文案", "创意", "风格", "模板", "creative"],
        "technical": ["FFmpeg", "编码", "渲染", "分辨率", "fps", "codec"],
    }

    def auto_accumulate(self, tool_name: str, result: Dict):
        """从工具执行结果自动提取知识"""
        if not result.get("success"):
            return

        # Determine category
        category = "general"
        for cat, keywords in self.CATEGORIES.items():
            if any(kw.lower() in tool_name.lower() for kw in keywords):
                category = cat
                break

        # Extract knowledge based on tool type
        if tool_name in ("analyze_video", "analyze_video_vl"):
            content = result.get("description") or result.get("summary") or ""
            if content:
                self.add(content, source=f"tool:{tool_name}", tags=[category, "auto"])

        elif tool_name == "transcribe_video":
            subtitle = result.get("subtitle", "")
            if subtitle:
                summary = subtitle[:500] + ("..." if len(subtitle) > 500 else "")
                self.add(f"转录内容摘要: {summary}", source="tool:transcribe", tags=["audio", "auto"])

        elif tool_name == "smart_clip":
            clips = result.get("clips", [])
            if clips:
                desc = "; ".join(f"{c.get('start','')}-{c.get('end','')}" for c in clips[:5])
                self.add(f"智能剪辑片段: {desc}", source="tool:smart_clip", tags=["editing", "auto"])

        elif tool_name == "quality_check":
            score = result.get("score", 0)
            issues = result.get("issues", [])
            self.add(f"质量评分: {score}, 问题: {', '.join(issues[:3])}", source="tool:quality_check", tags=["technical", "auto"])

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        docs = self.engine.docs
        categories = defaultdict(int)
        for doc in docs:
            for tag in doc.tags:
                categories[tag] += 1
        return {
            "total_documents": len(docs),
            "categories": dict(categories),
            "sources": list(set(doc.source for doc in docs if doc.source)),
        }

    def preload_domain_knowledge(self, domain: str = "video_editing"):
        """预加载领域基础知识"""
        domain_docs = {
            "video_editing": [
                ("视频剪辑基本术语: 剪切(cut)、合并(merge)、转场(transition)、关键帧(keyframe)", "基础知识", ["editing"]),
                ("常见视频分辨率: 720p(1280x720), 1080p(1920x1080), 4K(3840x2160)", "基础知识", ["technical"]),
                ("常见视频编码: H.264(兼容性好), H.265/HEVC(压缩率高), AV1(新一代)", "基础知识", ["technical"]),
                ("FFmpeg 常用参数: -crf 质量控制(18-28), -preset 编码速度, -r 帧率", "基础知识", ["technical"]),
                ("音频处理基础: 采样率44.1kHz/48kHz, 比特率128-320kbps, 声道mono/stereo", "基础知识", ["audio"]),
            ],
        }

        for content, source, tags in domain_docs.get(domain, []):
            if not any(doc.content == content for doc in self.engine.docs):
                self.add(content, source=source, tags=tags + ["domain"])


# 缓存
_kbs: Dict[int, KnowledgeBase] = {}


def get_knowledge_base(project_id: int) -> KnowledgeBase:
    """获取项目知识库"""
    if project_id not in _kbs:
        _kbs[project_id] = KnowledgeBase(project_id)
    return _kbs[project_id]
