<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Non-LLM NLP Fallback Options for Intent Resolution & Search Enhancement

## Summary

Feature Name: Non-LLM Intent Resolution & Search Enhancement
Feature Description: Lightweight NLP capabilities for understanding developer intent/goals and augmenting search/retrieval/filtering when LLM-based approaches are unavailable
Feature Goal: Provide credible backup options for intent analysis and search enhancement without heavy dependencies

Primary External Surface(s): TF-IDF vectorization, topic modeling, text similarity, classification pipelines

Integration Confidence: High - Multiple proven approaches with clear integration paths

## Core Analysis

### The Challenge
CodeWeaver needs robust fallback systems for:
1. **Intent/Goal Resolution**: Understanding what developers are looking for in natural language queries
2. **Search Enhancement**: Improving retrieval accuracy and relevance ranking
3. **Filtering Intelligence**: Smart content filtering based on semantic similarity

### Dependency Weight Considerations
The team's concern about "pretty heavy dependencies" is valid. Here's the dependency analysis:

**Lightweight** (< 50MB total):
- scikit-learn + basic requirements: ~45MB
- Pure Python solutions: ~10-20MB

**Medium Weight** (50-200MB):
- gensim + dependencies: ~80-120MB  
- spaCy small models: ~15MB core + 50MB models

**Heavy** (200MB+):
- spaCy large models: ~500MB+
- Full transformer models: 1GB+

## Recommended Approach: Tiered Fallback System

### Tier 1: Minimal Dependency Core (Recommended Starting Point)

**Primary Choice: scikit-learn + Basic NLP**

**Core Components:**
```python
# Minimal dependencies
sklearn.feature_extraction.text.TfidfVectorizer
sklearn.metrics.pairwise.cosine_similarity  
sklearn.naive_bayes.MultinomialNB
sklearn.cluster.KMeans
```

**Capabilities:**
- TF-IDF vectorization for text representation
- Cosine similarity for document/query matching
- Naive Bayes for intent classification
- K-means for topic clustering
- BM25-style ranking (implementable with TF-IDF)

**Dependency Footprint:** ~45MB
**Integration Confidence:** High (95%)

### Tier 2: Enhanced NLP (Optional Upgrade)

**Primary Choice: gensim 4.3+**

**Key Features:**
```python
# Core gensim capabilities for CodeWeaver
gensim.models.LdaModel          # Topic modeling
gensim.models.TfidfModel        # TF-IDF transformation  
gensim.similarities.Similarity   # Document similarity
gensim.corpora.Dictionary       # Vocabulary management
```

**Capabilities:**
- Advanced topic modeling (LDA, LSI)
- Document similarity with multiple algorithms
- Semantic space modeling
- Efficient large corpus handling

**Dependency Footprint:** ~80-120MB
**Integration Confidence:** High (90%)

### Tier 3: Full NLP Pipeline (Advanced Option)

**Primary Choice: spaCy 3.8+ (small models)**

**Key Features:**
```python
# spaCy core pipeline
nlp = spacy.load("en_core_web_sm")  # Small model (~50MB)
# Text processing pipeline
# Named entity recognition  
# Part-of-speech tagging
# Dependency parsing
```

**Capabilities:**
- Advanced text preprocessing
- Named entity recognition for code entities
- Semantic similarity with word vectors
- Pipeline components for custom processing

**Dependency Footprint:** ~100-150MB
**Integration Confidence:** High (88%)

## Implementation Strategy

### Phase 1: Core Intent Resolution

**Use Case:** Understanding queries like "find authentication code", "show API endpoints", "locate error handling"

**Implementation:**
```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.naive_bayes import MultinomialNB

# Intent classification training
vectorizer = TfidfVectorizer(
    stop_words='english',
    ngram_range=(1, 2),  # unigrams + bigrams
    max_features=5000
)

# Similarity-based retrieval
def find_relevant_code(query, code_corpus):
    query_vec = vectorizer.transform([query])
    corpus_vecs = vectorizer.transform(code_corpus)
    similarities = cosine_similarity(query_vec, corpus_vecs)
    return similarities.argsort()[0][-10:]  # Top 10 matches
```

### Phase 2: Enhanced Topic Modeling (Optional)

**Use Case:** Discovering code themes, clustering related functionality

