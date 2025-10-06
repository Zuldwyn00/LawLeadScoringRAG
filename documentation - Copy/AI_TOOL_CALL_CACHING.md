# AI Tool Call Caching Strategy

Comprehensive guide for caching AI-generated responses to reduce API costs and improve performance.

---

## 🎯 What to Cache

### High-Value Cacheable AI Responses
- **Document Summaries**: LLM-generated summaries of case documents
- **Metadata Extractions**: AI-extracted structured data from text chunks
- **Confidence Assessments**: AI confidence scores for specific case analyses
- **Case Comparisons**: AI analysis comparing new leads to historical cases
- **Legal Precedent Analysis**: AI interpretation of case law relevance

### Cache Priority by Cost/Benefit
1. **Document Summaries** (Highest ROI)
   - Cost: $0.02-0.10 per summary
   - Reuse potential: 60-80%
   - Cache for: 30-90 days

2. **Metadata Extractions** (High ROI)
   - Cost: $0.01-0.03 per extraction
   - Reuse potential: 70-90%
   - Cache for: 90+ days (rarely changes)

3. **Confidence Assessments** (Medium ROI)
   - Cost: $0.005-0.02 per assessment
   - Reuse potential: 20-40%
   - Cache for: 1-7 days

---

## 🛠 Caching Technology Options

### Option 1: Redis (Recommended for Production)

**Pros:**
- In-memory speed (sub-millisecond retrieval)
- Built-in TTL (time-to-live) support
- Persistence options available
- Clustering for high availability
- Rich data types (strings, hashes, lists)

**Cons:**
- Memory usage costs
- Requires separate infrastructure
- Data lost if not persisted

**Best For:** High-frequency access, fast retrieval, distributed systems

```python
# Redis Implementation Example
import redis
import json
import hashlib
from datetime import timedelta

class RedisAICache:
    def __init__(self):
        self.client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    
    def cache_document_summary(self, document_path: str, summary_type: str, 
                              summary: str, ttl_days: int = 30):
        """Cache LLM document summary"""
        cache_key = self._generate_summary_key(document_path, summary_type)
        self.client.setex(
            cache_key,
            timedelta(days=ttl_days),
            summary
        )
    
    def get_document_summary(self, document_path: str, summary_type: str) -> str:
        """Retrieve cached summary or None"""
        cache_key = self._generate_summary_key(document_path, summary_type)
        return self.client.get(cache_key)
    
    def _generate_summary_key(self, document_path: str, summary_type: str) -> str:
        """Generate consistent cache key"""
        doc_hash = self._hash_file_content(document_path)
        return f"ai_summary:{doc_hash}:{summary_type}"
```

### Option 2: SQLite/PostgreSQL Database Cache

**Pros:**
- Persistent storage
- ACID transactions
- Complex queries possible
- No additional infrastructure for SQLite
- Backup/restore capabilities

**Cons:**
- Slower than in-memory solutions
- Requires disk I/O
- May need indexing optimization

**Best For:** Long-term storage, audit trails, complex cache queries

```python
# Database Cache Implementation
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta

class DatabaseAICache:
    def __init__(self, db_path: str = "ai_cache.db"):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Initialize cache tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_responses (
                    cache_key TEXT PRIMARY KEY,
                    response_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    cost_saved REAL DEFAULT 0.0,
                    hit_count INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON ai_responses(expires_at);
                CREATE INDEX IF NOT EXISTS idx_response_type ON ai_responses(response_type);
            """)
    
    def cache_ai_response(self, cache_key: str, response_type: str, 
                         content: str, ttl_hours: int = 720, cost_saved: float = 0.0):
        """Store AI response with expiration"""
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ai_responses 
                (cache_key, response_type, content, expires_at, cost_saved)
                VALUES (?, ?, ?, ?, ?)
            """, (cache_key, response_type, content, expires_at, cost_saved))
    
    def get_ai_response(self, cache_key: str) -> str:
        """Retrieve cached response if not expired"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content FROM ai_responses 
                WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
            """, (cache_key,))
            
            result = cursor.fetchone()
            if result:
                # Increment hit counter
                conn.execute("""
                    UPDATE ai_responses SET hit_count = hit_count + 1 
                    WHERE cache_key = ?
                """, (cache_key,))
                return result[0]
        return None
```

### Option 3: File-Based Caching

**Pros:**
- Simple implementation
- No external dependencies
- Easy to inspect/debug
- Platform independent

**Cons:**
- Slower file I/O
- No automatic expiration
- Manual cleanup required
- No concurrent access protection

**Best For:** Development, small-scale deployment, simple use cases

