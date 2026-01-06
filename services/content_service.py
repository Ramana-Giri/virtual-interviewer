from sentence_transformers import SentenceTransformer, util
import nltk
import config

# Download necessary NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')

print("⏳ Loading Content Model (S-BERT)... This happens only once.")
# We use 'all-MiniLM-L6-v2' because it is 5x faster than BERT-Base 
# but almost equally accurate for this task.
model = SentenceTransformer('all-MiniLM-L6-v2')

class ContentService:
    def __init__(self):
        # List of strong action verbs recruiters love
        self.STRONG_VERBS = {
            "architected", "deployed", "optimized", "scaled", "led", "managed",
            "resolved", "built", "designed", "implemented", "reduced", "improved"
        }
        
        self.FILLER_WORDS = {"um", "ah","uh", "like", "you know", "actually", "basically", "sort of"}

    def analyze(self, transcript, ideal_answer_keywords):
        print(f"📖 Analyzing Content: {len(transcript)} chars")
        
        # 1. Semantic Relevance (S-BERT)
        # We construct an "Ideal Answer" string from the keywords to compare against
        ideal_sentence = " ".join(ideal_answer_keywords)
        
        # Encode both sentences into Vector Space
        embedding_1 = model.encode(transcript, convert_to_tensor=True)
        embedding_2 = model.encode(ideal_sentence, convert_to_tensor=True)
        
        # Calculate Cosine Similarity (0 to 1) -> Convert to 0-100 Score
        similarity = util.pytorch_cos_sim(embedding_1, embedding_2).item()
        relevance_score = int(similarity * 100)
        
        # 2. Vocabulary Analysis (NLTK)
        words = nltk.word_tokenize(transcript.lower())
        word_count = len(words)
        
        if word_count == 0:
            return {"relevance": 0, "strong_verbs": 0, "fillers": 0}

        # Count Strong Verbs
        action_verb_count = sum(1 for w in words if w in self.STRONG_VERBS)
        
        # Count Fillers
        filler_count = sum(1 for w in words if w in self.FILLER_WORDS)
        filler_ratio = (filler_count / word_count) * 100  # Percentage of speech that is garbage
        
        return {
            "relevance_score": relevance_score,
            "action_verb_count": action_verb_count,
            "filler_word_count": filler_count,
            "filler_ratio_percent": round(filler_ratio, 2)
        }