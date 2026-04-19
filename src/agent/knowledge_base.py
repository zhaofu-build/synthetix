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


class KnowledgeBase:
    """项目级知识库"""

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.engine = SimpleBM25()
        self._doc_counter = 0
        self._path = _KB_DIR / f"project_{project_id}.json"
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
        self.save()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索相关文档"""
        results = self.engine.search(query, top_k)
        return [{"id": doc.id, "content": doc.content, "source": doc.source, "score": round(score, 3)}
                for doc, score in results]

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


# 缓存
_kbs: Dict[int, KnowledgeBase] = {}


def get_knowledge_base(project_id: int) -> KnowledgeBase:
    """获取项目知识库"""
    if project_id not in _kbs:
        _kbs[project_id] = KnowledgeBase(project_id)
    return _kbs[project_id]