```python
# File-Based Cache Implementation
import os
import json
import pickle
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

class FileAICache:
    def __init__(self, cache_dir: str = "./ai_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def cache_ai_response(self, cache_key: str, content: str, ttl_hours: int = 24):
        """Store AI response as file"""
        cache_data = {
            'content': content,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
        }
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    def get_ai_response(self, cache_key: str) -> str:
        """Retrieve cached response if not expired"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            expires_at = datetime.fromisoformat(cache_data['expires_at'])
            if datetime.now() > expires_at:
                cache_file.unlink()  # Delete expired cache
                return None
                
            return cache_data['content']
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
```

### Option 4: Hybrid Approach (Recommended)

**Strategy:** Redis for hot cache + Database for persistent storage

```python
class HybridAICache:
    def __init__(self):
        self.redis_cache = RedisAICache()
        self.db_cache = DatabaseAICache()
    
    def get_ai_response(self, cache_key: str) -> str:
        """Try Redis first, fallback to database"""
        # Check Redis (fast)
        result = self.redis_cache.get(cache_key)
        if result:
            return result
        
        # Check database (slower but persistent)
        result = self.db_cache.get_ai_response(cache_key)
        if result:
            # Promote to Redis for faster future access
            self.redis_cache.store(cache_key, result, ttl_hours=24)
            return result
        
        return None
    
    def cache_ai_response(self, cache_key: str, content: str, **kwargs):
        """Store in both Redis and database"""
        self.redis_cache.store(cache_key, content, **kwargs)
        self.db_cache.cache_ai_response(cache_key, content, **kwargs)
```

---

## 🔑 Cache Key Strategies

### Document Summary Keys
```python
def generate_summary_cache_key(document_path: str, summary_type: str, 
                              focus_area: str = None) -> str:
    """Generate deterministic cache key for document summaries"""
    
    # Hash file content for consistency
    with open(document_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()[:16]
    
    # Include summary parameters
    key_components = [
        "doc_summary",
        file_hash,
        summary_type,
        focus_area or "general"
    ]
    
    return ":".join(filter(None, key_components))

# Examples:
# "doc_summary:a1b2c3d4e5f6g7h8:liability_focused:medical_records"
# "doc_summary:x9y8z7w6v5u4t3s2:general"
```

### Metadata Extraction Keys
```python
def generate_metadata_cache_key(text_chunk: str, extraction_type: str) -> str:
    """Generate cache key for metadata extractions"""
    
    # Hash the text content
    text_hash = hashlib.md5(text_chunk.encode()).hexdigest()[:16]
    
    return f"metadata:{text_hash}:{extraction_type}"

# Examples:
# "metadata:f1e2d3c4b5a6987:injury_classification"
# "metadata:9z8y7x6w5v4u3t2:case_timeline"
```

### Confidence Assessment Keys
```python
def generate_confidence_cache_key(lead_features: dict, context_hash: str) -> str:
    """Generate cache key for confidence assessments"""
    
    # Create stable hash of lead features
    features_str = json.dumps(lead_features, sort_keys=True)
    features_hash = hashlib.md5(features_str.encode()).hexdigest()[:16]
    
    return f"confidence:{features_hash}:{context_hash[:16]}"
```

---

## ⚙️ Implementation Integration

### Enhanced Tool Manager with Caching

```python
class CachedToolManager:
    def __init__(self, cache_backend: str = "hybrid"):
        self.cache = self._init_cache(cache_backend)
        self.tool_map = {
            'get_file_content': self._cached_file_content,
            'summarize_document': self._cached_summarize,
            'extract_metadata': self._cached_metadata
        }
    
    def _cached_summarize(self, document_path: str, focus: str = "general") -> str:
        """Cached document summarization"""
        cache_key = generate_summary_cache_key(document_path, "summary", focus)
        
        # Try cache first
        cached_result = self.cache.get_ai_response(cache_key)
        if cached_result:
            logger.info(f"Cache HIT for summary: {cache_key}")
            return cached_result
        
        # Cache miss - call AI
        logger.info(f"Cache MISS for summary: {cache_key}")
        result = self._call_summarization_ai(document_path, focus)
        
        # Cache the result
        self.cache.cache_ai_response(
            cache_key, 
            result, 
            ttl_hours=720,  # 30 days
            cost_saved=0.05  # Estimated API cost
        )
        
        return result
    
    def _cached_metadata(self, text: str, extraction_type: str) -> dict:
        """Cached metadata extraction"""
        cache_key = generate_metadata_cache_key(text, extraction_type)
        
        cached_result = self.cache.get_ai_response(cache_key)
        if cached_result:
            return json.loads(cached_result)
        
        # Extract metadata with AI
        result = self._call_metadata_ai(text, extraction_type)
        
        # Cache as JSON string
        self.cache.cache_ai_response(
            cache_key,
            json.dumps(result),
            ttl_hours=2160,  # 90 days
            cost_saved=0.02
        )
        
        return result
```