**Implementation with gensim:**
```python
from gensim import corpora, models

# Create dictionary and corpus
dictionary = corpora.Dictionary(tokenized_documents)
corpus = [dictionary.doc2bow(doc) for doc in tokenized_documents]

# Train LDA model
lda_model = models.LdaModel(
    corpus=corpus,
    num_topics=20,
    id2word=dictionary,
    passes=10
)

# Get topic distribution for new query
query_bow = dictionary.doc2bow(query_tokens)
topic_distribution = lda_model[query_bow]
```

### Phase 3: Advanced Processing (Future)

**Use Case:** Complex entity extraction, advanced semantic understanding

**Implementation with spaCy:**
```python
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_code_entities(text):
    doc = nlp(text)
    entities = {
        'functions': [ent.text for ent in doc.ents if ent.label_ == 'FUNCTION'],
        'variables': [token.text for token in doc if token.pos_ == 'NOUN'],
        'actions': [token.lemma_ for token in doc if token.pos_ == 'VERB']
    }
    return entities
```

## Alternative Lightweight Solutions

### Option A: BM25 + Minimal Classification

**Libraries:** `rank_bm25` (5MB) + basic scikit-learn
**Use Case:** Search ranking without complex topic modeling

```python
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import CountVectorizer

tokenized_corpus = [doc.split() for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)
scores = bm25.get_scores(query.split())
```

### Option B: Custom Lightweight Implementation

**Pure Python Solution (~10MB)**
- Custom TF-IDF implementation
- Basic cosine similarity
- Simple classification logic
- Minimal external dependencies

### Option C: Hybrid Approach

**Combining multiple lightweight tools:**
- `textstat` for readability metrics (2MB)
- `nltk.corpus.stopwords` for stop words (minimal)
- Custom similarity functions
- scikit-learn for classification

## Integration Patterns for CodeWeaver

### 1. Fallback Chain Architecture

```python
class IntentResolver:
    def __init__(self):
        self.primary_llm = None  # LLM-based resolver
        self.fallback_ml = SklearnResolver()  # Tier 1
        self.fallback_gensim = GensimResolver()  # Tier 2 (optional)
        
    def resolve_intent(self, query):
        try:
            if self.primary_llm and self.primary_llm.available():
                return self.primary_llm.resolve(query)
        except Exception:
            pass
            
        try:
            return self.fallback_ml.resolve(query)
        except Exception:
            return self.fallback_gensim.resolve(query)
```

### 2. Feature Flag System

```python
# In pydantic-settings config
class CodeWeaverConfig(BaseSettings):
    enable_gensim: bool = False
    enable_spacy: bool = False
    fallback_only_mode: bool = False
    min_similarity_threshold: float = 0.1
```

### 3. Progressive Enhancement

```python
# Start minimal, add features as needed
base_capabilities = ["tfidf", "cosine_similarity", "naive_bayes"]
enhanced_capabilities = ["lda_topics", "advanced_similarity", "clustering"]  
advanced_capabilities = ["ner", "pos_tagging", "dependency_parsing"]
```

## Performance Characteristics

### Memory Usage (Approximate)
- **Tier 1 (scikit-learn)**: 20-50MB runtime
- **Tier 2 (+gensim)**: 50-150MB runtime  
- **Tier 3 (+spaCy)**: 100-300MB runtime

### Processing Speed
- **TF-IDF + Cosine Similarity**: ~1-10ms per query
- **Topic Model Inference**: ~10-100ms per query
- **Full NLP Pipeline**: ~50-500ms per query

### Accuracy Expectations
- **Basic similarity**: 60-75% relevance
- **Enhanced topic modeling**: 70-80% relevance
- **Full NLP pipeline**: 75-85% relevance

## Synthetic Training Data Generation Strategy

**Resolved: No existing training data, but can generate using CodeWeaver's own capabilities**

This is an excellent approach that creates a self-improving system. Here's the recommended implementation:

### Phase 1: Automated Training Data Generation

**Use CodeWeaver + pydantic-ai + pydantic-evals pipeline:**

```python
# Training data generation workflow
class TrainingDataGenerator:
    def __init__(self, llm_client, codebase_analyzer):
        self.llm = llm_client  # pydantic-ai client
        self.analyzer = codebase_analyzer  # CodeWeaver analysis
        self.evaluator = pydantic_evals.Evaluator()
    
    async def generate_realistic_scenarios(self, codebase_path):
        # 1. Analyze codebase structure
        code_analysis = await self.analyzer.analyze_codebase(codebase_path)
        
        # 2. Generate realistic developer tasks
        scenarios = await self.llm.generate_scenarios(
            prompt=f"""
            Given this codebase analysis: {code_analysis}
            Generate 50 realistic developer queries for common tasks:
            - Finding authentication/auth code
            - Locating API endpoints 
            - Understanding error handling
            - Finding database models
            - Locating configuration code
            - etc.
            """,
            model="gpt-4"  # or chosen provider
        )
        
        # 3. Generate corresponding find_code calls
        training_pairs = []
        for scenario in scenarios:
            find_code_call = await self.llm.generate_tool_call(
                query=scenario.user_intent,
                codebase_context=code_analysis,
                expected_tool="find_code"
            )
            training_pairs.append((scenario.user_intent, find_code_call))
        
        return training_pairs

    async def validate_training_data(self, training_pairs):
        # Use pydantic-evals to validate quality
        return await self.evaluator.evaluate_batch(
            training_pairs,
            criteria=["relevance", "accuracy", "completeness"]
        )
```

### Phase 2: Continuous Data Augmentation

**Leverage GitHub codebases for diversity:**

```python
class GitHubTrainingAugmenter:
    def __init__(self, github_client):
        self.github = github_client
        
    async def augment_training_data(self, target_languages=["python", "typescript"]):
        popular_repos = await self.github.get_popular_repos(
            languages=target_languages,
            min_stars=1000,
            sample_size=50
        )
        
        augmented_data = []
        for repo in popular_repos:
            # Generate context-specific queries for each repo type
            repo_context = await self.analyze_repo_patterns(repo)
            scenarios = await self.generate_repo_specific_scenarios(repo_context)
            augmented_data.extend(scenarios)
            
        return augmented_data
```

### Phase 3: Intent Classification Training

**Train lightweight classifier on synthetic data:**

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

class IntentClassifier:
    def __init__(self):
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                stop_words='english',
                ngram_range=(1, 3),  # Include trigrams for code patterns
                max_features=10000
            )),
            ('classifier', MultinomialNB(alpha=0.1))
        ])
        
    def train_on_synthetic_data(self, training_pairs):
        queries = [pair[0] for pair in training_pairs]
        # Extract intent categories from find_code parameters
        intents = [self.extract_intent_category(pair[1]) for pair in training_pairs]
        
        self.pipeline.fit(queries, intents)
        return self
        
    def extract_intent_category(self, find_code_call):
        # Parse find_code parameters to determine intent type
        if "auth" in find_code_call.lower():
            return "authentication"
        elif "api" in find_code_call.lower():
            return "api_endpoints" 
        elif "error" in find_code_call.lower():
            return "error_handling"
        # ... more categories
        return "general_search"
```

## Updated Implementation Strategy

### Enhanced Phase 1: Bootstrap with Synthetic Data (Weeks 1-2)

1. **Generate Initial Training Set**
   - Use CodeWeaver on 10-20 diverse codebases
   - Generate 1000+ realistic query/intent pairs
   - Validate with pydantic-evals

2. **Train Lightweight Models**
   - Intent classification (Naive Bayes/SVM)
   - Query-to-parameters mapping
   - Relevance scoring

3. **Implement Fallback System**
   - Tier 1 scikit-learn implementation
   - Integration with existing pydantic-graph pipeline

### Enhanced Phase 2: Continuous Improvement (Weeks 3-4)

1. **Expand Training Data**
   - Add gensim for topic modeling on synthetic data
   - Generate domain-specific patterns per programming language
   - A/B test different model architectures

2. **Active Learning Integration**
   - Monitor fallback usage patterns
   - Identify edge cases where fallback fails
   - Generate additional training data for weak areas

### Enhanced Phase 3: Production Optimization (Future)

1. **Self-Improving Pipeline**
   - User feedback integration
   - Continuous model retraining
   - Performance optimization based on real usage

## Advantages of This Approach

**1. Domain-Specific Training**
- Generated data matches actual CodeWeaver use cases
- Realistic developer query patterns
- Covers edge cases from diverse codebases

**2. Scalable Data Generation**
- Can generate thousands of examples quickly
- Easy to expand to new domains/languages
- Quality control through pydantic-evals

**3. Cost-Effective**
- Uses existing infrastructure
- No manual annotation required
- Leverages LLM capabilities for bootstrapping

**4. Continuous Improvement**
- Data generation can be ongoing
- Models improve as more codebases analyzed
- Self-correcting through evaluation loops

## Integration with Existing Architecture

```python
# Enhanced pydantic-graph integration
class CodeWeaverPipeline:
    def __init__(self):
        self.llm_resolver = LLMIntentResolver()  # Primary
        self.ml_resolver = SyntheticTrainedResolver()  # Fallback
        self.data_generator = TrainingDataGenerator()  # Bootstrap
        
    async def resolve_intent(self, query):
        try:
            return await self.llm_resolver.resolve(query)
        except (ConnectionError, RateLimitError):
            # Use ML fallback trained on synthetic data
            return await self.ml_resolver.resolve(query)
            
    async def improve_system(self):
        # Continuous improvement cycle
        new_data = await self.data_generator.generate_from_recent_codebases()
        await self.ml_resolver.retrain(new_data)