### Cache-Aware Lead Scorer

```python
class CachedLeadScorer(LeadScorer):
    def __init__(self):
        super().__init__()
        self.cache = HybridAICache()
        self.tool_manager = CachedToolManager()
    
    def score_lead_with_cache(self, description: str) -> LeadScore:
        """Score lead using cached AI responses when possible"""
        
        # Check if we have cached analysis for similar lead
        lead_hash = self._hash_lead_description(description)
        cache_key = f"lead_analysis:{lead_hash}"
        
        cached_analysis = self.cache.get_ai_response(cache_key)
        if cached_analysis:
            logger.info("Using cached lead analysis")
            return LeadScore.from_json(cached_analysis)
        
        # Perform analysis with cached tools
        result = super().score_lead(description)
        
        # Cache the final analysis
        self.cache.cache_ai_response(
            cache_key,
            result.to_json(),
            ttl_hours=24,  # 1 day
            cost_saved=0.15  # Total API costs saved
        )
        
        return result
```

---

## 📊 Cache Performance Monitoring

### Cache Analytics Dashboard

```python
class CacheAnalytics:
    def __init__(self, cache: HybridAICache):
        self.cache = cache
    
    def get_performance_metrics(self) -> dict:
        """Get comprehensive cache performance data"""
        return {
            'hit_rates': self._calculate_hit_rates(),
            'cost_savings': self._calculate_cost_savings(),
            'response_time_improvement': self._calculate_speed_gains(),
            'cache_efficiency': self._calculate_efficiency(),
            'storage_usage': self._get_storage_stats()
        }
    
    def _calculate_hit_rates(self) -> dict:
        """Calculate hit rates by response type"""
        with self.cache.db_cache.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    response_type,
                    SUM(hit_count) as total_hits,
                    COUNT(*) as total_entries,
                    AVG(hit_count) as avg_hits_per_entry
                FROM ai_responses 
                WHERE expires_at > CURRENT_TIMESTAMP
                GROUP BY response_type
            """)
            
            return {row[0]: {
                'total_hits': row[1],
                'total_entries': row[2],
                'avg_hits': row[3]
            } for row in cursor.fetchall()}
    
    def _calculate_cost_savings(self) -> dict:
        """Calculate total and projected cost savings"""
        with self.cache.db_cache.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    SUM(cost_saved * hit_count) as total_saved,
                    AVG(cost_saved) as avg_cost_per_call
                FROM ai_responses
                WHERE hit_count > 0
            """)
            
            result = cursor.fetchone()
            return {
                'total_saved': result[0] or 0,
                'avg_cost_per_call': result[1] or 0,
                'projected_monthly_savings': (result[0] or 0) * 30
            }
```

---

## 🚀 Implementation Roadmap

### Phase 1: Basic Caching (Week 1-2)
- [ ] Choose cache backend (Redis recommended)
- [ ] Implement cache for document summaries
- [ ] Add cache key generation utilities
- [ ] Basic hit/miss logging

### Phase 2: Enhanced Caching (Week 3-4)
- [ ] Add metadata extraction caching
- [ ] Implement confidence assessment caching
- [ ] Add TTL configuration by response type
- [ ] Cache invalidation strategies

### Phase 3: Production Optimization (Week 5-6)
- [ ] Hybrid Redis + Database approach
- [ ] Cache analytics and monitoring
- [ ] Performance optimization
- [ ] Cost tracking and reporting

### Phase 4: Advanced Features (Week 7-8)
- [ ] Predictive cache warming
- [ ] Intelligent cache eviction
- [ ] Cross-session cache sharing
- [ ] Cache backup and recovery

---

## 💰 Expected ROI

### Cost Reduction Projections
- **Document Summaries**: 70% cache hit rate → 70% cost reduction
- **Metadata Extractions**: 80% cache hit rate → 80% cost reduction  
- **Overall AI Tool Costs**: 60-75% reduction after 30 days

### Performance Improvements
- **Cache Hit Response Time**: < 50ms (vs 5-15 seconds for AI calls)
- **Overall Lead Scoring Speed**: 40-60% faster
- **User Experience**: Near-instant responses for common cases

### Example Monthly Savings
```
Current Monthly AI Costs: $500
With 70% Cache Hit Rate: $150
Monthly Savings: $350 (70% reduction)
Annual Savings: $4,200
```

Cache implementation pays for itself within the first month while dramatically improving user experience. 