```

## Updated Blocking Questions

1. **LLM Provider Access**: Which pydantic-ai providers will be available for training data generation?
2. **Codebase Access**: Can CodeWeaver analyze its own codebase + sample GitHub repos for training?
3. **Evaluation Criteria**: What pydantic-evals metrics should validate synthetic training data quality?
4. **Retraining Frequency**: How often should the fallback models be updated with new synthetic data?

## Non-blocking Questions

1. **Evaluation Metrics**: How will you measure the quality of intent resolution?
2. **Continuous Learning**: Interest in online learning/adaptation based on user feedback?
3. **Multilingual Support**: Need for non-English code comment/documentation processing?
4. **Integration Timeline**: Preferred rollout strategy (all-at-once vs. progressive)?

## Recommended Implementation Path

### Phase 1 (Weeks 1-2): Minimal Viable Fallback
1. Implement Tier 1 solution with scikit-learn
2. Create basic intent classification for common patterns
3. Build TF-IDF-based similarity search
4. Establish fallback architecture

### Phase 2 (Weeks 3-4): Enhanced Capabilities  
1. Add gensim for topic modeling (if dependency acceptable)
2. Implement query expansion using topic similarity
3. Add clustering for code organization
4. Performance optimization

### Phase 3 (Future): Advanced Features
1. Consider spaCy integration for complex entity extraction
2. Advanced semantic similarity
3. Custom model training on your specific codebase patterns
4. Machine learning pipeline optimization

## Sources

### Primary Research Sources

[scikit-learn/scikit-learn | GitHub | v1.7.1] - Comprehensive machine learning library with text processing capabilities, TF-IDF vectorization, and classification algorithms. Extensive documentation on text feature extraction and similarity metrics.

[piskvorky/gensim | GitHub | latest] - Topic modeling and document similarity library with 2482 code snippets. Specialized for large-scale text processing, LDA/LSI topic modeling, and document indexing with memory-efficient algorithms.

[explosion/spacy | GitHub | latest] - Industrial-strength NLP library with 1578 code snippets. Advanced text processing pipeline with tokenization, NER, similarity computation, and extensible component system.

### Supporting Research Sources

[BM25 implementations on GitHub](https://github.com/topics/bm25) - Various lightweight BM25 implementations for ranking and retrieval

[Analytics Vidhya NLP Libraries Guide](https://www.analyticsvidhya.com/blog/2021/05/top-python-libraries-for-natural-language-processing-nlp-in/) - Overview of Python NLP ecosystem and alternatives

[Intent Classification Architecture Patterns](https://spotintelligence.com/2023/11/03/intent-classification-nlp/) - Modern approaches to intent classification without deep learning

## Risk Assessment

**Low Risk:**
- Tier 1 implementation with scikit-learn (mature, stable, well-documented)
- Basic TF-IDF and similarity matching (proven techniques)

**Medium Risk:**
- gensim integration (additional complexity, memory usage)
- Custom topic modeling (requires parameter tuning)

**High Risk:**
- spaCy with large models (significant dependency weight)
- Complex multi-tier fallback system (maintenance overhead)

## Next Steps

1. **Proof of Concept**: Implement Tier 1 solution with a small dataset
2. **Dependency Analysis**: Measure actual memory/storage impact in target environment
3. **Performance Benchmarking**: Test with representative CodeWeaver queries
4. **Integration Planning**: Design fallback integration with existing pydantic-graph pipeline
5. **Evaluation Framework**: Establish metrics for measuring intent resolution quality